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
    value = offensive_boost_value(stage_multiplier(0, stages), damage_fraction, tenure)
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

    def test_the_decision_does_not_depend_on_how_hard_we_hit(self):
        """The `f` cancels. This is the entire point of the change.

        The old flat price made setup a question of whether our attack was
        weak; the trade it actually represents has no `f` in it.
        """
        for damage in (0.05, 0.2, 0.5, 0.9):
            assert not prefers_setup(2, damage, tenure=1.9)
            assert prefers_setup(2, damage, tenure=2.1)

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
