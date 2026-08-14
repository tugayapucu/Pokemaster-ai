import pytest
from pydantic import ValidationError

from champions_ai.domain import REGULATION_M_B, Regulation, StatSpread


def test_default_is_all_zero():
    spread = StatSpread()
    assert spread.hp == 0
    assert spread.total == 0


def test_totals_and_values_are_exposed():
    spread = StatSpread(hp=24, special_attack=24, speed=18)
    assert spread.total == 66
    assert sum(spread.values) == 66


def test_rejects_negative_points_regardless_of_regulation():
    with pytest.raises(ValidationError):
        StatSpread(hp=-1)


def test_spread_within_reg_m_b_limits_has_no_problems():
    assert REGULATION_M_B.stat_spread_problems(StatSpread(hp=32, attack=32, speed=2)) == []


def test_regulation_flags_a_stat_over_its_per_stat_cap():
    problems = REGULATION_M_B.stat_spread_problems(StatSpread(hp=33))
    assert len(problems) == 1
    assert "hp" in problems[0]


def test_regulation_flags_a_spread_over_its_total_cap():
    problems = REGULATION_M_B.stat_spread_problems(StatSpread(hp=32, attack=32, defense=32))
    assert any("total" in problem for problem in problems)


def test_all_problems_are_reported_together_not_just_the_first():
    problems = REGULATION_M_B.stat_spread_problems(StatSpread(hp=40, attack=40))
    assert len(problems) == 3  # two per-stat violations plus the total


def test_limits_follow_the_regulation_rather_than_being_hardcoded():
    """A future regulation raising the caps must not require editing StatSpread."""
    generous = Regulation(
        format_id="hypothetical",
        name="Hypothetical Future Reg",
        game_type="doubles",
        level=50,
        min_team_size=6,
        picked_team_size=4,
        max_stat_points_per_stat=64,
        max_total_stat_points=132,
    )
    spread = StatSpread(hp=64, attack=64)
    assert generous.stat_spread_problems(spread) == []
    assert REGULATION_M_B.stat_spread_problems(spread)
