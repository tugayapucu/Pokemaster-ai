"""The margin's wiring into a match result.

`margin.py` is tested in isolation; this covers the join -- that outcomes carry
a margin, that a missing one degrades safely rather than reading as an even
result, and that the summary reports it.
"""

from champions_ai.evaluation.margin import BattleMargin
from champions_ai.evaluation.runner import BattleOutcome, MatchResult


def _outcome(index, won, survivors_a, survivors_b, margin=True):
    return BattleOutcome(
        index=index, seed=f"seed{index}", first_agent_played_as=0,
        winner=0 if won else 1, turns=6, matchup="a vs b",
        margin=BattleMargin(
            survivors_a=survivors_a, survivors_b=survivors_b,
            hp_a=float(survivors_a), hp_b=float(survivors_b), team_size=4,
        ) if margin else None,
    )


def _result(outcomes):
    return MatchResult(
        agent_a="a", agent_b="b", battles=len(outcomes),
        wins_a=sum(1 for o in outcomes if o.first_agent_won),
        wins_b=sum(1 for o in outcomes if not o.first_agent_won),
        draws=0, total_turns=6 * len(outcomes), seed=1, recorded_at="now",
        outcomes=tuple(outcomes),
    )


def test_an_outcome_exposes_its_margin():
    outcome = _outcome(0, True, 4, 1)
    assert outcome.pokemon_margin == 3
    assert outcome.hp_margin > 0


def test_a_battle_with_no_readable_final_state_reads_as_zero_not_as_a_win():
    """A missing margin must not be counted as an even result either -- it is
    excluded from the summary rather than averaged in as a nil."""
    outcome = _outcome(0, True, 0, 0, margin=False)
    assert outcome.pokemon_margin == 0
    assert _result([outcome]).pokemon_margin.values == ()


def test_the_match_result_summarises_both_margins():
    outcomes = [_outcome(i, True, 4, 1) for i in range(10)]
    result = _result(outcomes)
    assert result.pokemon_margin.mean == 3.0
    assert result.pokemon_margin.is_significant
    assert result.hp_margin.mean > 0


def test_a_decisive_run_and_a_narrow_one_differ_in_margin_but_not_in_wins():
    """The reason the margin exists: both are ten wins."""
    sweep = _result([_outcome(i, True, 4, 0) for i in range(10)])
    narrow = _result([_outcome(i, True, 1, 0) for i in range(10)])
    assert sweep.win_rate_a == narrow.win_rate_a == 1.0
    assert sweep.pokemon_margin.mean > narrow.pokemon_margin.mean


def test_the_summary_mentions_the_margin_when_there_is_one():
    result = _result([_outcome(i, True, 4, 1) for i in range(10)])
    assert "margin" in result.summary()


def test_the_summary_omits_the_margin_when_no_battle_recorded_one():
    result = _result([_outcome(i, True, 0, 0, margin=False) for i in range(10)])
    assert "margin" not in result.summary()
