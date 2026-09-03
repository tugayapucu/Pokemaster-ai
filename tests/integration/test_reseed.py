"""Determinism and branching: the two properties a fork is built on.

A fork here is a *replay*: start from the same seed, resend the same choices,
and the engine reproduces the position exactly. That only works if the engine
is deterministic given seed and inputs, which is asserted here rather than
assumed -- the same property common random numbers already rely on.

The second half is the opposite property. A reproduced position would give
identical rollouts forever, which measures nothing. `reseed` replaces the
generator at the branch point so that what follows is a sample.
"""

import pytest

from champions_ai.simulator import ShowdownBridge

pytestmark = pytest.mark.integration

SEED = "sodium," + "0123456789abcdef" * 4
BRANCH = "sodium," + "fedcba9876543210" * 4


def _play(bridge: ShowdownBridge, teams, battle_format, *, turns=6, reseed_after=None):
    """Drive a battle on `default` choices, returning the protocol it emitted."""
    lines: list[str] = []

    def collect(events):
        for event in events:
            if event.get("type") == "line":
                lines.append(event["line"])

    collect(bridge.start_battle(battle_format, teams[0], teams[1], seed=SEED))
    for player in ("p1", "p2"):
        collect(bridge.choose(player, "default"))

    for turn in range(turns):
        if reseed_after is not None and turn == reseed_after:
            bridge.reseed(BRANCH)
        for player in ("p1", "p2"):
            collect(bridge.choose(player, "default"))
    return lines


def test_replaying_a_seed_and_the_same_choices_reproduces_the_battle(bridge, teams, battle_format):
    """The property that makes a fork exact rather than approximate."""
    first = _play(bridge, teams, battle_format)
    second = _play(bridge, teams, battle_format)

    assert first == second
    assert len(first) > 20, "a six-turn battle should emit more than a handful of lines"


def test_reseeding_branches_the_battle(bridge, teams, battle_format):
    """Without this a reproduced position would roll the same dice every time."""
    straight = _play(bridge, teams, battle_format)
    branched = _play(bridge, teams, battle_format, reseed_after=1)

    shared = 0
    for a, b in zip(straight, branched):
        if a != b:
            break
        shared += 1

    assert branched != straight, "reseeding changed nothing; the fork would not sample"
    assert shared > 0, "the battle diverged before the branch point"


def test_reseeding_is_itself_reproducible(bridge, teams, battle_format):
    """A branch has to be repeatable, or a rollout cannot be re-run or debugged."""
    assert _play(bridge, teams, battle_format, reseed_after=1) == _play(
        bridge, teams, battle_format, reseed_after=1
    )


def test_reseed_reports_the_seed_now_in_force(bridge, teams, battle_format):
    """`battle.prngSeed` is captured at construction and never updated, so the
    obvious read-back silently reports the old seed."""
    bridge.start_battle(battle_format, teams[0], teams[1], seed=SEED)
    assert bridge.reseed(BRANCH) == BRANCH
