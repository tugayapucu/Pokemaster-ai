"""Forking the engine: reproduce a position exactly, then branch from it.

A fork here is a prefix replay. `BattleEnv.replay(..., stop_after=k)` re-runs a
recording for k steps and stops mid-battle, and `reseed` then replaces the
random number generator so what follows is a sample rather than the same
replay again.

The load-bearing claim is that the reproduced position is *exact*. It is
checked the strongest way available: finish the prefix with the same
deterministic agents that produced the recording, and require the whole battle
back, line for line. Any difference in the position at all -- a hidden volatile,
a PP count, an RNG offset -- would send a deterministic agent somewhere else.
"""

import pytest

from champions_ai.agents import HeuristicAgent
from champions_ai.dex import Dex
from champions_ai.evaluation import play_battle, play_out

pytestmark = pytest.mark.integration

SEED = "sodium," + "0f1e2d3c4b5a6978" * 4
BRANCH = "sodium," + "89abcdef01234567" * 4


@pytest.fixture(scope="module")
def dex(bridge) -> Dex:
    return Dex.load(bridge)


def _agents(dex):
    """Deterministic on both sides -- the whole test rests on that."""
    return (HeuristicAgent(dex, name="a"), HeuristicAgent(dex, name="b"))


@pytest.fixture(scope="module")
def recorded(env, dex, mega_teams):
    """One battle, and the recording that should reproduce it."""
    result = play_battle(env, _agents(dex), mega_teams, seed=SEED)
    return result, env.trajectory(include_protocol=True)


def test_a_prefix_replay_reproduces_the_position_exactly(env, dex, mega_teams, recorded):
    original, trajectory = recorded
    steps = max(1, len(trajectory.decisions) // 4)

    env.replay(trajectory, mega_teams, stop_after=steps)
    assert not env.terminal, "the prefix should stop mid-battle, not play the whole thing"

    finished = play_out(env, _agents(dex))

    assert finished.winner == original.winner
    assert finished.protocol == original.protocol


def test_the_prefix_actually_stops_early(env, mega_teams, recorded):
    _, trajectory = recorded
    env.replay(trajectory, mega_teams, stop_after=1)

    assert not env.terminal
    assert env.turn <= 1
    assert env.awaiting(), "a stopped battle should still be waiting on somebody"


def test_replaying_the_whole_thing_is_unchanged_by_the_new_argument(env, mega_teams, recorded):
    original, trajectory = recorded
    assert env.replay(trajectory, mega_teams).winner == original.winner


def test_reseeding_after_a_prefix_branches_the_battle(env, dex, mega_teams, recorded):
    original, trajectory = recorded
    steps = max(1, len(trajectory.decisions) // 4)

    env.replay(trajectory, mega_teams, stop_after=steps)
    env.reseed(BRANCH)
    branched = play_out(env, _agents(dex))

    assert branched.protocol != original.protocol, (
        "reseeding changed nothing, so every rollout from a position would be identical"
    )
    shared = 0
    for a, b in zip(original.protocol, branched.protocol):
        if a != b:
            break
        shared += 1
    assert shared > 0, "the branch diverged before the branch point"


def test_a_branch_is_reproducible(env, dex, mega_teams, recorded):
    """A rollout that cannot be re-run cannot be debugged."""
    _, trajectory = recorded
    steps = max(1, len(trajectory.decisions) // 4)

    outcomes = []
    for _ in range(2):
        env.replay(trajectory, mega_teams, stop_after=steps)
        env.reseed(BRANCH)
        outcomes.append(play_out(env, _agents(dex)).protocol)

    assert outcomes[0] == outcomes[1]


def test_different_branch_seeds_give_different_continuations(env, dex, mega_teams, recorded):
    """Otherwise the sample has one member however many rollouts are run."""
    _, trajectory = recorded
    steps = max(1, len(trajectory.decisions) // 4)

    seen = set()
    for tail in ("aa", "bb", "cc", "dd"):
        env.replay(trajectory, mega_teams, stop_after=steps)
        env.reseed("sodium," + (tail * 16))
        seen.add(play_out(env, _agents(dex)).protocol)

    assert len(seen) > 1


def test_a_branched_battle_is_not_recorded_as_replayable(env, dex, mega_teams, recorded):
    """The bug this guards: a fork used to record its *starting* seed.

    `replayable` then reported True and replaying produced a different battle --
    214 protocol lines against 210, with the same winner, so nothing looked
    wrong. A branched battle has no single seed and the record must say so.
    """
    _, trajectory = recorded

    env.replay(trajectory, mega_teams, stop_after=3)
    env.reseed(BRANCH)
    play_out(env, _agents(dex))
    branched = env.trajectory()

    assert branched.seed is None
    assert not branched.replayable
    assert branched.metadata["branched"] == "true"
    assert branched.metadata["starting_seed"] == SEED
    assert BRANCH in branched.metadata["branch_seeds"]
    # The decisions are still there -- the record is honest, not empty.
    assert branched.decisions


def test_replaying_a_branched_record_is_refused_by_name(env, dex, mega_teams, recorded):
    _, trajectory = recorded

    env.replay(trajectory, mega_teams, stop_after=3)
    env.reseed(BRANCH)
    play_out(env, _agents(dex))
    branched = env.trajectory()

    with pytest.raises(ValueError, match="branched"):
        env.replay(branched, mega_teams)


def test_an_unbranched_battle_still_records_its_seed(env, dex, mega_teams):
    """Regression: the fix must not strip the seed from ordinary battles."""
    play_battle(env, _agents(dex), mega_teams, seed=SEED)
    trajectory = env.trajectory()

    assert trajectory.seed == SEED
    assert trajectory.replayable
    assert "branched" not in trajectory.metadata


def test_resetting_clears_the_branch(env, dex, mega_teams, recorded):
    """A branched env must not poison the next battle it runs."""
    _, trajectory = recorded
    env.replay(trajectory, mega_teams, stop_after=3)
    env.reseed(BRANCH)

    play_battle(env, _agents(dex), mega_teams, seed=SEED)

    assert env.trajectory().replayable


def test_caller_metadata_survives_alongside_the_branch_note(env, dex, mega_teams, recorded):
    _, trajectory = recorded
    env.replay(trajectory, mega_teams, stop_after=3)
    env.reseed(BRANCH)

    recorded_with_note = env.trajectory(metadata={"experiment": "0039"})

    assert recorded_with_note.metadata["experiment"] == "0039"
    assert recorded_with_note.metadata["branched"] == "true"
