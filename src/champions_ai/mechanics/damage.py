"""Estimate what a move would do.

A range rather than a number: the engine's random factor spreads real damage
across 85-100% of the maximum roll, so "does this KO" is a probability, not a
yes or no. A heuristic that reasons only about average damage will confidently
leave things alive.

This deliberately models the main terms -- base power, the attack/defense
ratio, STAB, type effectiveness, the doubles spread reduction, burn -- and not
the long tail of abilities, items and field effects. It is an *estimate* used
to rank actions, not a replacement for the simulator, which remains the
authority on what actually happens.
"""

from dataclasses import dataclass

from champions_ai.dex import Dex, MoveInfo, SpeciesInfo

# The engine rolls damage uniformly across these fractions of the max roll.
MIN_ROLL = 0.85
MAX_ROLL = 1.0
AVERAGE_ROLL = (MIN_ROLL + MAX_ROLL) / 2

STAB_MULTIPLIER = 1.5
SPREAD_MULTIPLIER = 0.75  # doubles only
BURN_MULTIPLIER = 0.5  # physical moves only

SPREAD_TARGETS = frozenset({"allAdjacentFoes", "allAdjacent"})


@dataclass(frozen=True)
class DamageEstimate:
    """What a move is expected to do, as a range."""

    minimum: int
    maximum: int
    effectiveness: float
    defender_hp: int

    @property
    def average(self) -> float:
        return (self.minimum + self.maximum) / 2

    @property
    def average_fraction(self) -> float:
        """Expected damage as a fraction of the defender's remaining HP."""
        if self.defender_hp <= 0:
            return 0.0
        return min(1.0, self.average / self.defender_hp)

    @property
    def guaranteed_ko(self) -> bool:
        """Even the worst roll finishes it."""
        return self.minimum >= self.defender_hp > 0

    @property
    def possible_ko(self) -> bool:
        """The best roll finishes it -- a real chance, not a certainty."""
        return self.maximum >= self.defender_hp > 0

    @property
    def is_immune(self) -> bool:
        return self.effectiveness == 0.0


def is_spread_move(move: MoveInfo) -> bool:
    return move.target in SPREAD_TARGETS


def estimate_damage(
    dex: Dex,
    move: MoveInfo,
    *,
    attacker: SpeciesInfo,
    attack_stat: int,
    defender: SpeciesInfo,
    defense_stat: int,
    defender_hp: int,
    level: int = 50,
    doubles: bool = True,
    attacker_burned: bool = False,
) -> DamageEstimate:
    """Estimate a single hit's damage range.

    Returns a zero range for status moves and immunities, so callers can treat
    "deals no damage" uniformly rather than special-casing each reason.
    """
    effectiveness = dex.type_chart.effectiveness(move.type, defender.types)

    if not move.is_damaging or effectiveness == 0.0:
        return DamageEstimate(0, 0, effectiveness, defender_hp)

    # Engine order: the level/power/ratio term, then +2, then the modifiers.
    base = (2 * level // 5 + 2) * move.base_power * attack_stat // defense_stat // 50 + 2

    multiplier = effectiveness
    if move.type in attacker.types:
        multiplier *= STAB_MULTIPLIER
    if doubles and is_spread_move(move):
        multiplier *= SPREAD_MULTIPLIER
    if attacker_burned and move.category == "Physical":
        multiplier *= BURN_MULTIPLIER

    return DamageEstimate(
        minimum=max(1, int(base * multiplier * MIN_ROLL)),
        maximum=max(1, int(base * multiplier * MAX_ROLL)),
        effectiveness=effectiveness,
        defender_hp=defender_hp,
    )
