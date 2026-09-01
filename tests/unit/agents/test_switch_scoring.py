"""Switching: the flat cost, which is no longer the default.

Experiment 0032 turned matchup switching **on** at a horizon of 2, so these
tests construct the agent with `matchup_switching=False` explicitly. They still
earn their place: the flat scorer remains the comparison baseline every
switching measurement is made against, and it needs to keep behaving the way
those measurements assumed.

The history is worth knowing, because the question was answered wrongly three
times. 0004 built a matchup version, tuned its horizon to reproduce the *human*
switch rate, and reverted it. 0027 tested horizon 8 and concluded the agent's
near-zero rate was correct. Both were measuring a real effect at the wrong
point on a monotone curve that crosses even between horizons 2 and 4 -- and
both ran on a harness that never exchanged teams (0031).
"""

import pytest

from champions_ai.agents.heuristic import (
    LOW_HP_FRACTION,
    SWITCH_COST,
    SWITCH_WHEN_WEAKENED_BONUS,
    HeuristicAgent,
)
from champions_ai.dex import Dex
from champions_ai.domain import (
    REGULATION_M_B,
    BattlePokemon,
    Observation,
    ObservedPokemon,
    ObservedSide,
    PokemonSet,
    Side,
    SwitchAction,
)

TYPES = ["Normal", "Fire", "Water"]
CHART = {a: dict.fromkeys(TYPES, 1.0) for a in TYPES}
CHART["Water"]["Fire"] = 2.0
CHART["Fire"]["Water"] = 0.5


def _mon(name, types):
    return {
        "name": name,
        "types": list(types),
        "baseStats": {"hp": 100, "atk": 110, "def": 80, "spa": 110, "spd": 80, "spe": 100},
        "abilities": [],
        "weightkg": 1.0,
        "baseSpecies": name,
    }


def _move(name, move_type):
    return {
        "name": name,
        "type": move_type,
        "category": "Physical",
        "basePower": 90,
        "accuracy": 100,
        "priority": 0,
        "target": "normal",
        "flags": [],
        "secondaries": [],
    }


DEX = Dex.from_payload(
    {
        "species": {
            "firemon": _mon("Firemon", ("Fire",)),
            "watermon": _mon("Watermon", ("Water",)),
            "plainmon": _mon("Plainmon", ("Normal",)),
        },
        "moves": {
            "ember": _move("Ember", "Fire"),
            "splash": _move("Splash", "Water"),
            "bonk": _move("Bonk", "Normal"),
        },
        "types": TYPES,
        "chart": CHART,
    }
)
MOVE_FOR = {"Firemon": "ember", "Watermon": "splash", "Plainmon": "bonk"}


def _battle_mon(species, hp=175, max_hp=175):
    return BattlePokemon(
        pokemon_set=PokemonSet(species=species, level=50, ability="x", moves=(MOVE_FOR[species],)),
        current_hp=hp,
        max_hp=max_hp,
        computed_stats={"atk": 130, "def": 100, "spa": 130, "spd": 100, "spe": 120},
        choosable_moves=(MOVE_FOR[species],),
    )


def _observation(active, bench, foe="Watermon", active_hp=175, active_slots=(0, None)):
    team = (_battle_mon(active, hp=active_hp),) + tuple(_battle_mon(s) for s in bench)
    return Observation(
        regulation=REGULATION_M_B,
        turn=2,
        player=0,
        own_side=Side(team=team, active_slots=active_slots),
        opponent_side=ObservedSide(
            revealed=(ObservedPokemon(species=foe, level=50, hp_percent=100, fainted=False),),
            active_slots=(0, None),
        ),
    )


@pytest.fixture
def agent():
    """The flat scorer, which is now opt-in rather than the default."""
    return HeuristicAgent(DEX, name="test", matchup_switching=False)


@pytest.fixture
def shipped():
    """Whatever the agent actually does out of the box."""
    return HeuristicAgent(DEX, name="shipped")


def test_switching_a_healthy_pokemon_costs_a_turn(agent):
    observation = _observation("Firemon", ["Watermon"], foe="Firemon")
    scored = agent.score_slot_action(observation, 0, SwitchAction(team_index=1))
    assert scored.score == SWITCH_COST
    assert any("costs a turn" in r for r in scored.reasons)


def test_a_pokemon_about_to_be_knocked_out_is_worth_saving(agent):
    healthy = _observation("Firemon", ["Plainmon"], active_hp=175)
    nearly_dead = _observation("Firemon", ["Plainmon"], active_hp=8)
    assert (
        agent.score_slot_action(nearly_dead, 0, SwitchAction(team_index=1)).score
        == SWITCH_COST + SWITCH_WHEN_WEAKENED_BONUS
    )
    assert agent.score_slot_action(healthy, 0, SwitchAction(team_index=1)).score == SWITCH_COST


def test_the_weakened_bonus_applies_at_the_threshold(agent):
    at_threshold = _observation("Firemon", ["Plainmon"], active_hp=int(175 * LOW_HP_FRACTION))
    scored = agent.score_slot_action(at_threshold, 0, SwitchAction(team_index=1))
    assert scored.score == SWITCH_COST + SWITCH_WHEN_WEAKENED_BONUS
    assert any("weakened" in r for r in scored.reasons)


def test_filling_an_empty_slot_is_not_treated_as_giving_up_a_turn(agent):
    """A forced replacement has no turn to surrender, so it must not be charged
    the switch cost -- otherwise every replacement scores as a mistake."""
    observation = _observation("Firemon", ["Watermon"], active_slots=(None, None))
    scored = agent.score_slot_action(observation, 0, SwitchAction(team_index=1))
    assert scored.score == 0.0
    assert "empty slot" in scored.reasons[0]


def test_the_flat_cost_ignores_the_matchup(agent):
    """The flat scorer's known limitation, kept as the baseline's definition:
    a switch into a favourable matchup scores exactly the same as one into an
    awful matchup."""
    into_good = _observation("Plainmon", ["Watermon"], foe="Firemon")
    into_bad = _observation("Plainmon", ["Firemon"], foe="Watermon")
    assert (
        agent.score_slot_action(into_good, 0, SwitchAction(team_index=1)).score
        == agent.score_slot_action(into_bad, 0, SwitchAction(team_index=1)).score
    )


def test_the_shipped_agent_does_consult_the_matchup(shipped):
    """What 0032 changed. Switching into a type advantage must now beat
    switching into a disadvantage, or the horizon is doing nothing."""
    into_good = _observation("Plainmon", ["Watermon"], foe="Firemon")
    into_bad = _observation("Plainmon", ["Firemon"], foe="Watermon")
    good = shipped.score_slot_action(into_good, 0, SwitchAction(team_index=1)).score
    bad = shipped.score_slot_action(into_bad, 0, SwitchAction(team_index=1)).score
    assert good > bad, f"favourable {good} should beat unfavourable {bad}"
