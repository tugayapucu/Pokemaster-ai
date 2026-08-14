"""The evaluation harness against real battles."""

import pytest

from champions_ai.agents import RandomAgent
from champions_ai.data import TeamPool
from champions_ai.domain import REGULATION_M_B
from champions_ai.evaluation import evaluate, play_battle

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def mirror_pool(mega_team):
    """Two copies of one team: isolates the harness from team-strength effects."""
    return TeamPool([mega_team, mega_team])


@pytest.fixture(scope="module")
def mirror_match(env, mirror_pool):
    """Two random agents over enough battles to say something."""
    return evaluate(
        env,
        RandomAgent(seed=1, name="random-a"),
        RandomAgent(seed=2, name="random-b"),
        mirror_pool,
        battles=60,
        seed=42,
    )


def test_agents_can_play_a_battle_through_the_interface(env, mega_teams):
    result = play_battle(
        env,
        (RandomAgent(seed=1), RandomAgent(seed=2)),
        mega_teams,
        seed="sodium," + "c7" * 32,
    )
    assert result.terminal
    assert result.winner in (0, 1)


def test_agents_use_the_team_preview_they_are_given(env, mega_teams):
    """RandomAgent samples its picks, so it should not always bring the first four."""
    picks = set()
    for index in range(6):
        env.reset(mega_teams, seed=f"sodium,{index:064x}")
        preview = env.team_preview(0)
        assert len(preview.own_team) == REGULATION_M_B.min_team_size
        assert len(preview.opponent_team) == REGULATION_M_B.min_team_size
        action = RandomAgent(seed=index).select_team_preview(
            preview, REGULATION_M_B.picked_team_size
        )
        picks.add(action.picks)
    assert len(picks) > 1


def test_opponent_roster_at_preview_shows_species_but_not_their_sets(env, mega_teams):
    """Reg M-B does not open team sheets by default (ADR 0002)."""
    env.reset(mega_teams, seed="sodium," + "1a" * 32)
    for revealed in env.team_preview(0).opponent_team:
        assert revealed.species
        assert revealed.ability is None
        assert revealed.item is None
        assert revealed.moves is None


def test_identical_agents_are_a_coin_flip(mirror_match):
    """The strongest check on the harness: a mirror match must not favour a side.

    A skew here would mean the harness itself is biased -- side swapping broken,
    or one seat advantaged -- and every later agent comparison would inherit it.
    """
    low, high = mirror_match.confidence_interval_a
    assert low <= 0.5 <= high, mirror_match.summary()
    assert not mirror_match.is_significant


def test_sides_are_swapped_evenly(mirror_match):
    as_player_one = sum(1 for o in mirror_match.outcomes if o.first_agent_played_as == 0)
    assert as_player_one == mirror_match.battles // 2


def test_every_battle_is_accounted_for(mirror_match):
    assert mirror_match.wins_a + mirror_match.wins_b + mirror_match.draws == mirror_match.battles
    assert len(mirror_match.outcomes) == mirror_match.battles
    assert all(o.turns > 0 for o in mirror_match.outcomes)


def test_a_mirror_pool_is_all_one_pairing(mirror_match):
    """Both teams are identical, so every draw is the same matchup and groups as one."""
    assert mirror_match.matchups_played == 1
    assert sum(len(s) for s in mirror_match.matchup_scores.values()) == mirror_match.battles


def test_the_same_seed_reproduces_the_whole_run(env, mirror_pool, mirror_match):
    repeat = evaluate(
        env,
        RandomAgent(seed=1, name="random-a"),
        RandomAgent(seed=2, name="random-b"),
        mirror_pool,
        battles=60,
        seed=42,
    )
    assert repeat.wins_a == mirror_match.wins_a
    assert repeat.wins_b == mirror_match.wins_b
    assert [o.winner for o in repeat.outcomes] == [o.winner for o in mirror_match.outcomes]


def test_a_different_seed_gives_a_different_run(env, mirror_pool, mirror_match):
    other = evaluate(
        env,
        RandomAgent(seed=1, name="random-a"),
        RandomAgent(seed=2, name="random-b"),
        mirror_pool,
        battles=60,
        seed=7,
    )
    assert [o.seed for o in other.outcomes] != [o.seed for o in mirror_match.outcomes]


def test_trajectories_are_kept_only_when_asked(env, mirror_pool):
    without = evaluate(
        env, RandomAgent(seed=1), RandomAgent(seed=2), mirror_pool, battles=2, seed=5
    )
    assert without.trajectories == ()

    with_records = evaluate(
        env,
        RandomAgent(seed=1),
        RandomAgent(seed=2),
        mirror_pool,
        battles=2,
        seed=5,
        keep_trajectories=True,
    )
    assert len(with_records.trajectories) == 2
    assert all(t.replayable for t in with_records.trajectories)
    assert with_records.trajectories[0].metadata["agent_p1"]
    assert with_records.trajectories[0].metadata["matchup"]


def test_zero_battles_is_rejected(env, mirror_pool):
    with pytest.raises(ValueError):
        evaluate(env, RandomAgent(), RandomAgent(), mirror_pool, battles=0)


def test_evaluating_over_a_real_pool_spreads_across_teams(env, team_pool):
    """A result should rest on several team pairings, not one lucky matchup."""
    result = evaluate(
        env,
        RandomAgent(seed=1, name="random-a"),
        RandomAgent(seed=2, name="random-b"),
        team_pool,
        battles=12,
        seed=3,
    )
    assert result.matchups_played > 1
    assert result.battles == 12
    assert result.wins_a + result.wins_b + result.draws == 12
    # Every distinct pairing is played from both team assignments, so team
    # strength cancels instead of being credited to whichever agent drew it.
    assert all(len(scores) % 2 == 0 for scores in result.matchup_scores.values())
