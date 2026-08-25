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
from champions_ai.mechanics import abilities as ability_rules
from champions_ai.mechanics.abilities import ATE_MULTIPLIER
from champions_ai.mechanics.items import (
    attack_multiplier,
    base_power_multiplier,
    damage_multiplier,
    defender_multiplier,
    survives_a_knockout,
)
from champions_ai.mechanics.move_type import effective_type
from champions_ai.mechanics.typing import effective_types

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
    # Expected damage. Usually the midpoint of the range, but not for a
    # multi-hit move: the range spans the fewest and most landings, while a
    # 2-5 hit move averages 3.1 of them rather than 3.5, because the engine
    # samples 35/35/15/15 rather than uniformly.
    expected: float | None = None

    @property
    def average(self) -> float:
        if self.expected is not None:
            return self.expected
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


# A 2-5 hit move is not uniform: the engine samples 35/35/15/15 for 2/3/4/5,
# which averages 3.1. Every other count in this dex is fixed.
TWO_TO_FIVE = (2, 5)
TWO_TO_FIVE_EXPECTED = 3.1

# The crit stages, as chances. `critRatio` 1 is the ordinary 1 in 24.
CRIT_CHANCES = {1: 1 / 24, 2: 1 / 8, 3: 1 / 2, 4: 1.0}
CRIT_MULTIPLIER = 1.5


def expected_hits(move: MoveInfo) -> float:
    """How many times this move is expected to land, counting accuracy.

    One for almost everything. Fourteen moves here hit repeatedly, and
    predicting a single hit understated Icicle Spear and Bullet Seed
    threefold.
    """
    count = move.multihit
    if count is None:
        return 1.0
    if isinstance(count, tuple):
        hits = (
            TWO_TO_FIVE_EXPECTED
            if count == TWO_TO_FIVE
            else (count[0] + count[1]) / 2
        )
    else:
        hits = float(count)
    if move.multiaccuracy and move.accuracy is not None:
        # Triple Axel and Population Bomb roll for each hit, so the run stops
        # at the first miss: the expected length is a geometric sum, not the
        # full count.
        chance = move.accuracy / 100
        return sum(chance ** step for step in range(1, int(hits) + 1))
    return hits


def _splits_hits(move: MoveInfo, doubles: bool, opponents: int) -> bool:
    """Whether this move spreads its hits instead of stacking them.

    Dragon Darts fires one of its two darts at *each* opponent in doubles, so
    reading it as two hits on one target doubled it -- which showed up as
    knockouts the model promised and the engine did not deliver.
    """
    return bool(move.smart_target) and doubles and opponents > 1


def hit_range(move: MoveInfo) -> tuple[int, int]:
    """Fewest and most times this move can land.

    The ends of the damage range use these rather than the expected count, or
    a "guaranteed knockout" would be claimed on a run of hits the move is not
    guaranteed to get: Icicle Spear promises two and can manage five.
    """
    count = move.multihit
    if count is None:
        return 1, 1
    if isinstance(count, tuple):
        return count[0], count[1]
    return count, count


def critical_chance(move: MoveInfo) -> float:
    """Probability this move lands a critical hit.

    Three moves here always do -- Frost Breath, Storm Throw, Flower Trick --
    and the calibration excluded them as "crits" rather than predicting them
    as the certainties they are.
    """
    if move.always_crits:
        return 1.0
    return CRIT_CHANCES.get(move.crit_ratio or 1, 1.0)


# One-hit knockout moves. The engine ignores every accuracy modifier for
# these and uses a flat 30, dropping to 20 for Sheer Cold in the hands of a
# non-Ice user, plus the level difference -- which is always zero here.
OHKO_ACCURACY = 30
OHKO_ACCURACY_WITHOUT_TYPE = 20


