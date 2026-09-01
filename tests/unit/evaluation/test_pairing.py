"""Each agent must play each team, not just each seat.

`evaluate` plays every matchup twice. The two passes used to exchange the
agents *and* the teams, which cancels: agent A kept the team it started with
and only the seat was controlled.

That is not biased -- over many matchups the draw evens out -- but it is
enormously noisy. On the frozen pool, 85% of matchups are one-sided with
identical agents on both sides, and 93% of the variance in outcomes is the
matchup rather than play. Leaving that uncontrolled put all of it in the error
bars, which is why the harness could not resolve small effects.

The existing integration tests could not catch it. They use `mirror_pool`,
described in its own docstring as "two copies of one team: isolates the harness
from team-strength effects" -- so team assignment could not matter and the bug
was invisible. These use two *different* teams.

No battles are run: `play_battle` is stubbed, because the question is purely
who was handed what.
"""

import pytest

from champions_ai.data.team_pool import BattleTeam, TeamPool
from champions_ai.domain import PokemonSet, Team
from champions_ai.evaluation import runner


class _Result:
    """The little `play_battle` returns that `evaluate` actually reads."""

    def __init__(self, winner):
        self.winner = winner
        self.turn = 1


class _Env:
    """Enough env for `evaluate`; the margin path is meant to bail out."""

    def tracker(self, player):
        # `evaluate` catches RuntimeError here and records no margin.
        raise RuntimeError("no tracker in this stub")


def _team(species: str) -> BattleTeam:
    return BattleTeam(
        team=Team(
            pokemon=tuple(
                PokemonSet(species=f"{species}{i}", level=50, ability="a", moves=("tackle",))
                for i in range(6)
            )
        ),
        packed=species,
        name=species,
    )


@pytest.fixture
def recorded(monkeypatch):
    """Every (agents, teams) pairing `evaluate` hands to `play_battle`."""
    seen: list[tuple[tuple[str, str], tuple[str, str]]] = []

    def fake_play_battle(env, agents, teams, *, seed=None):
        seen.append(((agents[0].name, agents[1].name), (teams[0].name, teams[1].name)))
        return _Result(winner=0)

    monkeypatch.setattr(runner, "play_battle", fake_play_battle)

    class Agent:
        def __init__(self, name):
            self.name = name

        def on_battle_start(self):
            pass

    pool = TeamPool([_team("LEFT"), _team("RIGHT")])
    runner.evaluate(_Env(), Agent("A"), Agent("B"), pool, battles=2, seed=0)
    return seen


def _team_of(agent, agents, teams) -> str:
    return teams[agents.index(agent)]


class TestEachAgentPlaysEachTeam:
    def test_a_matchup_is_played_twice(self, recorded):
        assert len(recorded) == 2

    def test_agent_a_does_not_keep_one_team(self, recorded):
        """The bug: swapping agents *and* teams cancels, so A kept its team."""
        held = [_team_of("A", agents, teams) for agents, teams in recorded]
        assert len(set(held)) == 2, f"agent A held {held} in both passes"

    def test_agent_b_does_not_keep_one_team_either(self, recorded):
        held = [_team_of("B", agents, teams) for agents, teams in recorded]
        assert len(set(held)) == 2, f"agent B held {held} in both passes"

    def test_each_agent_sits_in_each_seat(self, recorded):
        """Seat control is what the old code did get right; keep it."""
        for name in ("A", "B"):
            seats = [agents.index(name) for agents, _ in recorded]
            assert sorted(seats) == [0, 1], f"{name} sat in {seats}"

    def test_the_two_passes_are_a_genuine_exchange(self, recorded):
        """A's team in pass 1 is B's team in pass 2, and vice versa."""
        first, second = recorded
        assert _team_of("A", *first) == _team_of("B", *second)
        assert _team_of("B", *first) == _team_of("A", *second)


class TestCommonRandomNumbers:
    """Both passes of a matchup should be able to share their luck.

    Once the teams and seats are identical between the two passes and only the
    agents swap, giving the pair one seed makes it differ in nothing but the
    policies. That is plain common random numbers, and it turns the mirror
    invariant from "should tie" into "must tie": two identical agents produce
    two identical battles, so each wins exactly one pass.

    Without it the passes draw different luck, which is why identical agents
    still failed to tie 19% of matchups after the pairing itself was fixed.
    """

    def _seeds(self, monkeypatch, *, common_seed):
        seen: list[str] = []

        def fake_play_battle(env, agents, teams, *, seed=None):
            seen.append(seed)
            return _Result(winner=0)

        monkeypatch.setattr(runner, "play_battle", fake_play_battle)

        class Agent:
            def __init__(self, name):
                self.name = name

            def on_battle_start(self):
                pass

        pool = TeamPool([_team("LEFT"), _team("RIGHT")])
        runner.evaluate(
            _Env(),
            Agent("A"),
            Agent("B"),
            pool,
            battles=4,
            seed=0,
            common_seed=common_seed,
        )
        return seen

    def test_a_pair_shares_one_seed(self, monkeypatch):
        seeds = self._seeds(monkeypatch, common_seed=True)
        assert len(seeds) == 4
        assert seeds[0] == seeds[1], "the two passes of a matchup must share luck"
        assert seeds[2] == seeds[3]

    def test_different_matchups_still_differ(self, monkeypatch):
        """Sharing within a pair must not mean sharing across pairs."""
        seeds = self._seeds(monkeypatch, common_seed=True)
        assert seeds[0] != seeds[2]

    def test_it_can_be_turned_off(self, monkeypatch):
        seeds = self._seeds(monkeypatch, common_seed=False)
        assert seeds[0] != seeds[1], "without it each battle draws its own luck"
