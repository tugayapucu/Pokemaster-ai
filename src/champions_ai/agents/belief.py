"""What we think the opponent's Stat Points are, inferred from what we have seen.

Stat Points are never published (ADR 0002), so the agent has always assumed the
neutral spread: 66 points shared evenly, eleven per stat. Experiment 0018
measured what perfect knowledge would be worth and found **+4.3 points of win
rate, essentially all of it spreads** — item and ability knowledge together
moved nothing. So this infers spreads and nothing else.

The signal is damage. Every hit is an equation with one unknown:

    a hit we take     tells us about their attacking stat
    a hit we land     tells us about their defending stat

Everything else in the damage formula is either ours (known exactly from our
own request) or public (the move, the weather, the terrain, the stages).

**Inverted by search rather than by algebra.** Damage rises monotonically with
the attacking stat and falls monotonically with the defending one, so a binary
search over `estimate_damage` finds the stat that would have produced what we
saw. That reuses the model already measured at 93.9% against the engine instead
of re-deriving its inverse and having two things to keep in step.

**Only unambiguous turns teach us anything.** In doubles two of ours attack and
two of theirs can lose HP, and attributing the wrong damage to the wrong
Pokemon is worse than not learning: a wrong belief is acted on with the same
confidence as a right one. So an observation is used only when exactly one
attacker and one victim can be paired.
"""

from dataclasses import dataclass, field

from champions_ai.dex import Dex, MoveInfo, SpeciesInfo
from champions_ai.mechanics.damage import estimate_damage
from champions_ai.mechanics.stats import STAT_CONSTANT, hp_stat, other_stat

# The regulation's own limits. A spread that breaks them is not a spread.
MAX_POINTS_PER_STAT = 32
TOTAL_POINTS = 66
NEUTRAL_POINTS = 11

# Stats we can learn about, and the move category each is read from.
ATTACKING = {"Physical": "atk", "Special": "spa"}
DEFENDING = {"Physical": "def", "Special": "spd"}

# A hit carries a damage roll worth +/-7.5%, so one reading is evidence rather
# than proof. But an exponential walk from the prior was worse than useless
# here: with one or two observations per stat it never travels far enough to
# beat the prior it started from, which is exactly what the first measurement
# showed (16.0 -> 15.4 points of error, 61 closer and 48 further).
#
# So the estimate is the *mean of what the hits imply*, and the prior is only
# what we report before any of them land. Evidence replaces the guess rather
# than nudging it.


def points_from_stat(base: int, stat: int) -> int:
    """Invert `other_stat` for a neutral nature, clamped to what is legal."""
    return max(0, min(MAX_POINTS_PER_STAT, stat - base - STAT_CONSTANT))


@dataclass
class SpreadBelief:
    """One opponent's inferred Stat Points, and how much we have seen."""

    points: dict[str, int] = field(
        default_factory=lambda: {
            key: NEUTRAL_POINTS for key in ("hp", "atk", "def", "spa", "spd", "spe")
        }
    )
    observations: dict[str, int] = field(default_factory=dict)
    # Every value the hits have implied, per stat, so the estimate is their
    # mean rather than a walk away from a guess.
    _implied: dict[str, list[int]] = field(default_factory=dict)

    def learn(self, key: str, inferred: int) -> None:
        """Take this stat to be the average of what the hits have implied."""
        seen = self._implied.setdefault(key, [])
        seen.append(max(0, min(MAX_POINTS_PER_STAT, inferred)))
        self.points[key] = round(sum(seen) / len(seen))
        self.observations[key] = len(seen)
        self._rebalance(key)

    def _rebalance(self, protected: str) -> None:
        """Keep the total legal by taking back from what we have not measured.

        Raising one stat has to cost another, because 66 points is the whole
        budget. What we have *seen* is better evidence than the prior, so the
        cost falls on the stats no hit has told us anything about.
        """
        while sum(self.points.values()) > TOTAL_POINTS:
            unmeasured = [
                key
                for key, value in self.points.items()
                if key != protected and value > 0 and not self.observations.get(key)
            ]
            pool = unmeasured or [
                key for key, value in self.points.items()
                if key != protected and value > 0
            ]
            if not pool:
                return
            # Take from the largest first, so the spread stays plausible.
            richest = max(pool, key=lambda key: self.points[key])
            self.points[richest] -= 1

    def stats(self, species: SpeciesInfo) -> dict[str, int]:
        base = species.base_stats
        return {
            "hp": hp_stat(base.hp, self.points["hp"]),
            "atk": other_stat(base.attack, self.points["atk"]),
            "def": other_stat(base.defense, self.points["def"]),
            "spa": other_stat(base.special_attack, self.points["spa"]),
            "spd": other_stat(base.special_defense, self.points["spd"]),
            "spe": other_stat(base.speed, self.points["spe"]),
        }


