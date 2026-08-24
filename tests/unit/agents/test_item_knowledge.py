"""What we know about an opponent's item, and what we may assume.

`revealed_item is None` used to mean two different things -- "we have never
seen an item" and "we watched it get used up" -- and only the second says they
are empty-handed. Almost every Pokemon in this format carries something, so
collapsing the two priced Knock Off at its floor against nearly every target.

There are three states, and the third has a wrinkle: a species with a Mega
Stone is most likely holding the one item that *cannot* be taken off it.
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


def _stats():
    return {"hp": 100, "atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100}


DEX = Dex.from_payload({
    "species": {
        "ours": {"name": "Ours", "types": ["Normal"], "baseStats": _stats(),
                 "abilities": [], "weightkg": 1.0, "baseSpecies": "Ours"},
        "plain": {"name": "Plain", "types": ["Normal"], "baseStats": _stats(),
                  "abilities": [], "weightkg": 1.0, "baseSpecies": "Plain"},
        # A species with a Mega Stone in this dex.
        "megamon": {"name": "Megamon", "types": ["Normal"], "baseStats": _stats(),
                    "abilities": [], "weightkg": 1.0, "baseSpecies": "Megamon"},
    },
    "moves": {
        "knockoff": {
            "name": "Knock Off", "type": "Dark", "category": "Physical",
            "basePower": 65, "accuracy": 100, "priority": 0, "target": "normal",
            "flags": [], "secondaries": [],
        },
    },
    "items": {
        "lifeorb": {"name": "Life Orb"},
        "megamonite": {"name": "Megamonite", "megaStone": "Megamon"},
    },
    "types": ["Normal", "Dark"],
    "chart": {"Normal": {"Normal": 1.0, "Dark": 1.0}, "Dark": {"Normal": 1.0, "Dark": 1.0}},
})


def _observation(*, foe="Plain", revealed_item=None, item_consumed=False):
    mine = BattlePokemon(
        pokemon_set=PokemonSet(species="Ours", level=50, ability="x", moves=("knockoff",)),
        current_hp=200, max_hp=200,
        computed_stats={"atk": 150, "def": 100, "spa": 150, "spd": 100, "spe": 100},
        choosable_moves=("knockoff",),
    )
    return Observation(
        regulation=REGULATION_M_B, turn=2, player=0,
        own_side=Side(team=(mine,), active_slots=(0, None)),
        opponent_side=ObservedSide(
            revealed=(ObservedPokemon(
                species=foe, level=50, hp_percent=100, fainted=False,
                revealed_item=revealed_item, item_consumed=item_consumed,
            ),),
            active_slots=(0, None),
        ),
    )


@pytest.fixture
def agent():
    return HeuristicAgent(DEX, name="test")


def _score(agent, **kwargs):
    return agent.score_slot_action(
        _observation(**kwargs), 0,
        MoveAction(move_index=0, target=TargetSlot(side="foe", slot=0)),
    ).score


# ------------------------------------------------------ the three item states


def test_an_item_we_watched_leave_means_there_is_nothing_to_take(agent):
    gone = _score(agent, item_consumed=True)
    unseen = _score(agent, item_consumed=False)
    assert gone < unseen, "Knock Off should be weaker once the item is gone"


def test_an_item_we_have_seen_is_checked_properly(agent):
    seen = _score(agent, revealed_item="lifeorb")
    gone = _score(agent, item_consumed=True)
    assert seen > gone


def test_an_unseen_item_is_assumed_present(agent):
    """Not seeing one is not evidence of absence -- almost every Pokemon in
    this format carries something."""
    unseen = _score(agent)
    gone = _score(agent, item_consumed=True)
    assert unseen > gone


def test_a_mega_capable_species_is_assumed_to_hold_its_own_stone(agent):
    """The one item it is most likely holding is the one that cannot be taken
    off it, so an unseen item there earns no boost."""
    mega = _score(agent, foe="Megamon")
    plain = _score(agent, foe="Plain")
    assert mega < plain


def test_a_mega_species_holding_something_else_can_still_be_knocked(agent):
    """The assumption only applies while the item is unknown."""
    revealed = _score(agent, foe="Megamon", revealed_item="lifeorb")
    assumed = _score(agent, foe="Megamon")
    assert revealed > assumed


# --------------------------------------------------------------- the dex side


def test_the_dex_finds_the_stone_for_a_species():
    assert DEX.mega_stone_for(DEX.get_species("Megamon")).item_id == "megamonite"
    assert DEX.mega_stone_for(DEX.get_species("Plain")) is None


def test_may_hold_item_is_true_until_we_watch_one_go():
    fresh = ObservedPokemon(species="Plain", level=50, hp_percent=100, fainted=False)
    spent = ObservedPokemon(species="Plain", level=50, hp_percent=100, fainted=False,
                            item_consumed=True)
    assert fresh.may_hold_item
    assert not spent.may_hold_item
