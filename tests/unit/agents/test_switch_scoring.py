"""Switching, priced by the matchup it buys.

The old scoring was a flat cost plus a bonus when weakened, which made
switching almost never worth it: rated humans switch on 10.7% of decisions and
that agent on 1.8%, agreeing on 11 of 117 switch labels.
"""

import pytest

from champions_ai.agents.heuristic import HeuristicAgent
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
        "name": name, "types": list(types),
        "baseStats": {"hp": 100, "atk": 110, "def": 80, "spa": 110, "spd": 80, "spe": 100},
        "abilities": [], "weightkg": 1.0, "baseSpecies": name,
    }


def _move(name, move_type):
    return {
        "name": name, "type": move_type, "category": "Physical", "basePower": 90,
        "accuracy": 100, "priority": 0, "target": "normal", "flags": [], "secondaries": [],
    }


DEX = Dex.from_payload({
    "species": {"firemon": _mon("Firemon", ("Fire",)),
                "watermon": _mon("Watermon", ("Water",)),
                "plainmon": _mon("Plainmon", ("Normal",))},
    "moves": {"ember": _move("Ember", "Fire"), "splash": _move("Splash", "Water"),
              "bonk": _move("Bonk", "Normal")},
    "types": TYPES, "chart": CHART,
})
MOVE_FOR = {"Firemon": "ember", "Watermon": "splash", "Plainmon": "bonk"}
STATS = {"atk": 130, "def": 100, "spa": 130, "spd": 100, "spe": 120}


def _battle_mon(species, hp=175, max_hp=175):
    return BattlePokemon(
        pokemon_set=PokemonSet(species=species, level=50, ability="x",
                               moves=(MOVE_FOR[species],)),
        current_hp=hp, max_hp=max_hp,
        computed_stats=dict(STATS),
        choosable_moves=(MOVE_FOR[species],),
    )


def _observation(active, bench, foe="Watermon", active_hp=175):
    team = (_battle_mon(active, hp=active_hp),) + tuple(_battle_mon(s) for s in bench)
    return Observation(
        regulation=REGULATION_M_B, turn=2, player=0,
        own_side=Side(team=team, active_slots=(0, None)),
        opponent_side=ObservedSide(
            revealed=(ObservedPokemon(species=foe, level=50, hp_percent=100, fainted=False),),
            active_slots=(0, None),
        ),
    )


@pytest.fixture
def agent():
    return HeuristicAgent(DEX, name="test")


def test_switching_into_a_better_matchup_beats_switching_into_a_worse_one(agent):
    """Against a Firemon, our Watermon both hits for double and takes half.

    The foe is deliberately Fire rather than Water: Water into Water and Normal
    into Water are both neutral in this chart, so that pairing would compare two
    genuinely identical options and assert a difference that does not exist.
    """
    observation = _observation("Firemon", ["Watermon", "Plainmon"], foe="Firemon")
    into_water = agent.score_slot_action(observation, 0, SwitchAction(team_index=1)).score
    into_plain = agent.score_slot_action(observation, 0, SwitchAction(team_index=2)).score
    assert into_water > into_plain


def test_switching_out_of_a_good_matchup_is_unattractive(agent):
    """Already winning the matchup, so giving up a turn to change it is a loss."""
    observation = _observation("Watermon", ["Firemon"], foe="Firemon")
    assert agent.score_slot_action(observation, 0, SwitchAction(team_index=1)).score < 0


def test_a_pokemon_about_to_be_knocked_out_is_worth_saving(agent):
    healthy = _observation("Firemon", ["Plainmon"], foe="Watermon", active_hp=175)
    nearly_dead = _observation("Firemon", ["Plainmon"], foe="Watermon", active_hp=8)
    assert (
        agent.score_slot_action(nearly_dead, 0, SwitchAction(team_index=1)).score
        > agent.score_slot_action(healthy, 0, SwitchAction(team_index=1)).score
    )


def test_filling_an_empty_slot_picks_the_best_placed_pokemon(agent):
    """A forced replacement has no turn to give up, so only the matchup counts."""
    team = (_battle_mon("Watermon"), _battle_mon("Firemon"))
    observation = Observation(
        regulation=REGULATION_M_B, turn=2, player=0,
        own_side=Side(team=team, active_slots=(None, None)),
        opponent_side=ObservedSide(
            revealed=(ObservedPokemon(species="Watermon", level=50, hp_percent=100,
                                      fainted=False),),
            active_slots=(0, None),
        ),
    )
    water = agent.score_slot_action(observation, 0, SwitchAction(team_index=0))
    fire = agent.score_slot_action(observation, 0, SwitchAction(team_index=1))
    assert water.score > fire.score
    assert "best placed" in water.reasons[0]


def test_the_reason_names_both_pokemon(agent):
    observation = _observation("Firemon", ["Watermon"], foe="Firemon")
    reasons = agent.score_slot_action(observation, 0, SwitchAction(team_index=1)).reasons
    assert any("Watermon" in r and "Firemon" in r for r in reasons)
    assert any("gives up" in r for r in reasons)
