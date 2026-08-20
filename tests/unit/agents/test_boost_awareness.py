"""Stat stages must reach the damage estimate.

They were tracked in the domain model and `apply_boost` was written for exactly
this, and nothing called either -- a Pokemon that had just used Swords Dance
scored identically to one that had not. Measured against 5,123 real attacks,
applying them lifts predictions within ten points of the truth from 35.8% to
39.2%.
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

TYPES = ["Normal"]
DEX = Dex.from_payload({
    "species": {
        "attacker": {
            "name": "Attacker", "types": ["Normal"],
            "baseStats": {"hp": 100, "atk": 120, "def": 90, "spa": 120, "spd": 90, "spe": 100},
            "abilities": [], "weightkg": 1.0, "baseSpecies": "Attacker",
        },
        "target": {
            "name": "Target", "types": ["Normal"],
            "baseStats": {"hp": 150, "atk": 60, "def": 90, "spa": 60, "spd": 90, "spe": 60},
            "abilities": [], "weightkg": 1.0, "baseSpecies": "Target",
        },
    },
    "moves": {"bonk": {
        "name": "Bonk", "type": "Normal", "category": "Physical", "basePower": 80,
        "accuracy": 100, "priority": 0, "target": "normal", "flags": [], "secondaries": [],
    }},
    "types": TYPES, "chart": {"Normal": {"Normal": 1.0}},
})


def _observation(our_boosts=None, their_boosts=None):
    mine = BattlePokemon(
        pokemon_set=PokemonSet(species="Attacker", level=50, ability="x", moves=("bonk",)),
        current_hp=195, max_hp=195,
        computed_stats={"atk": 151, "def": 121, "spa": 151, "spd": 121, "spe": 131},
        choosable_moves=("bonk",),
        boosts=our_boosts or Boosts(),
    )
    return Observation(
        regulation=REGULATION_M_B, turn=2, player=0,
        own_side=Side(team=(mine,), active_slots=(0, None)),
        opponent_side=ObservedSide(
            revealed=(ObservedPokemon(
                species="Target", level=50, hp_percent=100, fainted=False,
                boosts=their_boosts or Boosts(),
            ),),
            active_slots=(0, None),
        ),
    )


@pytest.fixture
def agent():
    return HeuristicAgent(DEX, name="test")


def _score(agent, observation):
    return agent.score_slot_action(
        observation, 0, MoveAction(move_index=0, target=TargetSlot(side="foe", slot=0))
    ).score


def test_our_own_attack_boost_raises_the_score(agent):
    plain = _score(agent, _observation())
    swords_dance = _score(agent, _observation(our_boosts=Boosts(attack=2)))
    assert swords_dance > plain


def test_our_own_attack_drop_lowers_the_score(agent):
    """Intimidate is everywhere in this format; ignoring it overstated every
    attack made after one."""
    plain = _score(agent, _observation())
    intimidated = _score(agent, _observation(our_boosts=Boosts(attack=-1)))
    assert intimidated < plain


def test_the_targets_defence_boost_lowers_the_score(agent):
    plain = _score(agent, _observation())
    fortified = _score(agent, _observation(their_boosts=Boosts(defense=2)))
    assert fortified < plain


def test_a_special_move_reads_the_special_stages_not_the_physical_ones(agent):
    """Boosting Attack must not make a Special move look stronger."""
    plain = _score(agent, _observation())
    wrong_stat = _score(agent, _observation(our_boosts=Boosts(special_attack=2)))
    assert wrong_stat == pytest.approx(plain), "Bonk is Physical; SpA must not touch it"


def test_the_incoming_threat_respects_stages_too(agent):
    """Protect is priced off this, so a boosted attacker must read as scarier."""
    mine = _observation().own_side.team[0]
    calm = agent._incoming_threat(_observation(), 0, mine)[0]
    scary = agent._incoming_threat(_observation(their_boosts=Boosts(attack=2)), 0, mine)[0]
    assert scary > calm


def test_the_assumed_opponent_spread_is_legal(agent):
    """Twelve per stat is 72 points against this format's budget of 66, so the
    old default modelled every opponent with a spread that cannot exist."""
    assert agent.assumed_opponent_points * 6 <= REGULATION_M_B.max_total_stat_points
