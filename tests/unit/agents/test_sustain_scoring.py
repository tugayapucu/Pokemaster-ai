"""Drain and recoil: HP the move moves onto or off our own bar.

Priced in the same currency as damage dealt, because that is what they are.
Before this, Flare Blitz's 33% recoil and Drain Punch's 50% heal were both
invisible, so one was overrated and the other underrated.
"""

import pytest

from champions_ai.agents.heuristic import HeuristicAgent
from champions_ai.dex import Dex
from champions_ai.domain import (
    REGULATION_M_B,
    BattlePokemon,
    MoveAction,
    Observation,
    ObservedPokemon,
    ObservedSide,
    PokemonSet,
    Side,
)

TYPES = ["Normal"]


def _attack(name, **extra):
    return {
        "name": name, "type": "Normal", "category": "Physical", "basePower": 100,
        "accuracy": 100, "priority": 0, "target": "normal", "flags": [], **extra,
    }


PAYLOAD = {
    "species": {
        "attacker": {
            "name": "Attacker", "types": ["Normal"],
            "baseStats": {"hp": 100, "atk": 150, "def": 80, "spa": 150, "spd": 80, "spe": 100},
            "abilities": [], "weightkg": 1.0, "baseSpecies": "Attacker",
        },
        "target": {
            "name": "Target", "types": ["Normal"],
            "baseStats": {"hp": 200, "atk": 50, "def": 80, "spa": 50, "spd": 80, "spe": 50},
            "abilities": [], "weightkg": 1.0, "baseSpecies": "Target",
        },
    },
    "moves": {
        "plain": _attack("Plain"),
        "drainer": _attack("Drainer", drain=[1, 2]),
        "reckless": _attack("Reckless", recoil=[33, 100]),
    },
    "types": TYPES,
    "chart": {"Normal": {"Normal": 1.0}},
}

DEX = Dex.from_payload(PAYLOAD)
MOVES = ("plain", "drainer", "reckless")


def _observation(current_hp=200, max_hp=200):
    mine = BattlePokemon(
        pokemon_set=PokemonSet(species="Attacker", level=50, ability="x", moves=MOVES),
        current_hp=current_hp,
        max_hp=max_hp,
        computed_stats={"atk": 150, "def": 80, "spa": 150, "spd": 80, "spe": 100},
        choosable_moves=MOVES,
    )
    return Observation(
        regulation=REGULATION_M_B,
        turn=1,
        player=0,
        own_side=Side(team=(mine,), active_slots=(0, None)),
        opponent_side=ObservedSide(
            revealed=(ObservedPokemon(species="Target", level=50, hp_percent=100, fainted=False),),
            active_slots=(0, None),
        ),
    )


@pytest.fixture
def agent():
    return HeuristicAgent(DEX, name="test")


def _score(agent, observation, index):
    from champions_ai.domain import TargetSlot
    return agent.score_slot_action(
        observation, 0, MoveAction(move_index=index, target=TargetSlot(side="foe", slot=0))
    )


def test_recoil_makes_an_otherwise_identical_move_worse(agent):
    observation = _observation()
    assert _score(agent, observation, 2).score < _score(agent, observation, 0).score


def test_drain_makes_an_otherwise_identical_move_better_when_hurt(agent):
    observation = _observation(current_hp=100)
    assert _score(agent, observation, 1).score > _score(agent, observation, 0).score


def test_drain_is_worth_nothing_at_full_health(agent):
    """Healing above full is wasted, and the reason should say so."""
    observation = _observation(current_hp=200)
    drained = _score(agent, observation, 1)
    assert drained.score == pytest.approx(_score(agent, observation, 0).score)
    assert any("wasted" in reason for reason in drained.reasons)


def test_recoil_that_would_faint_us_is_called_out(agent):
    observation = _observation(current_hp=5)
    reasons = _score(agent, observation, 2).reasons
    assert any("knock it out" in reason for reason in reasons)


def test_recoil_cannot_cost_more_hp_than_we_have(agent):
    """A 33% recoil on a big hit must not read as losing several health bars."""
    observation = _observation(current_hp=5, max_hp=200)
    scored = _score(agent, observation, 2)
    plain = _score(agent, observation, 0)
    # The loss is bounded by the 5 HP actually present, not by the damage dealt.
    assert plain.score - scored.score < 10


def test_a_move_with_neither_is_untouched(agent):
    scored = _score(agent, _observation(), 0)
    assert not any("recoil" in r or "heals" in r for r in scored.reasons)
