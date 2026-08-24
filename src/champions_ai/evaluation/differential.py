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
from champions_ai.mechanics import (
    apply_boost,
    attacking_side,
    dynamic_base_power,
    estimate_damage,
    is_removable,
)
from champions_ai.simulator.tracker import TERRAINS, split_ident, to_id

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
    # Field state the engine feeds into a base-power callback: Rising Voltage
    # doubles on Electric Terrain, Last Respects grows with the attacker's
    # fallen teammates.
    terrain: str | None = None
    fainted_allies: int = 0

    def predict(self, dex: Dex, *, level: int, doubles: bool) -> tuple[int, int]:
        """Our predicted damage range for this exact hit."""
        move = dex.get_move(self.move_id)
        # Not every move uses the stat its category implies -- Body Press
        # swings with Defense, Psyshock lands on it -- and Foul Play reads its
        # attacking stat off the target, so ask the move for both.
        attacking = move.offensive_stat
        defending = move.defensive_stat
        swinger = attacking_side(move, user=self.attacker, target=self.defender)
        stats = swinger.computed_stats or {}
        guard = self.defender.computed_stats or {}
        # Stat stages are not in `computed_stats` -- the request reports the
        # stats before them -- and Intimidate alone makes them vary constantly.
        attack = apply_boost(stats.get(attacking, 100), swinger.boosts.stage(attacking))
        defence = apply_boost(
            guard.get(defending, 100),
            # Darkest Lariat and Sacred Sword ignore the target's defensive
            # stages outright.
            0 if move.ignore_defensive else self.defender.boosts.stage(defending),
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
            attacker_item=self.attacker.current_item,
            defender_item=self.defender.current_item,
            attacker_hp=self.attacker.current_hp,
            terrain=self.terrain,
            # Twenty-nine moves have their power computed per hit, and the
            # harness was comparing against the static value for all of them --
            # so a Stored Power off two Calm Minds read as a fivefold error in
            # the formula when the formula was fine.
            base_power=dynamic_base_power(
                move,
                attacker=dex.get_species(self.attacker.pokemon_set.species),
                defender=dex.get_species(self.defender.pokemon_set.species),
                attacker_hp_fraction=self.attacker.hp_fraction,
                attacker_speed=(self.attacker.computed_stats or {}).get("spe"),
                defender_speed=(self.defender.computed_stats or {}).get("spe"),
                attacker_holds_item=self.attacker.current_item is not None,
                attacker_positive_boosts=self.attacker.boosts.positive_total,
                attacker_status=self.attacker.status,
                defender_status=self.defender.status,
                defender_item_removable=is_removable(
                    dex.items.get(self.defender.current_item or ""),
                    dex.get_species(self.defender.pokemon_set.species),
                    self.defender.current_ability,
                ),
                fainted_allies=self.fainted_allies,
                terrain=self.terrain,
                weather=self.weather,
            ),
            opponents=self.spread_targets,
            defender_at_full_hp=self.defender_hp_before >= self.defender.max_hp,
            defender_ability=self.defender.current_ability,
            attacker_volatiles=tuple(self.attacker.volatile_conditions),
            defender_volatiles=tuple(self.defender.volatile_conditions),
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


class DamageCollector:
    """Pairs `|move|` lines with the `|-damage|` they caused, across a stream.

    Stateful on purpose. A `|-damage|` line reports the HP the target has
    *after* the hit, so the damage dealt is only recoverable as a difference
    from a value carried in from earlier lines. That state has to outlive one
    chunk of protocol, because the runner reads the protocol a turn at a time.

    Handing each turn to a function that starts with an empty HP table drops
    the first hit on every target, every turn -- silently, because a hit with
    no known starting HP looks exactly like a hit that should be ignored. It
    left roughly one sample per battle, and the ones it kept were second hits:
    spread moves and focus-fire onto weakened targets, which is not a fair
    sample of anything. `unknown_hp` counts them now, so the same mistake is
    loud rather than silent.
    """

    def __init__(self, *, weather: str | None = None) -> None:
        self.weather = weather
        self.terrain: str | None = None
        self._fainted: dict[str, int] = {"p1": 0, "p2": 0}
        self._hp: dict[str, int] = {}
        self._screens: dict[str, set[str]] = {"p1": set(), "p2": set()}
        self.unknown_hp = 0
        """Hits dropped because the target's HP before them was not known."""

    def feed(
        self,
        protocol: Sequence[str],
        active_lookup: Callable[[str], BattlePokemon | None],
    ) -> list[DamageSample]:
        """Consume the next chunk of protocol and return what it yielded.

        `active_lookup` maps a protocol ident (`p1a: Chomper`) to that Pokemon
        as its *own* player sees it, which is where the engine's computed stats
        live. It is a per-chunk argument rather than collector state because it
        is a snapshot: who is active and what stages they carry both change
        from turn to turn, and a stale snapshot would score a hit against the
        Pokemon that used to be in that slot.

        A damage line is only attributed to the move before it when nothing
        intervenes: no `[from]` marker (that is residual damage), and never the
        attacker damaging itself (that is recoil).

        One sample is emitted per *target*, covering everything that move did
        to it -- so a five-hit Icicle Spear is one sample of the whole run, and
        a spread move produces one per Pokemon it reached.
        """
        samples: list[DamageSample] = []
        pending: tuple[str, str] | None = None
        critical = False
        spread = False
        spread_targets = 1
        # Every target this move has hit so far, as (HP before its first hit,
        # HP after its latest). Accumulated rather than taken one line at a
        # time, because a multi-hit move reports each hit separately and a
        # spread move reports each target separately -- and taking the first
        # line and stopping threw away every hit after it. Icicle Spear was
        # scored on a third of its damage, and the second target of every
        # spread move was never sampled at all.
        landed: dict[str, tuple[int, int]] = {}

        def flush() -> None:
            if pending is None:
                return
            attacker_ident, move_id = pending
            for target, (first, last) in landed.items():
                if last >= first:
                    continue
                attacker = active_lookup(attacker_ident)
                defender = active_lookup(target)
                if attacker is None or defender is None:
                    continue
                samples.append(
                    DamageSample(
                        attacker=attacker,
                        defender=defender,
                        move_id=move_id,
                        actual=first - last,
                        defender_hp_before=first,
                        weather=self.weather,
                        critical=critical,
                        spread=spread,
                        spread_targets=spread_targets,
                        truncated=last == 0,
                        behind_screen=bool(
                            self._screens.get(split_ident(target)[0], set())
                        ),
                        terrain=self.terrain,
                        fainted_allies=self._fainted.get(
                            split_ident(attacker_ident)[0], 0
                        ),
                    )
                )
            landed.clear()

        for line in protocol:
            parts = line.split("|")
            if len(parts) < 3:
                continue
            tag, args = parts[1], parts[2:]

            if tag in ("switch", "drag", "replace"):
                flush()
                if len(args) > 2:
                    self._hp[args[0]] = _current_hp(args[2])
                pending = None
            elif tag in ("-heal", "-sethp"):
                # Not a sample, but it moves the target's HP. Missing these
                # would make the *next* hit on that Pokemon read as a huge
                # over-prediction, or as no damage at all.
                if len(args) > 1:
                    self._hp[args[0]] = _current_hp(args[1])
            elif tag in ("-sidestart", "-sideend"):
                side = args[0].split(":")[0]
                condition = to_id(args[1].split(":")[-1])
                if condition in SCREEN_CONDITIONS and side in self._screens:
                    if tag == "-sidestart":
                        self._screens[side].add(condition)
                    else:
                        self._screens[side].discard(condition)
            elif tag == "-weather":
                self.weather = None if args[0] == "none" else to_id(args[0])
            elif tag == "-fieldstart":
                # `-fieldstart` also carries Trick Room and Gravity, so the tag
                # alone does not mean a terrain went up.
                condition = to_id(args[0].split(":")[-1])
                if condition in TERRAINS:
                    self.terrain = condition
            elif tag == "-fieldend":
                if to_id(args[0].split(":")[-1]) == self.terrain:
                    self.terrain = None
            elif tag == "faint":
                side = split_ident(args[0])[0]
                if side in self._fainted:
                    self._fainted[side] += 1
            elif tag == "-crit":
                critical = True
            elif tag == "move":
                flush()
                if any(part.startswith(RESIDUAL_MARKER) for part in args):
                    pending = None
                    continue
                pending = (args[0], to_id(args[1]))
                critical = False
                spread_note = next((p for p in args if p.startswith("[spread]")), None)
                spread = spread_note is not None
                spread_targets = (
                    len([t for t in spread_note[len("[spread]"):].split(",") if t.strip()])
                    if spread_note
                    else 1
                )
            elif tag == "-damage":
                target = args[0]
                before = self._hp.get(target)
                after = _current_hp(args[1])
                # Recorded whatever caused it. Residual damage -- recoil, a
                # burn tick, hazards -- is not a sample, but it moves the HP
                # the *next* hit has to be measured from. Skipping the line
                # outright left a stale, higher figure behind, so the next
                # real hit was credited with the residual as well: a Knock Off
                # that dealt 23 was recorded as 71.
                self._hp[target] = after
                if pending is None:
                    continue
                if any(part.startswith(RESIDUAL_MARKER) for part in args):
                    continue
                attacker_ident, _ = pending
                if target == attacker_ident:
                    continue
                if target in landed:
                    # A later hit of the same move: extend the run rather than
                    # starting a new sample from the HP the last hit left.
                    landed[target] = (landed[target][0], after)
                    continue
                if before is None:
                    self.unknown_hp += 1
                    continue
                landed[target] = (before, after)
            elif tag == "turn":
                flush()
                pending = None

        flush()
        return samples


def collect_samples(
    protocol: Sequence[str],
    active_lookup: Callable[[str], BattlePokemon | None],
    *,
    weather: str | None = None,
) -> list[DamageSample]:
    """Every sample in one complete protocol.

    For a whole battle log. A caller reading the protocol as it arrives wants
    `DamageCollector`, which carries HP between chunks.
    """
    return DamageCollector(weather=weather).feed(protocol, active_lookup)


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
