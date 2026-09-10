"""The invariant: a team scouted against a copy of itself must go 1-1.

Same agent both sides, same seed, seats swapped. If a mirror does not split,
the harness is measuring something other than the teams -- a seat advantage, an
unshared seed, or an agent carrying state between battles -- and every win rate
it reports is that thing plus the teams, with no way to tell them apart.

This is the same invariant `evaluate` rests on, pointed the other way: there it
proves the *teams* are controlled, here it proves the *policy* is.
"""

import pytest

from champions_ai.agents import HeuristicAgent
from champions_ai.data import TeamPool
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_B
from champions_ai.env import BattleEnv
from champions_ai.evaluation.team_strength import scout_team

pytestmark = pytest.mark.integration


def test_a_team_against_copies_of_itself_splits_every_matchup(bridge, mega_team):
    dex = Dex.load(bridge, mod=REGULATION_M_B.mod)
    env = BattleEnv(REGULATION_M_B, bridge=bridge)
    agent = HeuristicAgent(dex, name="both sides")
    mirror = TeamPool(teams=(mega_team, mega_team, mega_team))

    report = scout_team(env, agent, mega_team, mirror, opponents=3, seed=1)

    assert report.battles == 6
    assert report.opponents == 3
    assert report.even() == 3, (
        "a mirror did not split: the harness is measuring a seat advantage or a "
        "stateful agent, not the teams"
    )
    assert report.win_rate == 0.5
