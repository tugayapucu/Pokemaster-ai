import pytest

from champions_ai.domain import REGULATION_M_B, REGULATION_M_C

# The fields that are rules rather than identity. Named here so the claim below
# -- that these two regulations differ only in their dex -- is checked against
# every field the model has, not against a list someone remembered to update.
IDENTITY = {"format_id", "name", "mod"}


def test_regulation_m_b_matches_confirmed_showdown_format():
    assert REGULATION_M_B.format_id == "gen9championsvgc2026regmb"
    assert REGULATION_M_B.game_type == "doubles"
    assert REGULATION_M_B.min_team_size == 6
    assert REGULATION_M_B.picked_team_size == 4
    assert REGULATION_M_B.max_stat_points_per_stat == 32
    assert REGULATION_M_B.max_total_stat_points == 66


def test_regulation_m_c_matches_confirmed_showdown_format():
    assert REGULATION_M_C.format_id == "gen9championsvgc2026regmc"
    assert REGULATION_M_C.game_type == "doubles"
    assert REGULATION_M_C.min_team_size == 6
    assert REGULATION_M_C.picked_team_size == 4
    assert REGULATION_M_C.max_stat_points_per_stat == 32
    assert REGULATION_M_C.max_total_stat_points == 66


def test_the_two_regulations_differ_only_in_which_dex_they_use():
    """The load-bearing claim behind `mod`.

    Their rule tables are identical, read off the engine. What separates them
    is the dex the mod carries -- M-C has 35 species and 18 items M-B does
    not, and takes none away. If a future regulation makes this fail, that
    regulation genuinely changed a rule and the code assuming otherwise
    wants finding.
    """
    a = REGULATION_M_C.model_dump()
    b = REGULATION_M_B.model_dump()
    assert {k: v for k, v in a.items() if k not in IDENTITY} == {
        k: v for k, v in b.items() if k not in IDENTITY
    }


def test_the_two_regulations_do_not_share_a_mod():
    """If they did, one dex cache would serve both and the difference between
    them -- the only difference there is -- would vanish silently."""
    assert REGULATION_M_C.mod != REGULATION_M_B.mod


def test_regulation_is_frozen():
    with pytest.raises(Exception):
        REGULATION_M_B.level = 100


def test_both_regulations_enable_mega_but_not_terastallization():
    for regulation in (REGULATION_M_C, REGULATION_M_B):
        assert regulation.allows("mega")
        assert not regulation.allows("terastallize")
