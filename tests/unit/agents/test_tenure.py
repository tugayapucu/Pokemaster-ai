"""Tests for tenure-priced stat boosts.

These check the *decision* the pricing produces -- would the agent rather set
up or attack -- rather than the constants that produce it. Asserting the
constants would pass with the formula inverted, which is the failure mode this
project has already shipped twice.
"""

import pytest

from champions_ai.agents.tenure import (
    TENURE_CEILING,
    TENURE_FLOOR,
    TENURE_UNTHREATENED,
    expected_tenure,
    offensive_boost_value,
    stage_factor,
    stage_multiplier,
)


def prefers_setup(stages: int, damage_fraction: float, tenure: float) -> bool:
    """Whether the boost outscores simply attacking, in the agent's own terms."""
    return prefers_setup_against(stages, damage_fraction, tenure, target=1.0)


def prefers_setup_against(
    stages: int, damage_fraction: float, tenure: float, target: float
) -> bool:
    value = offensive_boost_value(
        stage_multiplier(0, stages), damage_fraction, tenure, target_fraction=target
    )
    return value > damage_fraction


class TestStageMultiplier:
    def test_matches_the_engine_ladder(self):
        assert stage_factor(0) == 1.0
        assert stage_factor(1) == 1.5
        assert stage_factor(2) == 2.0
        assert stage_factor(6) == 4.0
        assert stage_factor(-1) == pytest.approx(2 / 3)
        assert stage_factor(-2) == 0.5

    def test_a_boost_is_worth_less_the_more_you_have(self):
        """A fourth Swords Dance buys a third, not a double."""
        first = stage_multiplier(0, 2)
        fourth = stage_multiplier(4, 6)
        assert first == 2.0
        assert fourth == pytest.approx(4 / 3)
        assert fourth < first

    def test_maxed_out_buys_nothing(self):
        assert stage_multiplier(6, 6) == 1.0
        assert offensive_boost_value(stage_multiplier(6, 6), 0.4, 5.0) == 0.0


class TestBreakEven:
    """`T > m / (m - 1)` is the whole claim. These pin it down."""

    def test_plus_two_pays_off_from_two_turns(self):
        assert not prefers_setup(2, 0.35, tenure=1.9)
        assert prefers_setup(2, 0.35, tenure=2.1)

    def test_plus_one_needs_a_turn_longer_than_plus_two(self):
        assert not prefers_setup(1, 0.35, tenure=2.9)
        assert prefers_setup(1, 0.35, tenure=3.1)

    def test_the_decision_ignores_how_hard_we_hit_while_the_target_survives(self):
        """The `f` cancels -- but only up to the knockout threshold.

        The flat price made setup a question of whether our attack was weak.
        The trade has no `f` in it *while the boosted hit still leaves the
        target standing*, which is the range this covers. Past that the
        cancellation genuinely breaks, and the next test is that case: an
        earlier version of this file asserted independence at every `f` and
        was wrong to.
        """
        for damage in (0.05, 0.2, 0.4):
            assert not prefers_setup(2, damage, tenure=1.9)
            assert prefers_setup(2, damage, tenure=2.1)

    def test_boosting_an_attack_that_already_kills_buys_nothing(self):
        """Damage past a knockout is wasted, and a boost only makes damage.

        Pricing this as `(m - 1) * f` had the agent decline a guaranteed
        knockout on 14.5% of the turns one was available, at a cost of 4.6
        points of win rate.
        """
        assert offensive_boost_value(2.0, 0.6, tenure=5.0, target_fraction=0.5) == 0.0
        assert not prefers_setup_against(2, 0.9, tenure=5.0, target=1.0)

    def test_a_partial_overkill_is_worth_only_the_part_that_lands(self):
        """f = 0.6 into a full bar: doubling would deal 1.2, of which 0.4 is
        real and 0.2 is spilled on the floor."""
        value = offensive_boost_value(2.0, 0.6, tenure=2.0, target_fraction=1.0)
        assert value == pytest.approx(0.4)

    def test_a_boost_on_your_last_turn_is_worthless(self):
        assert offensive_boost_value(2.0, 0.4, tenure=1.0) == 0.0
        assert not prefers_setup(2, 0.4, tenure=1.0)

    def test_value_grows_with_the_turns_left(self):
        values = [offensive_boost_value(2.0, 0.4, t) for t in (1, 2, 3, 4, 5)]
        assert values == sorted(values)
        assert values[0] < values[-1]


class TestExpectedTenure:
    def test_more_health_buys_more_turns(self):
        assert expected_tenure(1.0, 0.25) > expected_tenure(0.3, 0.25)

    def test_a_bigger_threat_costs_turns(self):
        assert expected_tenure(1.0, 0.5) < expected_tenure(1.0, 0.2)

    def test_an_unthreatened_pokemon_is_not_immortal(self):
        """No threat means the ratio is undefined, not infinite."""
        assert expected_tenure(1.0, 0.0) == TENURE_UNTHREATENED
        assert expected_tenure(1.0, 0.0) < TENURE_CEILING

    def test_clamped_at_both_ends(self):
        assert expected_tenure(1.0, 0.0001) <= TENURE_CEILING
        assert expected_tenure(0.0, 1.0) >= TENURE_FLOOR

    def test_something_about_to_die_does_not_set_up(self):
        """A Pokemon at 10% facing a hit that takes 60% has one turn."""
        tenure = expected_tenure(0.1, 0.6)
        assert not prefers_setup(2, 0.35, tenure)

    def test_something_safe_does_set_up(self):
        """Full health against a chip hit has time to spare."""
        tenure = expected_tenure(1.0, 0.15)
        assert prefers_setup(2, 0.35, tenure)
