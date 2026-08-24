"""Costs and benefits a move carries besides its damage.

Three fields were dumped and read by nothing:

  has_crash_damage   High Jump Kick takes half a health bar when it *misses*,
                     so a 90% move is not 90% of a good move -- it is 90% of a
                     good move and 10% of a disaster
  self_switch        U-turn, Volt Switch and Flip Turn attack and pivot
  ignore_defensive   Darkest Lariat and Sacred Sword ignore the target's
                     defensive stages, which is the whole reason to bring them
                     into a boosted matchup
"""

import pytest

from champions_ai.agents.heuristic import HeuristicAgent
from champions_ai.dex import Dex
from champions_ai.domain import (
    REGULATION_M_B,
    BattlePokemon,
    Boosts,
    MoveAction,
    Observation,
    ObservedPokemon,
    ObservedSide,
    PokemonSet,
    Side,
    TargetSlot,
)

MOVES = ("plain", "crasher", "pivot", "lariat")


def _move(move_id, **extra):
    return {
        "name": move_id, "type": "Normal", "category": "Physical",
        "basePower": 100, "accuracy": 100, "priority": 0, "target": "normal",
        "flags": [], "secondaries": [], **extra,
    }


def _stats():
    return {"hp": 100, "atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100}


DEX = Dex.from_payload({
    "species": {
        "ours": {"name": "Ours", "types": ["Normal"], "baseStats": _stats(),
                 "abilities": [], "weightkg": 1.0, "baseSpecies": "Ours"},
        "theirs": {"name": "Theirs", "types": ["Normal"], "baseStats": _stats(),
                   "abilities": [], "weightkg": 1.0, "baseSpecies": "Theirs"},
    },
    "moves": {
        "plain": _move("plain", accuracy=90),
        "crasher": _move("crasher", accuracy=90, hasCrashDamage=True),
        "pivot": _move("pivot", selfSwitch=True),
        "lariat": _move("lariat", ignoreDefensive=True),
    },
    "types": ["Normal"], "chart": {"Normal": {"Normal": 1.0}},
})

INDEX = {move_id: i for i, move_id in enumerate(MOVES)}


def _observation(*, our_hp=200, their_boosts=None):
    mine = BattlePokemon(
        pokemon_set=PokemonSet(species="Ours", level=50, ability="x", moves=MOVES),
        current_hp=our_hp, max_hp=200,
        computed_stats={"atk": 150, "def": 100, "spa": 150, "spd": 100, "spe": 100},
        choosable_moves=MOVES,
    )
    return Observation(
        regulation=REGULATION_M_B, turn=2, player=0,
        own_side=Side(team=(mine,), active_slots=(0, None)),
        opponent_side=ObservedSide(
            revealed=(ObservedPokemon(
                species="Theirs", level=50, hp_percent=100, fainted=False,
                boosts=their_boosts or Boosts(),
            ),),
            active_slots=(0, None),
        ),
    )


@pytest.fixture
def agent():
    return HeuristicAgent(DEX, name="test")


def _score(agent, move_id, **kwargs):
    return agent.score_slot_action(
        _observation(**kwargs), 0,
        MoveAction(move_index=INDEX[move_id], target=TargetSlot(side="foe", slot=0)),
    ).score


def test_crash_damage_is_a_real_cost(agent):
    """Identical to the plain move but for the crash, so the gap is the cost."""
    assert _score(agent, "crasher") < _score(agent, "plain")


def test_a_pivot_is_worth_more_when_we_are_nearly_dead(agent):
    healthy = _score(agent, "pivot", our_hp=200)
    weakened = _score(agent, "pivot", our_hp=40)
    assert weakened > healthy


def test_an_ordinary_move_gains_nothing_from_being_weak(agent):
    """Guards the test above: the pivot bonus must not leak onto every move."""
    healthy = _score(agent, "plain", our_hp=200)
    weakened = _score(agent, "plain", our_hp=40)
    assert weakened == pytest.approx(healthy)


def test_ignoring_defensive_stages_beats_a_boosted_target(agent):
    """Against a Pokemon at +2 Defence, the move that ignores it should not
    care, and the one that does not should."""
    plain_fresh = _score(agent, "plain")
    plain_boosted = _score(agent, "plain", their_boosts=Boosts(defense=2))
    lariat_fresh = _score(agent, "lariat")
    lariat_boosted = _score(agent, "lariat", their_boosts=Boosts(defense=2))

    assert plain_boosted < plain_fresh, "an ordinary move is blunted by +2 Def"
    assert lariat_boosted == pytest.approx(lariat_fresh), "Darkest Lariat is not"
