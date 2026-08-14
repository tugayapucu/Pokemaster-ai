"""Champions' stat formula.

Not the mainline one. Champions drops level scaling and IVs entirely:

    HP    = base + points + 75
    other = (base + points + 20) * nature

Confirmed against `statModify` in the champions mod's `scripts.ts` and against
live engine output -- Charizard with 32 SpA points reports exactly 109+32+20 =
161, and 153 HP from 78+0+75.

This matters beyond tidiness: applying the mainline formula would misestimate
every stat, and every damage figure derived from one.
"""

from champions_ai.dex import BaseStats

HP_CONSTANT = 75
STAT_CONSTANT = 20

BOOST_MULTIPLIERS = {
    -6: 2 / 8, -5: 2 / 7, -4: 2 / 6, -3: 2 / 5, -2: 2 / 4, -1: 2 / 3,
    0: 1.0,
    1: 3 / 2, 2: 4 / 2, 3: 5 / 2, 4: 6 / 2, 5: 7 / 2, 6: 8 / 2,
}

STAT_FIELDS = {
    "hp": "hp",
    "atk": "attack",
    "def": "defense",
    "spa": "special_attack",
    "spd": "special_defense",
    "spe": "speed",
}


def hp_stat(base_hp: int, points: int = 0) -> int:
    return base_hp + points + HP_CONSTANT


def other_stat(base: int, points: int = 0, *, nature: int = 0) -> int:
    """A non-HP stat. `nature` is +1 boosting, -1 hindering, 0 neutral.

    Truncates like the engine: a boosting nature is floor(stat * 110 / 100),
    not a rounded 10% -- rounding would drift by a point and quietly change
    speed ties.
    """
    stat = base + points + STAT_CONSTANT
    if nature > 0:
        return stat * 110 // 100
    if nature < 0:
        return stat * 90 // 100
    return stat


def estimate_stats(base_stats: BaseStats, points_per_stat: int = 0) -> dict[str, int]:
    """A plausible stat line for a Pokemon whose investment is unknown.

    Used for opponents, whose Stat Points are never revealed (ADR 0002). The
    assumed investment is a modelling choice, not a fact -- opponent modelling
    (Milestone 10) is where it should be replaced by something inferred.
    """
    return {
        "hp": hp_stat(base_stats.hp, points_per_stat),
        "atk": other_stat(base_stats.attack, points_per_stat),
        "def": other_stat(base_stats.defense, points_per_stat),
        "spa": other_stat(base_stats.special_attack, points_per_stat),
        "spd": other_stat(base_stats.special_defense, points_per_stat),
        "spe": other_stat(base_stats.speed, points_per_stat),
    }


def apply_boost(stat: int, stage: int) -> int:
    """Apply an in-battle stat stage, clamped to the legal -6..+6 range."""
    clamped = max(-6, min(6, stage))
    return int(stat * BOOST_MULTIPLIERS[clamped])
