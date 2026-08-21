"""Estimate what a move would do.

A range rather than a number: the engine's random factor spreads real damage
across 85-100% of the maximum roll, so "does this KO" is a probability, not a
yes or no. A heuristic that reasons only about average damage will confidently
leave things alive.

This deliberately models the main terms -- base power, the attack/defense
ratio, STAB, type effectiveness, the doubles spread reduction, burn, weather --
and not the long tail of abilities and items. It is an *estimate* used to rank
actions, not a replacement for the simulator, which remains the authority on
what actually happens.

Weather was added after calibrating against 5,123 real attacks, where Sun was
the worst-fitting group at 0.82x predicted/actual -- exactly the shape of an
unmodelled 1.5x on Fire.
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

# Weather that scales a move by its type. Verified against `onWeatherModifyDamage`
# in the engine's conditions.ts rather than from memory.
WEATHER_TYPE_MULTIPLIERS: dict[str, dict[str, float]] = {
    "sunnyday": {"Fire": 1.5, "Water": 0.5},
    "raindance": {"Water": 1.5, "Fire": 0.5},
    # The primal weathers negate the opposing type outright rather than halving
    # it. Not in Reg M-B, but wrong-by-omission is the failure this table exists
    # to avoid.
    "desolateland": {"Fire": 1.5, "Water": 0.0},
    "primordialsea": {"Water": 1.5, "Fire": 0.0},
}

# Weather that raises one defensive stat, and only for one type. These are not
# damage multipliers: sandstorm boosts a Rock-type's Special Defense and snow
# boosts an Ice-type's Defense, so they apply to the stat before the ratio.
WEATHER_DEFENCE_BOOSTS: dict[str, tuple[str, str]] = {
    "sandstorm": ("Rock", "Special"),
    "snowscape": ("Ice", "Physical"),
    "snow": ("Ice", "Physical"),
}
WEATHER_DEFENCE_MULTIPLIER = 1.5


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
    weather: str | None = None,
    base_power: int | None = None,
) -> DamageEstimate:
    """Estimate a single hit's damage range.

    Returns a zero range for status moves and immunities, so callers can treat
    "deals no damage" uniformly rather than special-casing each reason.

    `weather` is Showdown's id (`sunnyday`, `raindance`, `sandstorm`,
    `snowscape`). An unknown value is ignored rather than guessed at, so a new
    weather costs accuracy but never correctness.

    `base_power` overrides the move's static value, for the eleven moves whose
    power the engine computes per hit. See `mechanics.base_power`.
    """
    effectiveness = dex.type_chart.effectiveness(move.type, defender.types)

    if not move.is_damaging or effectiveness == 0.0:
        return DamageEstimate(0, 0, effectiveness, defender_hp)

    # Sandstorm and snow raise a defensive stat rather than scaling damage, so
    # they belong to the ratio and must be applied before it, not after.
    boosted = WEATHER_DEFENCE_BOOSTS.get(weather or "")
    if boosted is not None:
        typing, category = boosted
        if typing in defender.types and move.category == category:
            defense_stat = int(defense_stat * WEATHER_DEFENCE_MULTIPLIER)

    # Engine order: the level/power/ratio term, then +2, then the modifiers.
    power = move.base_power if base_power is None else base_power
    base = (2 * level // 5 + 2) * power * attack_stat // max(1, defense_stat) // 50 + 2

    multiplier = effectiveness
    if move.type in attacker.types:
        multiplier *= STAB_MULTIPLIER
    if doubles and is_spread_move(move):
        multiplier *= SPREAD_MULTIPLIER
    if attacker_burned and move.category == "Physical":
        multiplier *= BURN_MULTIPLIER
    multiplier *= WEATHER_TYPE_MULTIPLIERS.get(weather or "", {}).get(move.type, 1.0)

    # A zero multiplier means the move genuinely does nothing -- a primal
    # weather negating the opposing type, say. The floor of 1 below exists so a
    # real hit never rounds away to nothing, and applying it here would turn
    # "cannot damage" into "does 1".
    if multiplier == 0.0:
        return DamageEstimate(0, 0, effectiveness, defender_hp)

    return DamageEstimate(
        minimum=max(1, int(base * multiplier * MIN_ROLL)),
        maximum=max(1, int(base * multiplier * MAX_ROLL)),
        effectiveness=effectiveness,
        defender_hp=defender_hp,
    )
