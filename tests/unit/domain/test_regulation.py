import pytest

from champions_ai.domain import REGULATION_M_B


def test_regulation_m_b_matches_confirmed_showdown_format():
    assert REGULATION_M_B.format_id == "gen9championsvgc2026regmb"
    assert REGULATION_M_B.game_type == "doubles"
    assert REGULATION_M_B.min_team_size == 6
    assert REGULATION_M_B.picked_team_size == 4
    assert REGULATION_M_B.max_stat_points_per_stat == 32
    assert REGULATION_M_B.max_total_stat_points == 66


def test_regulation_is_frozen():
    with pytest.raises(Exception):
        REGULATION_M_B.level = 100
