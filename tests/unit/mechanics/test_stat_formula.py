"""Champions' stat formula, checked against values the live engine produced.

The expected numbers below are not derived from the formula -- they were read
out of a real battle request for the Charizard/Garchomp test team. If the
formula is wrong, these fail.
"""

from champions_ai.dex import BaseStats
from champions_ai.mechanics import apply_boost, estimate_stats, hp_stat, other_stat

# Charizard: 78/84/78/109/85/100, Timid (+Spe -Atk), 32 SpA / 32 Spe.
CHARIZARD = BaseStats(
    hp=78, attack=84, defense=78, special_attack=109, special_defense=85, speed=100
)


def test_hp_matches_the_engine():
    """Engine reported 153/153 for an uninvested Charizard."""
    assert hp_stat(CHARIZARD.hp) == 153


def test_invested_special_attack_matches_the_engine():
    """Engine reported spa 161 with 32 points: 109 + 32 + 20."""
    assert other_stat(CHARIZARD.special_attack, 32) == 161


def test_boosting_nature_matches_the_engine():
    """Engine reported spe 167: (100 + 32 + 20) * 1.1, truncated."""
    assert other_stat(CHARIZARD.speed, 32, nature=1) == 167


def test_uninvested_stats_match_the_engine():
    """Engine reported def 98 and spd 105 with no investment."""
    assert other_stat(CHARIZARD.defense) == 98
    assert other_stat(CHARIZARD.special_defense) == 105


def test_hindering_nature_truncates_downward():
    assert other_stat(CHARIZARD.attack, 0, nature=-1) == (84 + 20) * 90 // 100


def test_there_is_no_level_scaling():
    """Champions drops the mainline level term; the same points give the same stat."""
    assert other_stat(100, 0) == 120


def test_points_add_one_for_one():
    assert other_stat(100, 32) - other_stat(100, 0) == 32
    assert hp_stat(100, 32) - hp_stat(100, 0) == 32


def test_estimate_stats_fills_a_whole_line():
    stats = estimate_stats(CHARIZARD)
    assert stats["hp"] == 153
    assert stats["spa"] == 129  # 109 + 0 + 20
    assert set(stats) == {"hp", "atk", "def", "spa", "spd", "spe"}


def test_assumed_investment_raises_every_stat():
    lean = estimate_stats(CHARIZARD, 0)
    invested = estimate_stats(CHARIZARD, 16)
    assert all(invested[key] > lean[key] for key in lean)


def test_boosts_follow_the_standard_multipliers():
    assert apply_boost(100, 0) == 100
    assert apply_boost(100, 1) == 150
    assert apply_boost(100, 2) == 200
    assert apply_boost(100, 6) == 400
    assert apply_boost(100, -1) == 66
    assert apply_boost(100, -6) == 25


def test_boosts_clamp_beyond_the_legal_range():
    assert apply_boost(100, 9) == apply_boost(100, 6)
    assert apply_boost(100, -9) == apply_boost(100, -6)
