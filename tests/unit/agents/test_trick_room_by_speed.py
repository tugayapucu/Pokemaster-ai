"""Trick Room priced by what the speed flip does for us, not at a flat value.

The flat price had two faults. It paid the same for setting Trick Room with a
fast side as with a slow one. And it scored the move at nothing when Trick
Room was already up -- but the engine's `onFieldRestart` calls
`removePseudoWeather('trickroom')`, so using it then *ends* it. Against an
opponent's Trick Room that is the most valuable thing the move does.

Every test below uses one of our Pokemon against one of theirs, so a single
pairing decides the share: 1 when we move first, 0 when they do, 0.5 on a tie.
Our Speed is set directly; theirs is whatever the agent believes it to be,
which the tie test reads back rather than assuming.
"""

import pytest

from champions_ai.agents.heuristic import PSEUDO_WEATHER_VALUE, HeuristicAgent
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

FLAT = PSEUDO_WEATHER_VALUE["trickroom"]
SLOW, FAST = 40, 400


def _species(name):
    return {
        "name": name, "types": ["Normal"], "abilities": [], "weightkg": 1.0,
        "baseSpecies": name,
        "baseStats": {"hp": 100, "atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
    }


DEX = Dex.from_payload({
    "species": {"ours": _species("Ours"), "theirs": _species("Theirs")},
    "moves": {
        "trickroom": {
            "name": "Trick Room", "type": "Psychic", "category": "Status", "basePower": 0,
            "accuracy": 100, "priority": -7, "target": "all", "flags": [],
            "secondaries": [], "pseudoWeather": "trickroom",
        },
    },
    "types": ["Normal", "Psychic"],
    "chart": {a: {"Normal": 1.0, "Psychic": 1.0} for a in ("Normal", "Psychic")},
})
TRICK_ROOM = DEX.get_move("trickroom")


def _observation(our_speed, *, up=False, foe_on_field=True):
    mine = BattlePokemon(
        pokemon_set=PokemonSet(species="Ours", level=50, ability="x", moves=("trickroom",)),
        current_hp=200, max_hp=200,
        computed_stats={"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": our_speed},
        choosable_moves=("trickroom",),
    )
    return Observation(
        regulation=REGULATION_M_B, turn=2, player=0,
        own_side=Side(team=(mine,), active_slots=(0, None)),
        opponent_side=ObservedSide(
            revealed=(ObservedPokemon(species="Theirs", level=50, hp_percent=100, fainted=False),),
            active_slots=(0 if foe_on_field else None, None),
        ),
        field_conditions={"trickroom": 0} if up else {},
    )


def _value(agent, observation):
    return agent._field_value(
        TRICK_ROOM, observation, 0, observation.own_side.team[0], []
    )


@pytest.fixture
def by_speed():
    return HeuristicAgent(DEX, trick_room_by_speed=True)


def test_the_premise_holds_our_slow_side_is_slower_and_fast_side_faster(by_speed):
    """Guards the fixture: if the believed opponent Speed ever moved outside
    SLOW..FAST, every sign below would be testing nothing."""
    theirs = by_speed._opponent_stats(DEX.get_species("Theirs"))["spe"]
    assert SLOW < theirs < FAST


def test_setting_it_with_a_slower_side_is_worth_the_full_price(by_speed):
    assert _value(by_speed, _observation(SLOW)) == pytest.approx(FLAT)


def test_setting_it_with_a_faster_side_costs_the_full_price(by_speed):
    """The flat price paid +55 here. Handing the opponent the speed order is
    the opposite of an advantage."""
    assert _value(by_speed, _observation(FAST)) == pytest.approx(-FLAT)


def test_ending_their_trick_room_with_a_faster_side_is_worth_the_full_price(by_speed):
    """The case the flat price could not see at all: it scored an active Trick
    Room at zero, and using the move is how the engine ends it."""
    assert _value(by_speed, _observation(FAST, up=True)) == pytest.approx(FLAT)


def test_ending_our_own_trick_room_costs_the_full_price(by_speed):
    assert _value(by_speed, _observation(SLOW, up=True)) == pytest.approx(-FLAT)


def test_a_speed_tie_is_unchanged_by_the_flip(by_speed):
    theirs = by_speed._opponent_stats(DEX.get_species("Theirs"))["spe"]
    assert _value(by_speed, _observation(theirs)) == pytest.approx(0.0)


def test_nothing_on_the_other_side_means_nothing_to_flip(by_speed):
    assert _value(by_speed, _observation(SLOW, foe_on_field=False)) == 0.0


def test_the_speed_control_scale_still_applies():
    agent = HeuristicAgent(DEX, trick_room_by_speed=True, speed_control_scale=2.0)
    assert _value(agent, _observation(FAST)) == pytest.approx(-2.0 * FLAT)


def test_off_by_default_and_the_flat_price_is_untouched():
    """Speed-blind when off: the same +55 for a slow side and a fast one, and
    nothing at all once it is up."""
    agent = HeuristicAgent(DEX)
    assert _value(agent, _observation(SLOW)) == pytest.approx(FLAT)
    assert _value(agent, _observation(FAST)) == pytest.approx(FLAT)
    assert _value(agent, _observation(FAST, up=True)) == 0.0


def test_the_whole_move_score_follows_the_sign(by_speed):
    """Through the public scorer, not only the helper: with the flag on, a
    slower side prefers Trick Room more than a faster one does."""
    slow = by_speed.score_slot_action(_observation(SLOW), 0, MoveAction(move_index=0))
    fast = by_speed.score_slot_action(_observation(FAST), 0, MoveAction(move_index=0))
    assert slow.score > fast.score
