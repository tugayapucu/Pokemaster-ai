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
    assert empty.by_species(min_opponents=1) == ()
    assert empty.by_roster(min_opponents=1) == ()


def _rostered(*rows: tuple[tuple[str, ...], int]) -> TeamReport:
    """A report from (opposing roster, wins out of two) rows."""
    matchups = tuple(
        Matchup(opponent=f"t{i}", roster=roster, wins=wins, battles=2)
        for i, (roster, wins) in enumerate(rows)
    )
    return TeamReport(
        team="mine",
        battles=2 * len(rows),
        wins=sum(wins for _, wins in rows),
        draws=0,
        opponents=len(rows),
        matchups=matchups,
    )


def test_a_species_group_pools_every_opponent_that_brought_it():
    """One row is two battles, which a battle seed alone can flip. A species
    group reads across every opponent carrying it."""
    report = _rostered((("Drake", "Bloom"), 0), (("Drake", "Fang"), 1), (("Bloom", "Fang"), 2))
    groups = {g.label: g for g in report.by_species(min_opponents=1)}
    drake = groups[("Drake",)]
    assert (drake.opponents, drake.wins, drake.battles) == (2, 1, 4)
    assert groups[("Fang",)].rate == 0.75


def test_species_groups_come_out_hardest_first():
    report = _rostered((("Drake", "Bloom"), 0), (("Drake", "Fang"), 1), (("Bloom", "Fang"), 2))
    assert [g.label[0] for g in report.by_species(min_opponents=1)] == ["Drake", "Bloom", "Fang"]


def test_a_species_seen_on_too_few_opponents_is_left_out():
    report = _rostered((("Drake", "Bloom"), 0), (("Drake", "Fang"), 1))
    assert [g.label[0] for g in report.by_species(min_opponents=2)] == ["Drake"]


def test_the_same_six_in_a_different_order_are_one_roster():
    """Near-copies of one player's team: drawn twice, it is one four-battle
    matchup, not two two-battle ones."""
    report = _rostered((("Drake", "Bloom"), 0), (("Bloom", "Drake"), 1), (("Fang", "Wisp"), 2))
    groups = report.by_roster()
    assert len(groups) == 1
    assert (groups[0].opponents, groups[0].wins, groups[0].battles) == (2, 1, 4)


def test_a_roster_drawn_once_is_not_a_group_by_default():
    report = _rostered((("Drake", "Bloom"), 0), (("Fang", "Wisp"), 2))
    assert report.by_roster() == ()
    assert len(report.by_roster(min_opponents=1)) == 2


def test_a_group_interval_narrows_with_more_opponents():
    few = _rostered(*[(("Drake",), 1)] * 2).by_species(min_opponents=1)[0]
    many = _rostered(*[(("Drake",), 1)] * 50).by_species(min_opponents=1)[0]
    assert few.rate == many.rate == 0.5
    assert (many.interval[1] - many.interval[0]) < (few.interval[1] - few.interval[0])


class TestRefusedBattles:
    """A battle the engine refuses is skipped and recorded, not fatal.

    A refusal used to end the whole scout run, and a long run is exactly where a
    one-in-thousands legality bug turns up. It is still a bug, so it is kept.
    """

    def _pool(self, count: int):
        from types import SimpleNamespace

        teams = [
            SimpleNamespace(
                name=f"opp{i}",
                team=SimpleNamespace(pokemon=(SimpleNamespace(species=f"Mon{i}"),)),
            )
            for i in range(count)
        ]
        return SimpleNamespace(teams=teams)

    def _scout(self, monkeypatch, refuse: set[int], opponents: int = 2):
        """Scout with a fake battle runner: calls numbered from 0 in `refuse`
        are refused, and every other battle is won by whoever sits in seat 0."""
        from types import SimpleNamespace

        import champions_ai.evaluation.team_strength as module
        from champions_ai.simulator import BridgeError

        calls = []

        def fake_play_battle(env, agents, teams, seed):
            number = len(calls)
            calls.append(seed)
            if number in refuse:
                raise BridgeError("engine rejected a choice: [Invalid choice] test")
            return SimpleNamespace(winner=0)

        monkeypatch.setattr(module, "play_battle", fake_play_battle)
        team = SimpleNamespace(name="mine")
        report = module.scout_team(None, None, team, self._pool(opponents),
                                   opponents=opponents, seed=0)
        return report, calls

    def test_the_run_carries_on_past_a_refused_battle(self, monkeypatch):
        report, calls = self._scout(monkeypatch, refuse={1})
        assert len(calls) == 4
        assert report.battles == 3
        assert len(report.refused) == 1

    def test_a_refusal_records_what_reproduces_it(self, monkeypatch):
        report, calls = self._scout(monkeypatch, refuse={1})
        refused = report.refused[0]
        assert refused.seat == 1
        assert refused.seed == calls[1]
        assert "Invalid choice" in refused.message

    def test_a_matchup_counts_only_the_battles_that_finished(self, monkeypatch):
        report, _ = self._scout(monkeypatch, refuse={1})
        assert [m.battles for m in report.matchups] == [1, 2]

    def test_an_opponent_with_no_finished_battle_adds_no_matchup(self, monkeypatch):
        """A 0/0 row would sort as the worst matchup of all."""
        report, _ = self._scout(monkeypatch, refuse={0, 1})
        assert len(report.matchups) == 1
        assert report.battles == 2

    def test_nothing_refused_records_nothing(self, monkeypatch):
        report, _ = self._scout(monkeypatch, refuse=set())
        assert report.refused == ()
        assert report.battles == 4
