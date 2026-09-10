"""A regulation's numbers, asked of the engine instead of transcribed.

`Regulation` states a level, team sizes and a stat-point budget. Every one of
those written by hand from `config/formats.ts` is a chance to describe a
different game than the one being played, and a *silent* one: a wrong picked
team size still validates teams, a wrong level still runs battles, and nothing
looks broken until a result is compared against reality.

So these check the constants against `bridge.format_rules`, which reads the
engine's own rule table. Adding a regulation is then mechanical rather than a
transcription exercise, and a regulation that drifts from its format fails
here.
"""

import pytest

from champions_ai.domain import REGULATION_M_B, REGULATION_M_C
from champions_ai.simulator import BridgeError

pytestmark = pytest.mark.integration

REGULATIONS = (REGULATION_M_B, REGULATION_M_C)


@pytest.mark.parametrize("regulation", REGULATIONS, ids=lambda r: r.format_id)
def test_every_stated_number_is_the_engines(bridge, regulation):
    rules = bridge.format_rules(regulation.format_id)

    assert rules["gameType"] == regulation.game_type
    assert rules["mod"] == regulation.mod
    assert rules["name"] == regulation.name
    # `adjustLevel` is what actually forces every Pokemon to 50; `defaultLevel`
    # is 100 in this format and means something else entirely, so reading the
    # wrong one would set the whole game to the wrong level.
    assert rules["adjustLevel"] == regulation.level
    assert rules["minTeamSize"] == regulation.min_team_size
    assert rules["pickedTeamSize"] == regulation.picked_team_size
    assert rules["evLimit"] == regulation.max_total_stat_points


def test_the_two_regulations_really_do_share_a_rule_table(bridge):
    """The claim `Regulation.mod` rests on: a regulation is a dex, not a rule
    change. Checked against the engine rather than against our own constants,
    which could agree with each other while both being wrong."""
    ignored = {"id", "name", "mod"}
    b = {k: v for k, v in bridge.format_rules(REGULATION_M_B.format_id).items()
         if k not in ignored}
    c = {k: v for k, v in bridge.format_rules(REGULATION_M_C.format_id).items()
         if k not in ignored}
    assert b == c


def test_a_format_this_build_does_not_have_is_an_error_not_a_blank(bridge):
    """`gen9championsvgc2026regma` existed in 0.11.11 and does not exist here.
    Returning empty rules for a missing format would let a regulation be built
    out of nothing at all."""
    with pytest.raises(BridgeError, match="no such format"):
        bridge.format_rules("gen9championsvgc2026regma")


def test_the_per_stat_cap_is_a_family_fact_not_a_rule_table_one(bridge):
    """32 per stat is hardcoded in the core team validator for any mod whose
    name starts with "champions", so it is deliberately absent from the rule
    table and stated on `Regulation` instead. This pins the reason: if it ever
    appears in the table, the constant should come from there."""
    rules = bridge.format_rules(REGULATION_M_C.format_id)
    assert "maxStatPointsPerStat" not in rules
    assert REGULATION_M_C.max_stat_points_per_stat == 32
