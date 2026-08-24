"""Two slots aimed at the same Pokemon are not independent.

The joint score is a sum of independently scored slots, which cannot see that
two attacks land on one target. That is wrong in both directions: two
guaranteed knockouts each collected the full bonus, so the agent was rewarded
for wasting an attack; and two attacks that remove a Pokemon between them
collected nothing, because neither is a knockout alone.

Measured, this is agreement- and strength-neutral: it fires on 2.17% of joint
actions and moves neither instrument (experiment 0011). It is kept because a
Pokemon can only faint once, so claiming two knockouts of it is a double-count
whatever the measurement says.
"""

import pytest

from champions_ai.agents.heuristic import (
    GUARANTEED_KO_BONUS,
    POSSIBLE_KO_BONUS,
    ScoredAction,
    _combined_targets,
)
from champions_ai.domain import MoveAction


def _scored(target_index, damage_fraction, knockout_bonus, index=0):
    return ScoredAction(
        action=MoveAction(move_index=index),
        score=0.0,
        target_index=target_index,
        damage_fraction=damage_fraction,
        knockout_bonus=knockout_bonus,
    )


def test_two_slots_on_different_targets_are_left_alone():
    scored = [
        _scored(0, 1.0, GUARANTEED_KO_BONUS),
        _scored(1, 1.0, GUARANTEED_KO_BONUS, index=1),
    ]
    assert _combined_targets(scored) == 0.0


def test_two_guaranteed_knockouts_on_one_target_only_count_once():
    """A Pokemon faints once. Paying twice rewarded overkill."""
    scored = [
        _scored(0, 1.0, GUARANTEED_KO_BONUS),
        _scored(0, 1.0, GUARANTEED_KO_BONUS, index=1),
    ]
    assert _combined_targets(scored) == pytest.approx(-GUARANTEED_KO_BONUS)


def test_two_half_knockouts_that_combine_earn_the_bonus():
    """Neither is a knockout alone, and together they remove the Pokemon."""
    scored = [_scored(0, 0.55, 0.0), _scored(0, 0.55, 0.0, index=1)]
    assert _combined_targets(scored) == pytest.approx(GUARANTEED_KO_BONUS)


def test_two_attacks_that_do_not_combine_into_a_knockout_earn_nothing():
    scored = [_scored(0, 0.3, 0.0), _scored(0, 0.3, 0.0, index=1)]
    assert _combined_targets(scored) == 0.0


def test_a_high_roll_claim_survives_when_the_pair_falls_short():
    """One slot might knock out on a good roll; the pair still cannot promise
    it, so the smaller claim is what stands."""
    scored = [_scored(0, 0.4, POSSIBLE_KO_BONUS), _scored(0, 0.2, 0.0, index=1)]
    assert _combined_targets(scored) == 0.0


def test_a_guaranteed_knockout_plus_chip_damage_keeps_one_bonus():
    scored = [_scored(0, 1.0, GUARANTEED_KO_BONUS), _scored(0, 0.1, 0.0, index=1)]
    assert _combined_targets(scored) == 0.0


def test_actions_with_no_target_are_ignored():
    """Switches and self-targeting status moves carry no target index."""
    scored = [_scored(None, 0.0, 0.0), _scored(None, 0.0, 0.0, index=1)]
    assert _combined_targets(scored) == 0.0
