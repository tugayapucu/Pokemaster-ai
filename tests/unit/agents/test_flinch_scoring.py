"""Flinch, and the moves that only work on their first turn out.

Flinch is the one rider whose value depends on turn order: denying a target its
turn is worth nothing if it has already acted. Fake Out's +3 priority is what
makes it reliable, and Rock Slide's 30% only pays when we outspeed.
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
    TargetSlot,
)

TYPES = ["Normal"]


def _move(name, power=100, priority=0, flinch=None):
    entry = {
        "name": name, "type": "Normal", "category": "Physical", "basePower": power,
        "accuracy": 100, "priority": priority, "target": "normal", "flags": [],
        "secondaries": [],
    }
    if flinch:
        entry["secondaries"] = [{"chance": flinch, "volatileStatus": "flinch"}]
    return entry


def _mon(name, spe):
    return {
        "name": name, "types": ["Normal"],
        "baseStats": {"hp": 120, "atk": 120, "def": 80, "spa": 120, "spd": 80, "spe": spe},
        "abilities": [], "weightkg": 1.0, "baseSpecies": name,
    }


PAYLOAD = {
    "species": {"speedy": _mon("Speedy", 200), "sluggish": _mon("Sluggish", 5),
                "foe": _mon("Foe", 100)},
    "moves": {
        "plain": _move("Plain"),
        "shaker": _move("Shaker", flinch=30),
        "fakeout": _move("Fake Out", power=40, priority=3, flinch=100),
    },
    "types": TYPES,
    "chart": {"Normal": {"Normal": 1.0}},
}
DEX = Dex.from_payload(PAYLOAD)
MOVES = ("plain", "shaker", "fakeout")


def _observation(species="Speedy", turns_on_field=1):
    mine = BattlePokemon(
        pokemon_set=PokemonSet(species=species, level=50, ability="x", moves=MOVES),
        current_hp=195, max_hp=195,
        computed_stats={"atk": 140, "def": 100, "spa": 140, "spd": 100,
                        "spe": 220 if species == "Speedy" else 25},
        choosable_moves=MOVES,
        turns_on_field=turns_on_field,
    )
    return Observation(
        regulation=REGULATION_M_B, turn=1, player=0,
        own_side=Side(team=(mine,), active_slots=(0, None)),
        opponent_side=ObservedSide(
            revealed=(ObservedPokemon(species="Foe", level=50, hp_percent=100, fainted=False),),
            active_slots=(0, None),
        ),
    )


@pytest.fixture
def agent():
    return HeuristicAgent(DEX, name="test")


def _score(agent, observation, move):
    index = observation.own_side.team[0].selectable_moves.index(move)
    return agent.score_slot_action(
        observation, 0, MoveAction(move_index=index, target=TargetSlot(side="foe", slot=0))
    )


def test_a_flinch_is_worth_something_when_we_move_first(agent):
    fast = _observation("Speedy")
    assert _score(agent, fast, "shaker").score > _score(agent, fast, "plain").score


def test_a_flinch_is_worth_nothing_when_we_move_second(agent):
    """The target has already acted, so denying its turn denies nothing."""
    slow = _observation("Sluggish")
    scored = _score(agent, slow, "shaker")
    assert scored.score == pytest.approx(_score(agent, slow, "plain").score)
    assert any("wasted moving second" in r for r in scored.reasons)


def test_priority_makes_a_flinch_reliable_even_when_slow(agent):
    """Fake Out's +3 is exactly why it works on a slow Pokemon."""
    slow = _observation("Sluggish")
    assert any("flinch" in r for r in _score(agent, slow, "fakeout").reasons)


def test_fake_out_is_rejected_after_its_first_turn_out(agent):
    """The engine refuses it at runtime and never reports it as disabled, so
    nothing upstream filters it -- a human in our own data pressed it on turn
    two and got the failure hint."""
    late = _observation("Speedy", turns_on_field=3)
    scored = _score(agent, late, "fakeout")
    assert scored.score < 0
    assert any("first turn out" in r for r in scored.reasons)


def test_fake_out_is_fine_on_the_turn_it_arrives(agent):
    fresh = _observation("Speedy", turns_on_field=1)
    assert _score(agent, fresh, "fakeout").score > 0


def test_an_unknown_arrival_does_not_block_the_move(agent):
    """turns_on_field of zero means we never saw it arrive, which is unknown
    rather than 'long ago' -- blocking a legal move on missing data is worse
    than allowing an illegal one."""
    unknown = _observation("Speedy", turns_on_field=0)
    assert _score(agent, unknown, "fakeout").score > 0
