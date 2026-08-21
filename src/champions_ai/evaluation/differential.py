"""Check our damage model against the engine, on inputs we fully control.

Every calibration so far has used **replays**, which are observational: when
prediction and reality disagree we cannot tell whether the formula is wrong or
we simply do not know their spread, item and ability. Untangling that confound
took a whole session and two wrong hypotheses.

This removes the confound. We run the battle ourselves, so both sides' real
stats come from the engine's own request payloads, and every disagreement has
exactly one possible cause: **our formula is wrong**.

That makes it a different instrument from the replay calibration, answering a
different question:

- **replays** tell us what spreads and items people actually run -- a fact about
  the metagame;
- **the engine** tells us whether our arithmetic is right -- a fact about the
  rules.

Samples are collected from the *omniscient* protocol stream rather than either
player's view, which is safe here and only here: this is a referee measuring the
game, not an agent playing it. Nothing in this module may be used to build an
`Observation`.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from champions_ai.dex import Dex
from champions_ai.domain import BattlePokemon
from champions_ai.mechanics import apply_boost, estimate_damage
from champions_ai.simulator.tracker import split_ident, to_id

# Damage lines carrying one of these describe residual damage -- recoil, a
# status, hazards, weather -- rather than the move that preceded them.
RESIDUAL_MARKER = "[from]"

# Side conditions that halve incoming damage. Unmodelled, so a hit taken behind
# one cannot be compared against a prediction that ignores it.
SCREEN_CONDITIONS = frozenset({"reflect", "lightscreen", "auroraveil"})


@dataclass(frozen=True)
class DamageSample:
    """One hit, with everything needed to reproduce our prediction of it."""

    attacker: BattlePokemon
    defender: BattlePokemon
    move_id: str
    actual: int
    defender_hp_before: int
    weather: str | None
    critical: bool
    spread: bool
    # A screen was up on the defending side. Reflect, Light Screen and Aurora
    # Veil halve damage and we do not model them, so these are excluded rather
    # than scored as arithmetic errors.
    behind_screen: bool = False
    # How many targets the move actually reached. The engine only applies the
    # spread reduction when a move hits more than one, so a Heat Wave into a
    # single remaining opponent does full damage.
    spread_targets: int = 1
    # The target fainted, so `actual` is the HP it had left rather than the
    # damage the move dealt. A hit that overkills by 80 is recorded as the 15
    # the target could absorb, which reads as a wild over-prediction.
    truncated: bool = False

    def predict(self, dex: Dex, *, level: int, doubles: bool) -> tuple[int, int]:
        """Our predicted damage range for this exact hit."""
        move = dex.get_move(self.move_id)
        physical = move.category == "Physical"
        stats = self.attacker.computed_stats or {}
        guard = self.defender.computed_stats or {}
        # Stat stages are not in `computed_stats` -- the request reports the
        # stats before them -- and Intimidate alone makes them vary constantly.
        attack = apply_boost(
            stats.get("atk" if physical else "spa", 100),
            getattr(self.attacker.boosts, "attack" if physical else "special_attack"),
        )
        defence = apply_boost(
            guard.get("def" if physical else "spd", 100),
            getattr(self.defender.boosts, "defense" if physical else "special_defense"),
        )
        estimate = estimate_damage(
            dex,
            move,
            attacker=dex.get_species(self.attacker.pokemon_set.species),
            attack_stat=attack,
            defender=dex.get_species(self.defender.pokemon_set.species),
            defense_stat=defence,
            defender_hp=max(1, self.defender_hp_before),
            level=level,
            # The spread reduction only applies when a move reaches more than
            # one target, so tell the estimator this is a singles-shaped hit
            # when the engine says it only hit one.
            doubles=doubles and self.spread_targets > 1,
            attacker_burned=self.attacker.status == "brn",
            weather=self.weather,
        )
        return estimate.minimum, estimate.maximum


@dataclass
class DifferentialReport:
    """How our predictions compared with what the engine actually did."""

    samples: int = 0
    inside_range: int = 0
    above_range: int = 0
    below_range: int = 0
    skipped: int = 0
    mismatches: list[str] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.inside_range / self.samples if self.samples else 0.0

    def summary(self) -> str:
        return (
            f"{self.inside_range}/{self.samples} inside the predicted range "
            f"({self.accuracy:.1%}); {self.above_range} under-predicted, "
            f"{self.below_range} over-predicted; {self.skipped} skipped"
        )


def collect_samples(
    protocol: Sequence[str],
    active_lookup: Callable[[str], BattlePokemon | None],
    *,
    weather: str | None = None,
) -> list[DamageSample]:
    """Pair `|move|` lines with the `|-damage|` they caused.

    `active_lookup` maps a protocol ident (`p1a: Chomper`) to that Pokemon as
    its *own* player sees it, which is where the engine's computed stats live.

    A damage line is only attributed to the move before it when nothing
    intervenes: no `[from]` marker (that is residual damage), and never the
    attacker damaging itself (that is recoil).
    """
    samples: list[DamageSample] = []
    hp: dict[str, int] = {}
    pending: tuple[str, str] | None = None
    critical = False
    spread = False
    spread_targets = 1
    multi_hit = False
    screens: dict[str, set[str]] = {"p1": set(), "p2": set()}

    for line in protocol:
        parts = line.split("|")
        if len(parts) < 3:
            continue
        tag, args = parts[1], parts[2:]

        if tag in ("switch", "drag", "replace"):
            if len(args) > 2:
                hp[args[0]] = _current_hp(args[2])
            pending = None
        elif tag in ("-sidestart", "-sideend"):
            side = args[0].split(":")[0]
            condition = to_id(args[1].split(":")[-1])
            if condition in SCREEN_CONDITIONS and side in screens:
                if tag == "-sidestart":
                    screens[side].add(condition)
                else:
                    screens[side].discard(condition)
        elif tag == "-weather":
            weather = None if args[0] == "none" else to_id(args[0])
        elif tag == "-crit":
            critical = True
        elif tag == "-hitcount":
            # Multi-hit moves report one damage line per hit, so a single
            # prediction cannot be compared against any one of them.
            multi_hit = True
        elif tag == "move":
            if any(part.startswith(RESIDUAL_MARKER) for part in args):
                pending = None
                continue
            pending = (args[0], to_id(args[1]))
            critical = False
            multi_hit = False
            spread_note = next((p for p in args if p.startswith("[spread]")), None)
            spread = spread_note is not None
            spread_targets = (
                len([t for t in spread_note[len("[spread]"):].split(",") if t.strip()])
                if spread_note
                else 1
            )
        elif tag == "-damage" and pending is not None:
            if any(part.startswith(RESIDUAL_MARKER) for part in args):
                continue
            target = args[0]
            attacker_ident, move_id = pending
            before = hp.get(target)
            after = _current_hp(args[1])
            hp[target] = after
            if target == attacker_ident or before is None or after >= before:
                continue

            attacker = active_lookup(attacker_ident)
            defender = active_lookup(target)
            if attacker is not None and defender is not None and not multi_hit:
                samples.append(
                    DamageSample(
                        attacker=attacker,
                        defender=defender,
                        move_id=move_id,
                        actual=before - after,
                        defender_hp_before=before,
                        weather=weather,
                        critical=critical,
                        spread=spread,
                        spread_targets=spread_targets,
                        truncated=after == 0,
                        behind_screen=bool(screens.get(split_ident(target)[0], set())),
                    )
                )
            pending = None
        elif tag == "turn":
            pending = None

    return samples


def _current_hp(condition: str) -> int:
    """`123/194` or `0 fnt` -> 123 or 0."""
    head = condition.split()[0] if condition.strip() else "0"
    if head.startswith("0"):
        return 0
    return int(head.split("/")[0])


def compare(
    samples: Sequence[DamageSample],
    dex: Dex,
    *,
    level: int = 50,
    doubles: bool = True,
    include_crits: bool = False,
) -> DifferentialReport:
    """Score our predicted ranges against what the engine actually dealt.

    Critical hits are excluded by default because the model does not claim to
    predict them: it estimates the ordinary damage roll, and a crit is a
    different calculation. Counting them as misses would report a known
    omission as an arithmetic error.

    Hits that knocked the target out are excluded always, because the protocol
    records how much HP the target *lost*, which for an overkill is how much it
    had rather than how much the move dealt.
    """
    report = DifferentialReport()
    for sample in samples:
        if sample.critical and not include_crits:
            report.skipped += 1
            continue
        if sample.behind_screen:
            # Halved by a screen we do not model. Scoring it would report a
            # known omission as an arithmetic error.
            report.skipped += 1
            continue
        if sample.truncated:
            # The target fainted, so the observed drop is what it could absorb
            # rather than what the move dealt. Comparing against it would score
            # every overkill as an over-prediction.
            report.skipped += 1
            continue
        try:
            low, high = sample.predict(dex, level=level, doubles=doubles)
        except KeyError:
            report.skipped += 1
            continue

        report.samples += 1
        if low <= sample.actual <= high:
            report.inside_range += 1
            continue

        if sample.actual > high:
            report.above_range += 1
            direction = "under"
        else:
            report.below_range += 1
            direction = "over"
        if len(report.mismatches) < 25:
            report.mismatches.append(
                f"{sample.attacker.pokemon_set.species} {sample.move_id} -> "
                f"{sample.defender.pokemon_set.species}: predicted {low}-{high}, "
                f"engine dealt {sample.actual} ({direction}-predicted"
                + (", spread" if sample.spread else "")
                + (f", {sample.weather}" if sample.weather else "")
                + ")"
            )
    return report


def active_by_ident(sides: dict[str, list[BattlePokemon]]) -> Callable[[str], BattlePokemon | None]:
    """Build a lookup from `p1a: Chomper` to that Pokemon on its own side.

    Matching is by species rather than nickname because the request payload
    identifies Pokemon by species while the protocol may use a nickname, and
    Species Clause makes species unique within a team.
    """

    def lookup(ident: str) -> BattlePokemon | None:
        side, _, name = split_ident(ident)
        for mon in sides.get(side, ()):
            if to_id(mon.pokemon_set.species) == to_id(name):
                return mon
        return None

    return lookup
