"""Recording and replaying battles.

The point of storing decisions rather than states is that a record can be
*checked*: replaying it must land on the same winner, the same turn count, and
the same protocol. These tests assert exactly that, so a recording format that
silently loses information fails rather than producing plausible-looking data.
"""

import random

import pytest

from champions_ai.data import Trajectory
from champions_ai.domain import REGULATION_M_B, TeamPreviewAction
from champions_ai.env import BattleEnv, Decision

pytestmark = pytest.mark.integration


def _agent(env: BattleEnv, player: int, rng: random.Random):
    if env.decision(player) is Decision.TEAM_PREVIEW:
        return TeamPreviewAction(
            picks=tuple(rng.sample(range(6), REGULATION_M_B.picked_team_size))
        )
    return rng.choice(env.legal_actions(player))


def _play(env: BattleEnv, teams, seed: str, rng: random.Random):
    result = env.reset(teams, seed=seed)
    while not result.terminal:
        waiting = env.awaiting()
        if not waiting:
            break
        result = env.step({p: _agent(env, p, rng) for p in waiting})
    return result


@pytest.fixture(scope="module")
def recorded(env, mega_teams):
    """A finished battle plus its trajectory."""
    result = _play(env, mega_teams, "sodium," + "a1" * 32, random.Random(31))
    return result, env.trajectory(include_protocol=True), list(env.protocol)


def test_trajectory_captures_the_battle(recorded):
    result, trajectory, protocol = recorded
    assert trajectory.winner == result.winner
    assert trajectory.turns == result.turn
    assert trajectory.decisions
    assert trajectory.replayable
    assert trajectory.format_id == REGULATION_M_B.format_id
    assert trajectory.protocol == tuple(protocol)


def test_decisions_record_how_many_options_there_were(recorded):
    """Choosing one action out of ninety is different evidence from one out of two."""
    _, trajectory, _ = recorded
    turn_decisions = [d for d in trajectory.decisions if d.action.kind == "joint"]
    assert turn_decisions
    assert all(d.legal_action_count and d.legal_action_count >= 1 for d in turn_decisions)


def _without_timestamps(lines) -> list[str]:
    """`|t:|` lines carry wall-clock time and differ between identical battles."""
    return [line for line in lines if not line.startswith("|t:|")]


def test_replay_reproduces_the_battle_exactly(env, mega_teams, recorded):
    result, trajectory, protocol = recorded
    replayed = env.replay(trajectory, mega_teams)

    assert replayed.winner == result.winner
    assert replayed.turn == result.turn
    assert _without_timestamps(env.protocol) == _without_timestamps(protocol)


def test_trajectory_survives_a_json_round_trip(tmp_path, recorded):
    _, trajectory, _ = recorded
    path = tmp_path / "battle.json"
    trajectory.save(path)
    assert Trajectory.load(path) == trajectory


def test_a_reloaded_trajectory_still_replays(env, mega_teams, tmp_path, recorded):
    """The stored form, not just the in-memory object, must be enough to reproduce a battle."""
    result, trajectory, _ = recorded
    path = tmp_path / "battle.json"
    trajectory.save(path)

    replayed = env.replay(Trajectory.load(path), mega_teams)
    assert replayed.winner == result.winner
    assert replayed.turn == result.turn


def test_protocol_can_be_dropped_to_shrink_a_record(recorded):
    _, trajectory, _ = recorded
    lean = trajectory.without_protocol()
    assert lean.protocol == ()
    assert lean.replayable
    assert len(lean.model_dump_json()) < len(trajectory.model_dump_json())


def test_replay_refuses_an_unseeded_record(env, mega_teams, recorded):
    _, trajectory, _ = recorded
    unseeded = trajectory.model_copy(update={"seed": None})
    assert not unseeded.replayable
    with pytest.raises(ValueError):
        env.replay(unseeded, mega_teams)


def test_truncated_trajectory_fails_instead_of_replaying_half_a_battle(env, mega_teams, recorded):
    _, trajectory, _ = recorded
    truncated = trajectory.model_copy(update={"decisions": trajectory.decisions[:2]})
    with pytest.raises(ValueError):
        env.replay(truncated, mega_teams)
