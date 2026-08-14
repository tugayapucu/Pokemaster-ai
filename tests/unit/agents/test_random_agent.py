import pytest

from champions_ai.agents import Agent, RandomAgent
from champions_ai.domain import (
    REGULATION_M_B,
    JointAction,
    MoveAction,
    PassAction,
    PokemonSet,
    RevealedPokemon,
    StatSpread,
    Team,
    TeamPreview,
)


def _team() -> Team:
    return Team(
        pokemon=tuple(
            PokemonSet(
                species=f"species{i}",
                level=50,
                ability="a",
                moves=("tackle",),
                stats=StatSpread(),
            )
            for i in range(6)
        )
    )


def _preview() -> TeamPreview:
    return TeamPreview(
        regulation=REGULATION_M_B,
        own_team=_team(),
        opponent_team=tuple(
            RevealedPokemon(species=f"foe{i}", level=50) for i in range(6)
        ),
    )


OPTIONS = (
    JointAction(slot_actions=(MoveAction(move_index=0), PassAction())),
    JointAction(slot_actions=(MoveAction(move_index=1), PassAction())),
    JointAction(slot_actions=(PassAction(), PassAction())),
)


def test_is_an_agent():
    assert isinstance(RandomAgent(), Agent)


def test_always_returns_one_of_the_offered_actions():
    agent = RandomAgent(seed=7)
    for _ in range(30):
        assert agent.select_action(None, OPTIONS) in OPTIONS


def test_same_seed_gives_the_same_choices():
    """Evaluation reproducibility depends on this."""
    first = [RandomAgent(seed=3).select_action(None, OPTIONS) for _ in range(1)]
    second = [RandomAgent(seed=3).select_action(None, OPTIONS) for _ in range(1)]
    assert first == second

    a, b = RandomAgent(seed=3), RandomAgent(seed=3)
    assert [a.select_action(None, OPTIONS) for _ in range(20)] == [
        b.select_action(None, OPTIONS) for _ in range(20)
    ]


def test_different_seeds_diverge():
    a = [RandomAgent(seed=1).select_action(None, OPTIONS) for _ in range(1)]
    many_a = RandomAgent(seed=1)
    many_b = RandomAgent(seed=999)
    choices_a = [many_a.select_action(None, OPTIONS) for _ in range(30)]
    choices_b = [many_b.select_action(None, OPTIONS) for _ in range(30)]
    assert choices_a != choices_b
    assert a  # sanity


def test_does_not_draw_from_the_global_random_state():
    """A shared generator would make an evaluation run depend on unrelated code."""
    import random

    random.seed(0)
    agent = RandomAgent(seed=5)
    before = [agent.select_action(None, OPTIONS) for _ in range(10)]

    random.seed(12345)
    agent_again = RandomAgent(seed=5)
    after = [agent_again.select_action(None, OPTIONS) for _ in range(10)]

    assert before == after


def test_team_preview_picks_the_right_number_without_repeats():
    action = RandomAgent(seed=11).select_team_preview(_preview(), 4)
    assert len(action.picks) == 4
    assert len(set(action.picks)) == 4
    assert all(0 <= pick < 6 for pick in action.picks)


def test_base_agent_defaults_to_the_declared_order():
    class Minimal(Agent):
        def select_action(self, observation, legal_actions):
            return legal_actions[0]

    assert Minimal().select_team_preview(_preview(), 4).picks == (0, 1, 2, 3)


def test_agent_interface_requires_select_action():
    with pytest.raises(TypeError):
        Agent()
