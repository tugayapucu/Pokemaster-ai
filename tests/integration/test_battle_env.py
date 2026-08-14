"""BattleEnv driving real battles, with agents that only see domain objects."""

import random

import pytest

from champions_ai.domain import (
    REGULATION_M_B,
    JointAction,
    PassAction,
    PokemonSet,
    StatSpread,
    Team,
    TeamPreviewAction,
)
from champions_ai.env import BattleEnv, Decision

pytestmark = pytest.mark.integration


def _parse_team(text: str) -> Team:
    mons = []
    for block in text.split("\n\n"):
        lines = [line.strip() for line in block.strip().splitlines() if line.strip()]
        head = lines[0]
        mons.append(
            PokemonSet(
                species=head.split("@")[0].strip(),
                level=50,
                ability=next(
                    x.split(":", 1)[1].strip() for x in lines if x.startswith("Ability:")
                ),
                moves=tuple(x[2:].strip() for x in lines if x.startswith("- ")),
                item=head.split("@")[1].strip() if "@" in head else None,
                stats=StatSpread(),
            )
        )
    return Team(pokemon=tuple(mons))


def _random_agent(env: BattleEnv, player: int, rng: random.Random):
    """The whole agent. If this needs to grow, the environment is doing too little."""
    if env.decision(player) is Decision.TEAM_PREVIEW:
        return TeamPreviewAction(
            picks=tuple(rng.sample(range(6), REGULATION_M_B.picked_team_size))
        )
    return rng.choice(env.legal_actions(player))


def _play(env: BattleEnv, packed: str, seed: str, rng: random.Random):
    result = env.reset((packed, packed), seed=seed)
    while not result.terminal:
        waiting = env.awaiting()
        if not waiting:
            break
        result = env.step({p: _random_agent(env, p, rng) for p in waiting})
    return result


@pytest.fixture(scope="module")
def env(bridge, mega_team_text):
    team = _parse_team(mega_team_text)
    return BattleEnv(REGULATION_M_B, (team, team), bridge=bridge)


@pytest.fixture(scope="module")
def packed(bridge, battle_format, mega_team_text):
    return bridge.validate_team(battle_format, mega_team_text)


def test_random_agents_complete_many_battles_without_a_rejected_action(env, packed):
    """The engine accepting every generated action is the real correctness check."""
    rng = random.Random(2026)
    results = [_play(env, packed, f"sodium,{i:064x}", rng) for i in range(8)]

    assert all(r.terminal for r in results)
    assert all(r.winner in (0, 1) for r in results)
    assert all(r.turn > 0 for r in results)


def test_both_sides_win_sometimes(env, packed):
    """A mirror match between random agents should not be one-sided.

    16 battles: a fair result makes an all-one-side outcome vanishingly
    unlikely, so a failure here means one side's actions are being generated
    worse than the other's rather than bad luck.
    """
    rng = random.Random(2026)
    winners = [_play(env, packed, f"sodium,{i + 100:064x}", rng).winner for i in range(16)]
    assert set(winners) == {0, 1}, f"one-sided result: {winners}"


def test_same_seed_reproduces_the_same_battle(env, packed):
    first = _play(env, packed, "sodium," + "7b" * 32, random.Random(4))
    protocol_first = [line for line in env.protocol if not line.startswith("|t:|")]

    second = _play(env, packed, "sodium," + "7b" * 32, random.Random(4))
    protocol_second = [line for line in env.protocol if not line.startswith("|t:|")]

    assert first.winner == second.winner
    assert protocol_first == protocol_second


def test_step_rejects_actions_for_players_that_were_not_asked(env, packed):
    rng = random.Random(1)
    env.reset((packed, packed), seed="sodium," + "9d" * 32)
    with pytest.raises(ValueError):
        env.step({})
    waiting = env.awaiting()
    with pytest.raises(ValueError):
        env.step({p: _random_agent(env, p, rng) for p in waiting} | {9: None})


def test_team_preview_requires_a_team_preview_action(env, packed):
    env.reset((packed, packed), seed="sodium," + "9d" * 32)
    assert env.decision(0) is Decision.TEAM_PREVIEW

    # Enumerating joint actions makes no sense for a pick-N-of-6 decision.
    with pytest.raises(ValueError):
        env.legal_actions(0)

    turn_action = JointAction(slot_actions=(PassAction(), PassAction()))
    with pytest.raises(TypeError):
        env.step({p: turn_action for p in env.awaiting()})


def test_observations_stay_masked_throughout(env, packed):
    _play(env, packed, "sodium," + "2f" * 32, random.Random(5))
    for player in (0, 1):
        observation = env.observation(player)
        for mon in observation.opponent_side.revealed:
            assert 0 <= mon.hp_percent <= 100


def test_finished_battle_cannot_be_stepped_again(env, packed):
    _play(env, packed, "sodium," + "4e" * 32, random.Random(6))
    assert env.terminal
    with pytest.raises(RuntimeError):
        env.step({})
