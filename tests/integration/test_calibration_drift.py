"""A canary for the score scale the cost bands are calibrated against.

0042 turned score gaps into win-rate points using bands measured by rollout in
0041. That calibration is tied to *this* scorer: it says a gap of 100 is worth
about 5 points because that is what a gap of 100 was worth when it was
measured. Change a scoring constant and the same decision produces a different
gap, and the number on screen quietly becomes wrong while still looking
authoritative.

Nothing else notices. Every unit test on the scorer asserts a judgement -- that
Protect beats attacking here, that a Mega scores above its base forme -- and a
change that scales every score by 1.5 would leave all of them passing while
turning "about 5 points behind" into a lie.

So this pins the *scale* rather than any judgement, and it does it on a
distribution rather than on individual values so that an unrelated tweak to one
move does not trip it. **A failure here is not a bug. It means the scorer moved
and `experiments/0041` has to be re-run before the bands in
`recommendation/calibration.py` can be trusted again.**

Measured on 2026-09-04 over six fixed seeds of `mega_team` against itself:
median 25.4, mean 38.8, p75 46.8. The same measurement over thirty battles from
the real evaluation pool gave a median of 24.0, so the fixture is
representative of what a player would actually see.
"""

import statistics

import pytest

from champions_ai.agents import HeuristicAgent
from champions_ai.dex import Dex
from champions_ai.env.battle_env import Decision
from champions_ai.recommendation import Recommender

pytestmark = pytest.mark.integration

# Wide enough that a change to one move's price does not trip it, narrow enough
# that a change to the *scale* does. The recorded median is 25.4 and the fixture
# is deterministic, so the only thing that moves these is the scorer.
#
# Sensitivity, measured by scaling every score and re-running rather than
# guessed: x2.0 and x0.5 trip it, x1.5 (median 38.0) and x0.7 (median 17.8)
# trip it, x1.25 (median 31.8) does not. A quarter is about the point where a
# uniform scale change stops moving a meaningful share of decisions across the
# 60-point band boundary, so that is where the line sits.
MEDIAN_RANGE = (18.0, 34.0)
MEAN_RANGE = (28.0, 52.0)
SEEDS = tuple(f"sodium,{0xCA1B0000 + i:032x}" for i in range(6))


@pytest.fixture(scope="module")
def dex(bridge) -> Dex:
    return Dex.load(bridge)


@pytest.fixture(scope="module")
def gaps(env, dex, mega_teams) -> list[float]:
    """Top-vs-runner-up score gaps across a fixed set of battles."""
    recommender = Recommender(dex)
    collected: list[float] = []
    for seed in SEEDS:
        result = env.reset(mega_teams, seed=seed)
        agents = (HeuristicAgent(dex), HeuristicAgent(dex))
        while not result.terminal:
            waiting = env.awaiting()
            if not waiting:
                break
            choices = {}
            for player in waiting:
                if env.decision(player) is Decision.TEAM_PREVIEW:
                    choices[player] = agents[player].select_team_preview(
                        env.team_preview(player), env.regulation.picked_team_size
                    )
                    continue
                observation = env.observation(player)
                legal = env.legal_actions(player)
                choices[player] = agents[player].select_action(observation, legal)
                if player == 0 and len(legal) > 1:
                    advice = recommender.recommend(observation, legal)
                    if len(advice.recommendations) > 1:
                        collected.append(
                            advice.best.score - advice.recommendations[1].score
                        )
            result = env.step(choices)
    return collected


def test_enough_decisions_to_say_anything(gaps):
    assert len(gaps) > 40, "the fixture stopped producing decisions; the canary is blind"


def test_the_score_scale_has_not_moved(gaps):
    """If this fails, re-run experiments/0041 before trusting the cost bands."""
    median = statistics.median(gaps)
    mean = statistics.fmean(gaps)

    assert MEDIAN_RANGE[0] <= median <= MEDIAN_RANGE[1], (
        f"median top-vs-runner-up score gap is {median:.1f}, outside {MEDIAN_RANGE}. "
        "The scorer's scale has changed, so the win-rate bands in "
        "recommendation/calibration.py no longer describe it. Re-run "
        "experiments/0041-delayed-payoff and re-fit them."
    )
    assert MEAN_RANGE[0] <= mean <= MEAN_RANGE[1], (
        f"mean top-vs-runner-up score gap is {mean:.1f}, outside {MEAN_RANGE}. "
        "See the median assertion above; the calibration needs re-measuring."
    )


def test_most_decisions_land_in_the_close_band(gaps):
    """The shape the bands assume, not just their scale.

    Most turns the top two options are inside the band where rollouts find no
    difference -- 70% over the real evaluation pool. If that collapsed, the
    bands would still have the right scale while describing a different game.
    """
    close = sum(1 for gap in gaps if gap < 60.0) / len(gaps)
    assert 0.45 <= close <= 0.95, (
        f"{close:.0%} of decisions have the runner-up inside the close band. "
        "The distribution has changed shape; the cost bands describe a "
        "different game than the one being played."
    )
