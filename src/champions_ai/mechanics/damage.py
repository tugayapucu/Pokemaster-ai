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
from typing import TypeVar

from champions_ai.dex import Dex, MoveInfo, SpeciesInfo
from champions_ai.mechanics.items import (
    attack_multiplier,
    base_power_multiplier,
    damage_multiplier,
    defender_multiplier,
)

T = TypeVar("T")

# The engine rolls damage uniformly across these fractions of the max roll.
MIN_ROLL = 0.85
MAX_ROLL = 1.0
AVERAGE_ROLL = (MIN_ROLL + MAX_ROLL) / 2

# The roll is 100 - random(16), applied as `trunc(trunc(damage * n) / 100)`.
MIN_ROLL_PERCENT = 85
MAX_ROLL_PERCENT = 100

# Showdown works in 4096ths and truncates at every step, so a "1.5x" is not a
# float multiply. Reproducing that matters more than it sounds: applying the
# modifiers in float and rounding once put our predicted minimum a point above
# the engine's actual damage often enough to be the largest remaining source of
# over-prediction in the differential.
MODIFIER_SCALE = 4096


def modify(value: int, multiplier: float) -> int:
    """Showdown's `Battle.modify`.

    `trunc(numerator * 4096 / denominator)` first, then
    `trunc((trunc(value * modifier) + 2047) / 4096)`. Expressing the multiplier
    as a float reproduces the engine's own constants exactly: 1.3 gives 5324,
    1.2 gives 4915, 1.1 gives 4505, which are the numbers in its source.
    """
    factor = int(multiplier * MODIFIER_SCALE)
    return int((int(value * factor) + MODIFIER_SCALE // 2 - 1) / MODIFIER_SCALE)


def _effectiveness_steps(effectiveness: float) -> int:
    """How many doublings the type chart is worth, as the engine counts them.

    It does not multiply by 0.25: it halves twice, truncating each time.
    """
    steps = 0
    value = effectiveness
    while value >= 2:
        steps += 1
        value /= 2
    while value <= 0.5:
        steps -= 1
        value *= 2
    return steps

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


# Fixed damage equal to the user's level. The engine spells it as a string.
LEVEL_DAMAGE = "level"

# Halves what the target has left, to a floor of one.
SUPER_FANG = "superfang"
# Brings the target down to the user's own remaining HP, and does nothing if
# the user has more.
ENDEAVOR = "endeavor"
# Deals exactly the user's remaining HP, and knocks the user out doing it.
FINAL_GAMBIT = "finalgambit"

# Reflect back what was just taken. All four need the damage this Pokemon
# received this turn, which nothing tracks, so they are left at zero -- but
# they still read as *damaging*, which is the part that was wrong.
REFLECTING_MOVES = frozenset({"counter", "mirrorcoat", "metalburst", "comeuppance"})


def fixed_damage(
    move: MoveInfo,
    *,
    level: int,
    defender_hp: int,
    attacker_hp: int = 0,
) -> int | None:
    """Damage that bypasses the formula, or None if this move does not.

    Nine moves here work this way and every one carries a zero base power with
    no `basePowerCallback`, so they read as status moves and were scored as
    support: Seismic Toss and Night Shade always deal 50 at this level, and
    Super Fang always takes half a health bar.
    """
    if not move.deals_fixed_damage:
        return None
    if move.fixed_damage == LEVEL_DAMAGE:
        return level
    if isinstance(move.fixed_damage, int):
        return move.fixed_damage
    if move.move_id == SUPER_FANG:
        return max(1, defender_hp // 2)
    if move.move_id == ENDEAVOR:
        return max(0, defender_hp - attacker_hp)
    if move.move_id == FINAL_GAMBIT:
        return attacker_hp
    # A reflecting move with nothing to reflect. Zero is the honest answer
    # until the damage taken this turn is tracked.
    return 0


def is_spread_move(move: MoveInfo) -> bool:
    return move.target in SPREAD_TARGETS


def attacking_side(move: MoveInfo, *, user: T, target: T) -> T:
    """Which side of the field the attacking stat is read from.

    Almost always the user. Foul Play is the exception: the engine sets
    `attacker = target` before reading either the stat or its stages, so a Foul
    Play says nothing about the Pokemon using it and everything about the one
    it is aimed at. Aimed at a Swords Dance user it swings at +2.

    Generic over whatever pair the caller has to hand -- a stat dict, a
    `BattlePokemon` -- so each call site keeps its own shape.
    """
    return target if move.uses_target_offense else user


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
    attacker_item: str | None = None,
    defender_item: str | None = None,
    attacker_hp: int = 0,
) -> DamageEstimate:
    """Estimate a single hit's damage range.

    Returns a zero range for status moves and immunities, so callers can treat
    "deals no damage" uniformly rather than special-casing each reason.

    `weather` is Showdown's id (`sunnyday`, `raindance`, `sandstorm`,
    `snowscape`). An unknown value is ignored rather than guessed at, so a new
    weather costs accuracy but never correctness.

    `base_power` overrides the move's static value, for the eleven moves whose
    power the engine computes per hit. See `mechanics.base_power`.

    The two item arguments are Showdown ids, and each is applied where the
    engine applies it: a type-boosting item to base power, Light Ball to the
    attacking stat, Life Orb to the final damage, a resist berry to what the
    defender takes. See `mechanics.items`.
    """
    # Through the dex rather than the chart: Freeze-Dry and Flying Press do
    # not follow it, and reading the chart here bypassed both.
    effectiveness = dex.effectiveness(move, defender)

    if not move.is_damaging or effectiveness == 0.0:
        return DamageEstimate(0, 0, effectiveness, defender_hp)

    # Fixed damage skips the formula but not the type chart: Night Shade is
    # Ghost and still does nothing at all to a Normal type, which the immunity
    # check above has already handled.
    fixed = fixed_damage(
        move, level=level, defender_hp=defender_hp, attacker_hp=attacker_hp
    )
    if fixed is not None:
        return DamageEstimate(fixed, fixed, effectiveness, defender_hp)

    # Sandstorm and snow raise a defensive stat rather than scaling damage, so
    # they belong to the ratio and must be applied before it, not after.
    boosted = WEATHER_DEFENCE_BOOSTS.get(weather or "")
    if boosted is not None:
        typing, category = boosted
        if typing in defender.types and move.category == category:
            defense_stat = int(defense_stat * WEATHER_DEFENCE_MULTIPLIER)

    # A primal weather negating the opposing type means the move genuinely does
    # nothing. Checked before the arithmetic so the floor of 1 further down
    # cannot turn "cannot damage" into "does 1".
    weather_multiplier = WEATHER_TYPE_MULTIPLIERS.get(weather or "", {}).get(
        move.type, 1.0
    )
    if weather_multiplier == 0.0:
        return DamageEstimate(0, 0, effectiveness, defender_hp)

    # Engine order: the level/power/ratio term, then +2, then the modifiers.
    # A type-boosting item raises base power and Light Ball raises the stat, so
    # both belong inside this term rather than after it.
    power = move.base_power if base_power is None else base_power
    power = modify(power, base_power_multiplier(attacker_item, move))
    attack_stat = modify(attack_stat, attack_multiplier(attacker_item, attacker))
    base = (2 * level // 5 + 2) * power * attack_stat // max(1, defense_stat) // 50 + 2

    # Spread and weather apply *before* the roll, so they are part of the
    # number that gets rolled rather than modifiers on the result.
    if doubles and is_spread_move(move):
        base = modify(base, SPREAD_MULTIPLIER)
    if weather_multiplier != 1.0:
        base = modify(base, weather_multiplier)

    steps = _effectiveness_steps(effectiveness)
    stab = move.type in attacker.types
    burned = attacker_burned and move.category == "Physical"
    final = damage_multiplier(attacker_item, effectiveness=effectiveness)
    final *= defender_multiplier(defender_item, move, effectiveness=effectiveness)

    def rolled(percent: int) -> int:
        """One end of the range, following the engine step for step.

        The roll lands here -- between the base term and STAB -- rather than at
        the end. Applying it last and rounding once put our minimum a point
        above the engine's real damage often enough to dominate the residual.
        """
        damage = int(int(base * percent) / 100)
        if stab:
            damage = modify(damage, STAB_MULTIPLIER)
        # The chart is applied as doublings and truncated halvings, not as a
        # single multiply: 0.25x is two separate `trunc(damage / 2)` steps.
        for _ in range(steps):
            damage *= 2
        for _ in range(-steps):
            damage = int(damage / 2)
        if burned:
            damage = modify(damage, BURN_MULTIPLIER)
        if final != 1.0:
            damage = modify(damage, final)
        return max(1, damage)

    return DamageEstimate(
        minimum=rolled(MIN_ROLL_PERCENT),
        maximum=rolled(MAX_ROLL_PERCENT),
        effectiveness=effectiveness,
        defender_hp=defender_hp,
    )
