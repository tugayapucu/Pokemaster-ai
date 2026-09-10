"""Scouting a team against the field.

The load-bearing property is the one `evaluate` established for the other
direction: **with the same agent on both sides, an even matchup must tie.** A
team played against a copy of itself has to come out 1-1, and if it does not,
the harness is measuring something other than the teams -- a seat advantage, an
unshared seed, an agent with memory.

Everything else here is arithmetic on the report, which exists so the caller
reads *which* matchups lost rather than only how many.
"""

from champions_ai.evaluation.team_strength import Matchup, TeamReport


def _report(*results: int) -> TeamReport:
    """A report from per-matchup win counts out of two."""
    matchups = tuple(
        Matchup(opponent=f"t{i}", roster=(f"mon{i}",), wins=w, battles=2)
        for i, w in enumerate(results)
    )
    return TeamReport(
        team="mine",
        battles=2 * len(results),
        wins=sum(results),
        draws=0,
        opponents=len(results),
        matchups=matchups,
    )


def test_the_win_rate_is_over_battles_not_matchups():
    """Two battles per opponent, so 3 of 4 matchups won 2-0 is not 75%."""
    report = _report(2, 2, 2, 0)
    assert report.battles == 8
    assert report.win_rate == 0.75


def test_the_interval_widens_when_there_is_less_to_go_on():
    """A scout over ten opponents is not the same claim as one over a hundred,
    and the number alone does not say which it was."""
    narrow = _report(*([2, 0] * 50))
    wide = _report(2, 0)
    assert narrow.win_rate == wide.win_rate == 0.5
    assert (narrow.interval[1] - narrow.interval[0]) < (wide.interval[1] - wide.interval[0])


def test_the_worst_matchups_come_out_hardest_first():
    """The useful half of the output. A win rate says whether to keep looking;
    these say what to change."""
    report = _report(2, 0, 1, 0, 2)
    assert [m.wins for m in report.worst(3)] == [0, 0, 1]


def test_the_best_matchups_come_out_easiest_first():
    report = _report(2, 0, 1, 0, 2)
    assert [m.wins for m in report.best(3)] == [2, 2, 1]


def test_an_even_matchup_is_one_that_split_rather_than_one_we_were_lucky_in():
    """With identical agents and a shared seed, 1-1 means the two teams could
    not separate each other. 2-0 either way means one of them did."""
    assert _report(1, 1, 2, 0).even() == 2


def test_a_team_with_no_opponents_reports_nothing_rather_than_dividing_by_zero():
    empty = TeamReport(team="mine", battles=0, wins=0, draws=0, opponents=0)
    assert empty.win_rate == 0.0
    assert empty.worst() == ()