class OpponentBelief:
    """Everything we have worked out about the other side, per species."""

    def __init__(self, dex: Dex) -> None:
        self.dex = dex
        self._by_species: dict[str, SpreadBelief] = {}

    def of(self, species_name: str) -> SpreadBelief:
        return self._by_species.setdefault(species_name, SpreadBelief())

    def stats(self, species: SpeciesInfo) -> dict[str, int]:
        return self.of(species.name).stats(species)

    # --- learning ---------------------------------------------------------

    def note_hit_we_landed(
        self,
        *,
        move: MoveInfo,
        attacker: SpeciesInfo,
        attack_stat: int,
        defender: SpeciesInfo,
        defender_max_hp: int,
        fraction_lost: float,
        **kwargs,
    ) -> None:
        """Their defending stat, from what our own attack actually did."""
        key = DEFENDING.get(move.category)
        if key is None or fraction_lost <= 0:
            return
        target = fraction_lost * defender_max_hp
        inferred = self._search(
            lambda candidate: self._predict(
                move, attacker, attack_stat, defender,
                defender_max_hp, defending=candidate, **kwargs
            ),
            target,
            base=getattr(defender.base_stats, _FIELD[key]),
            falling=True,
        )
        if inferred is not None:
            self.of(defender.name).learn(key, inferred)

    def note_hit_we_took(
        self,
        *,
        move: MoveInfo,
        attacker: SpeciesInfo,
        defender: SpeciesInfo,
        defence_stat: int,
        our_max_hp: int,
        fraction_lost: float,
        **kwargs,
    ) -> None:
        """Their attacking stat, from what their attack actually did to us."""
        key = ATTACKING.get(move.category)
        if key is None or fraction_lost <= 0:
            return
        target = fraction_lost * our_max_hp
        inferred = self._search(
            lambda candidate: self._predict(
                move, attacker, candidate, defender,
                our_max_hp, defending=defence_stat, **kwargs
            ),
            target,
            base=getattr(attacker.base_stats, _FIELD[key]),
            falling=False,
        )
        if inferred is not None:
            self.of(attacker.name).learn(key, inferred)

    # --- the search -------------------------------------------------------

    def _predict(
        self, move, attacker, attacking, defender, defender_hp, *, defending, **kwargs
    ) -> float:
        estimate = estimate_damage(
            self.dex,
            move,
            attacker=attacker,
            attack_stat=attacking,
            defender=defender,
            defense_stat=defending,
            defender_hp=defender_hp,
            **kwargs,
        )
        return (estimate.minimum + estimate.maximum) / 2

    def _search(self, predict, target: float, *, base: int, falling: bool):
        """The Stat Points that would have produced `target`.

        Binary search over the model rather than an inverse of it: damage is
        monotonic in both stats, and reusing `estimate_damage` keeps one
        formula in the project instead of two that can drift apart.
        """
        low, high = 0, MAX_POINTS_PER_STAT
        best, best_error = None, None
        for _ in range(7):
            middle = (low + high) // 2
            got = predict(other_stat(base, middle))
            error = abs(got - target)
            if best_error is None or error < best_error:
                best, best_error = middle, error
            if got == target:
                break
            # More points means more damage when attacking, less when defending.
            too_high = got > target
            if too_high != falling:
                high = middle - 1
            else:
                low = middle + 1
            if low > high:
                break
        return best


_FIELD = {
    "atk": "attack",
    "def": "defense",
    "spa": "special_attack",
    "spd": "special_defense",
    "spe": "speed",
    "hp": "hp",
}
