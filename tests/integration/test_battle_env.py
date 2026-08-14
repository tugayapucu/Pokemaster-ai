"""BattleEnv driving real battles, with agents that only see domain objects."""

import random

import pytest

from champions_ai.domain import (
    REGULATION_M_B,
    JointAction,
    PassAction,
    TeamPreviewAction,
)
from champions_ai.env import BattleEnv, Decision

pytestmark = pytest.mark.integration


def _random_agent(env: BattleEnv, player: int, rng: random.Random):
    """The whole agent. If this needs to grow, the environment is doing too little."""
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
        result = env.step({p: _random_agent(env, p, rng) for p in waiting})
    return result


def test_random_agents_complete_many_battles_without_a_rejected_action(env, mega_teams):
    """The engine accepting every generated action is the real correctness check."""
    rng = random.Random(2026)
    results = [_play(env, mega_teams, f"sodium,{i:064x}", rng) for i in range(8)]

    assert all(r.terminal for r in results)
    assert all(r.winner in (0, 1) for r in results)
    assert all(r.turn > 0 for r in results)


def test_both_sides_win_sometimes(env, mega_teams):
    """A mirror match between random agents should not be one-sided.

    16 battles: a fair result makes an all-one-side outcome vanishingly
    unlikely, so a failure here means one side's actions are being generated
    worse than the other's rather than bad luck.
    """
    rng = random.Random(2026)
    winners = [_play(env, mega_teams, f"sodium,{i + 100:064x}", rng).winner for i in range(16)]
    assert set(winners) == {0, 1}, f"one-sided result: {winners}"


def test_same_seed_reproduces_the_same_battle(env, mega_teams):
    first = _play(env, mega_teams, "sodium," + "7b" * 32, random.Random(4))
    protocol_first = [line for line in env.protocol if not line.startswith("|t:|")]

    second = _play(env, mega_teams, "sodium," + "7b" * 32, random.Random(4))
    protocol_second = [line for line in env.protocol if not line.startswith("|t:|")]

    assert first.winner == second.winner
    assert protocol_first == protocol_second


def test_step_rejects_actions_for_players_that_were_not_asked(env, mega_teams):
    rng = random.Random(1)
    env.reset(mega_teams, seed="sodium," + "9d" * 32)
    with pytest.raises(ValueError):
        env.step({})
    waiting = env.awaiting()
    with pytest.raises(ValueError):
        env.step({p: _random_agent(env, p, rng) for p in waiting} | {9: None})


def test_team_preview_requires_a_team_preview_action(env, mega_teams):
    env.reset(mega_teams, seed="sodium," + "9d" * 32)
    assert env.decision(0) is Decision.TEAM_PREVIEW

    # Enumerating joint actions makes no sense for a pick-N-of-6 decision.
    with pytest.raises(ValueError):
        env.legal_actions(0)

    turn_action = JointAction(slot_actions=(PassAction(), PassAction()))
    with pytest.raises(TypeError):
        env.step({p: turn_action for p in env.awaiting()})


def test_observations_stay_masked_throughout(env, mega_teams):
    _play(env, mega_teams, "sodium," + "2f" * 32, random.Random(5))
    for player in (0, 1):
        observation = env.observation(player)
        for mon in observation.opponent_side.revealed:
            assert 0 <= mon.hp_percent <= 100


def test_finished_battle_cannot_be_stepped_again(env, mega_teams):
    _play(env, mega_teams, "sodium," + "4e" * 32, random.Random(6))
    assert env.terminal
    with pytest.raises(RuntimeError):
        env.step({})
