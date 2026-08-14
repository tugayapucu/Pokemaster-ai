"""The statistics behind a claim like 'A beats B'."""

import pytest

from champions_ai.evaluation import MatchResult, wilson_interval


def _result(**overrides) -> MatchResult:
    defaults = dict(
        agent_a="a",
        agent_b="b",
        battles=100,
        wins_a=50,
        wins_b=50,
        draws=0,
        total_turns=1000,
        seed=0,
        recorded_at="2026-08-11T00:00:00+00:00",
    )
    return MatchResult(**{**defaults, **overrides})


def test_interval_brackets_the_observed_rate():
    low, high = wilson_interval(50, 100)
    assert low < 0.5 < high


def test_interval_narrows_as_battles_increase():
    """More evidence should mean a tighter claim."""
    small = wilson_interval(10, 20)
    large = wilson_interval(500, 1000)
    assert (large[1] - large[0]) < (small[1] - small[0])


def test_impossible_counts_are_rejected_clearly():
    """Otherwise this surfaces as a math domain error deep inside a sqrt."""
    with pytest.raises(ValueError, match="impossible"):
        wilson_interval(50, 20)
    with pytest.raises(ValueError, match="non-negative"):
        wilson_interval(-1, 10)


def test_interval_stays_within_zero_and_one_at_the_extremes():
    """The normal approximation goes outside [0,1] here; Wilson is chosen to avoid that."""
    assert wilson_interval(0, 10) == pytest.approx((0.0, wilson_interval(0, 10)[1]))
    low, high = wilson_interval(10, 10)
    assert 0.0 <= low <= 1.0 and high == pytest.approx(1.0)


def test_a_perfect_record_still_admits_uncertainty():
    """10 wins from 10 is not proof of a 100% win rate."""
    low, _ = wilson_interval(10, 10)
    assert low < 1.0


def test_no_trials_means_no_information():
    assert wilson_interval(0, 0) == (0.0, 1.0)


def test_even_split_is_not_significant():
    assert not _result(wins_a=50, wins_b=50).is_significant


def test_small_lead_over_few_battles_is_not_significant():
    """6-4 is not evidence, and the harness must not pretend it is."""
    assert not _result(battles=10, wins_a=6, wins_b=4).is_significant


def test_large_lead_over_many_battles_is_significant():
    assert _result(battles=400, wins_a=280, wins_b=120).is_significant


def test_losing_significantly_also_counts_as_significant():
    """The interval excluding 0.5 from below is just as informative."""
    result = _result(battles=400, wins_a=120, wins_b=280)
    assert result.is_significant
    assert result.confidence_interval_a[1] < 0.5


def test_draws_count_against_the_win_rate():
    result = _result(battles=100, wins_a=40, wins_b=40, draws=20)
    assert result.win_rate_a == 0.4


def test_summary_states_the_evidence_not_just_the_score():
    summary = _result(battles=400, wins_a=280, wins_b=120).summary()
    assert "70.0%" in summary
    assert "95% CI" in summary
    assert "significant" in summary


def test_summary_flags_an_inconclusive_run():
    assert "not significant" in _result(battles=10, wins_a=6, wins_b=4).summary()