def ohko_chance(
    move: MoveInfo, *, attacker: SpeciesInfo, defender: SpeciesInfo
) -> float | None:
    """Probability a one-hit knockout move connects, or None if it is not one.

    `ohko` is `True` for most of them and the *name of a type* for Sheer Cold,
    which that type is outright immune to and which a user of that type lands
    more often.
    """
    if not move.ohko:
        return None
    named = move.ohko if isinstance(move.ohko, str) else None
    if named is not None and named in defender.types:
        return 0.0
    if named is not None and named not in attacker.types:
        return OHKO_ACCURACY_WITHOUT_TYPE / 100
    return OHKO_ACCURACY / 100


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
    if move.ohko:
        # The whole bar, however much of it is left.
        return defender_hp
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
    terrain: str | None = None,
    opponents: int = 1,
    defender_at_full_hp: bool = False,
    defender_ability: str | None = None,
    attacker_volatiles: tuple[str, ...] = (),
    defender_volatiles: tuple[str, ...] = (),
    attacker_ability: str | None = None,
    attacker_hp_fraction: float = 1.0,
    attacker_status: str | None = None,
    defender_status: str | None = None,
    defender_types: tuple[str, ...] | None = None,
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
    # Four moves decide their own type when they are used, so the chart has to
    # be read on the row the move will *actually* have. Weather Ball in sun is
    # a Fire move, which is super effective against a Grass type the chart
    # would otherwise have called neutral.
    actual_type = effective_type(
        move, attacker=attacker, weather=weather, terrain=terrain
    )
    # An -ate ability rewrites the move's type outright, which changes both
    # the chart row and whether STAB applies.
    rewritten = ability_rules.rewritten_type(attacker_ability, move)
    if rewritten is not None:
        actual_type = rewritten
    # Typing is not fixed for the battle either: a Roosting Pokemon has no
    # Flying type this turn, which is why Earthquake reaches an Altaria and
    # Head Smash into one does half what the chart says.
    attacker_types = effective_types(attacker.types, attacker_volatiles)
    # An explicit override answers "what if they were this type instead",
    # which is the only way to price Soak, Trick-or-Treat and the rest: what
    # those moves are worth *is* the difference between two of these calls.
    if defender_types is None:
        defender_types = effective_types(defender.types, defender_volatiles)
    # Through the dex rather than the chart: Freeze-Dry and Flying Press do
    # not follow it, and reading the chart here bypassed both.
    effectiveness = dex.effectiveness(
        move, defender, move_type=actual_type, defender_types=defender_types
    )

    if not move.is_damaging or effectiveness == 0.0:
        return DamageEstimate(0, 0, effectiveness, defender_hp)

    # An ability can make a hit not land at all -- Levitate against Ground,
    # Flash Fire against Fire. That is an immunity, not a reduction, so it is
    # settled here rather than folded into a multiplier further down.
    absorbed = ability_rules.taken_multiplier(
        defender_ability, move, effectiveness=effectiveness,
        at_full_hp=defender_at_full_hp,
    )
    if absorbed == 0.0:
        return DamageEstimate(0, 0, 0.0, defender_hp)

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
        if typing in defender_types and move.category == category:
            defense_stat = int(defense_stat * WEATHER_DEFENCE_MULTIPLIER)

    # A primal weather negating the opposing type means the move genuinely does
    # nothing. Checked before the arithmetic so the floor of 1 further down
    # cannot turn "cannot damage" into "does 1".
    weather_multiplier = WEATHER_TYPE_MULTIPLIERS.get(weather or "", {}).get(
        actual_type, 1.0
    )
    if weather_multiplier == 0.0:
        return DamageEstimate(0, 0, effectiveness, defender_hp)

    # Engine order: the level/power/ratio term, then +2, then the modifiers.
    # A type-boosting item raises base power and Light Ball raises the stat, so
    # both belong inside this term rather than after it.
    power = move.base_power if base_power is None else base_power
    power = modify(power, base_power_multiplier(attacker_item, move))
    power = modify(power, ability_rules.base_power_multiplier(
        attacker_ability, move, base_power=power, weather=weather
    ))
    if rewritten is not None:
        # The -ate abilities pay a small bonus for the rewrite itself, and the
        # engine pays it through `onBasePower` -- so it has to land here, while
        # `power` still feeds the base term below.
        power = modify(power, ATE_MULTIPLIER)
    attack_stat = modify(attack_stat, attack_multiplier(attacker_item, attacker))
    attack_stat = modify(attack_stat, ability_rules.attack_multiplier(
        attacker_ability, move, hp_fraction=attacker_hp_fraction,
        status=attacker_status, weather=weather,
    ))
    defense_stat = modify(defense_stat, ability_rules.defence_multiplier(
        defender_ability, move, status=defender_status
    ))
    base = (2 * level // 5 + 2) * power * attack_stat // max(1, defense_stat) // 50 + 2

    # Spread and weather apply *before* the roll, so they are part of the
    # number that gets rolled rather than modifiers on the result.
    if doubles and is_spread_move(move):
        base = modify(base, SPREAD_MULTIPLIER)

    # Parental Bond adds a second, weaker strike rather than scaling the first.
    # Both land on the same target and the harness accumulates them into one
    # sample, so it belongs here as a multiplier on the pair.
    base = modify(
        base,
        ability_rules.extra_hit_multiplier(
            attacker_ability, move, is_spread=doubles and is_spread_move(move)
        ),
    )
    if weather_multiplier != 1.0:
        base = modify(base, weather_multiplier)

    steps = _effectiveness_steps(effectiveness)
    # STAB follows the type the move ends up with, not the one it was written
    # with: a Morpeko-Hangry gets it on a Dark Aura Wheel.
    has_stab = actual_type in attacker_types
    stab_bonus = ability_rules.stab_multiplier(attacker_ability, has_stab=has_stab)
    burned = attacker_burned and move.category == "Physical"
    final = damage_multiplier(attacker_item, effectiveness=effectiveness)
    final *= defender_multiplier(defender_item, move, effectiveness=effectiveness)
    final *= absorbed

    # Three moves here always crit, and a crit is a flat 1.5x on top. Modelled
    # as the certainty it is rather than excluded as "a crit": Frost Breath,
    # Storm Throw and Flower Trick have no non-crit case to predict.
    crit = CRIT_MULTIPLIER if move.always_crits else 1.0

    def rolled(percent: int) -> int:
        """One end of the range, following the engine step for step.

        The roll lands here -- between the base term and STAB -- rather than at
        the end. Applying it last and rounding once put our minimum a point
        above the engine's real damage often enough to dominate the residual.
        """
        damage = int(int(base * percent) / 100)
        if has_stab:
            damage = modify(damage, stab_bonus)
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

    low_hits, high_hits = hit_range(move)
    # Skill Link removes the roll, so it has to reach the *bounds* and not only
    # the expected count. Setting the average alone left the range spanning two
    # to five hits for a Pokemon that always lands five -- a claim wide enough
    # to be nearly unfalsifiable, which is the opposite of what a certainty
    # should do to a prediction.
    forced_hits = ability_rules.linked_hits(attacker_ability, move)
    if forced_hits is not None:
        low_hits = high_hits = forced_hits
    if _splits_hits(move, doubles, opponents):
        low_hits = high_hits = 1
    low = rolled(MIN_ROLL_PERCENT)
    high = rolled(MAX_ROLL_PERCENT)
    average_hit = (low + high) / 2

    # A critical hit is a flat 1.5x, and the fourteen high-crit moves here land
    # one far more often than the ordinary 1 in 24. It belongs in the
    # *expected* damage but not in the range: the range is the ordinary roll,
    # and a crit is a different calculation rather than a lucky end of this
    # one. Already-certain crits are folded into `crit` above and must not be
    # counted twice.
    crit_lift = 1.0 if move.always_crits else 1 + (CRIT_MULTIPLIER - 1) * critical_chance(move)

    if _splits_hits(move, doubles, opponents):
        hits = 1.0
    elif forced_hits is not None:
        hits = float(forced_hits)
    else:
        hits = expected_hits(move)
    minimum = max(1, int(low * low_hits * crit))
    maximum = max(1, int(high * high_hits * crit))
    expected = average_hit * hits * crit * crit_lift

    # A Focus Sash or Sturdy leaves the holder on 1 HP rather than fainting,
    # but only from full health. Capping here is what stops the model
    # *promising* a knockout it will not get: measured against the engine, a
    # "guaranteed" knockout lands 98.1% of the time and a sash is the single
    # largest reason for the rest.
    if survives_a_knockout(defender_item, defender_ability, at_full_hp=defender_at_full_hp):
        survivable = max(1, defender_hp - 1)
        minimum = min(minimum, survivable)
        maximum = min(maximum, survivable)
        expected = min(expected, float(survivable))

    return DamageEstimate(
        minimum=minimum,
        maximum=maximum,
        effectiveness=effectiveness,
        defender_hp=defender_hp,
        expected=expected,
    )
