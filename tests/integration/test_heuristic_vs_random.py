"""The first result about play quality rather than plumbing.

Measured, not asserted loosely: the heuristic must beat Random by a margin
whose confidence interval clears a coin flip, and must do so across most
matchups rather than by exploiting a few favourable team pairings.
"""

import pytest

from champions_ai.agents import HeuristicAgent, RandomAgent
from champions_ai.dex import Dex
from champions_ai.evaluation import evaluate

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def dex(bridge) -> Dex:
    return Dex.load(bridge)


@pytest.fixture(scope="module")
def head_to_head(env, dex, team_pool):
    return evaluate(
        env,
        HeuristicAgent(dex, name="heuristic-v1"),
        RandomAgent(seed=7, name="random"),
        team_pool,
        battles=60,
        seed=2026,
    )


def test_the_dex_loads_the_champions_roster(dex):
    assert len(dex.species) > 200
    assert len(dex.moves) > 300
    assert dex.type_chart.effectiveness("Rock", ("Fire", "Flying")) == 4.0


def test_heuristic_beats_random_by_a_significant_margin(head_to_head):
    low, _ = head_to_head.confidence_interval_a
    assert head_to_head.is_significant, head_to_head.summary()
    assert low > 0.5, head_to_head.summary()
    assert head_to_head.win_rate_a > 0.75, head_to_head.summary()


def test_the_advantage_is_not_confined_to_a_few_matchups(head_to_head):
    """Winning overall while losing most pairings means exploiting teams, not playing better."""
    assert head_to_head.matchups_won > head_to_head.matchups_played * 0.6, (
        head_to_head.summary()
    )


def test_the_heuristic_ends_battles_faster_than_random_flailing(head_to_head):
    """Efficient knockouts should shorten games; ~10 turns was the Random baseline.

    The bound was 9 while the agent scored nothing but damage. Pricing move
    effects (2026-08-18) made it press Protect, status and flinch, all of which
    lengthen a game on purpose, and it drifted to just over 9 on this pool.

    Widened rather than reverted, because the change was checked for a strength
    regression and there is none: 295-5 against Random versus the damage-only
    agent's 296-4, and 204-196 head to head over 400 battles. The assertion is
    meant to catch flailing, and the Random baseline it is measured against is
    ~10.
    """
    assert head_to_head.average_turns < 9.5


def test_the_run_reproduces(env, dex, team_pool, head_to_head):
    repeat = evaluate(
        env,
        HeuristicAgent(dex, name="heuristic-v1"),
        RandomAgent(seed=7, name="random"),
        team_pool,
        battles=60,
        seed=2026,
    )
    assert repeat.wins_a == head_to_head.wins_a
