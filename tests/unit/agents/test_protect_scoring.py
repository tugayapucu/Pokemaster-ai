"""Protect, priced by what it stops rather than by our own HP bar.

The old scoring was a flat value plus a bonus when weakened, which could not
express the two cases that matter: a healthy Pokemon facing a knockout should
protect, and a weakened one facing nothing should not. Measured against real
humans, it protected almost never (experiment 0002).
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

TYPES = ["Normal", "Fire", "Water", "Fighting"]


def _species(name, hp, atk, spa, types):
    return {
        "name": name,
        "types": list(types),
        "baseStats": {"hp": hp, "atk": atk, "def": 80, "spa": spa, "spd": 80, "spe": 80},
        "abilities": [],
        "weightkg": 1.0,
        "baseSpecies": name,
    }


PAYLOAD = {
        "species": {
            # A wall and a monster, so "how hard does this hit" is unmistakable.
            "pillow": _species("Pillow", 100, 20, 20, ("Normal",)),
            "hammer": _species("Hammer", 100, 200, 200, ("Fighting",)),
        },
        "moves": {
            "protect": {
                "name": "Protect", "type": "Normal", "category": "Status",
                "basePower": 0, "accuracy": None, "priority": 4,
                "target": "self", "flags": [],
            },
            "tackle": {
                "name": "Tackle", "type": "Normal", "category": "Physical",
                "basePower": 40, "accuracy": 100, "priority": 0,
                "target": "normal", "flags": [],
            },
        },
        "types": TYPES,
    # Fighting hits Normal hard; everything else neutral.
    "chart": {
        a: {d: (2.0 if (a, d) == ("Fighting", "Normal") else 1.0) for d in TYPES}
        for a in TYPES
    },
}

DEX = Dex.from_payload(PAYLOAD)


def _mine(species="Pillow", hp=200, max_hp=200, streak=0, moves=("protect", "tackle")):
    return BattlePokemon(
        pokemon_set=PokemonSet(species=species, level=50, ability="x", moves=moves),
        current_hp=hp,
        max_hp=max_hp,
        computed_stats={"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
        choosable_moves=moves,
        protect_streak=streak,
    )


def _foe(species="Hammer", revealed=(), fainted=False):
    return ObservedPokemon(
        species=species,
        level=50,
        hp_percent=0 if fainted else 100,
        fainted=fainted,
        revealed_moves=frozenset(revealed),
    )


def _observation(mine=None, foes=(("Hammer", ()),), foe_active=(0,)):
    revealed = tuple(_foe(species, moves) for species, moves in foes)
    return Observation(
        regulation=REGULATION_M_B,
        turn=1,
        player=0,
        own_side=Side(team=(mine or _mine(),), active_slots=(0, None)),
        opponent_side=ObservedSide(
            revealed=revealed,
            active_slots=tuple(foe_active) + (None,) * (2 - len(foe_active)),
        ),
    )


@pytest.fixture
def agent():
    return HeuristicAgent(DEX, name="test")


def _protect_score(agent, observation):
    return agent.score_slot_action(observation, 0, MoveAction(move_index=0)).score


# ------------------------------------------------------- priced by the threat


def test_protect_is_worth_more_against_a_bigger_threat(agent):
    """The whole point: value tracks the incoming hit, not our HP bar."""
    against_monster = _protect_score(agent, _observation(foes=(("Hammer", ()),)))
    against_pillow = _protect_score(agent, _observation(foes=(("Pillow", ()),)))
    assert against_monster > against_pillow


def test_an_opponent_with_no_revealed_moves_is_not_treated_as_harmless(agent):
    """Assuming an unseen moveset is harmless is why search was inert (0001)."""
    unseen = _protect_score(agent, _observation(foes=(("Hammer", ()),)))
    assert unseen > 0, "an unrevealed attacker must still register as a threat"


def test_a_revealed_move_is_used_when_one_exists(agent):
    seen = agent._incoming_threat(
        _observation(foes=(("Hammer", ("tackle",)),)), 0, _mine()
    )
    assert seen[2].endswith("seen")

    assumed = agent._incoming_threat(_observation(foes=(("Hammer", ()),)), 0, _mine())
    assert assumed[2].endswith("assumed")


def test_a_fainted_opponent_threatens_nothing(agent):
    observation = Observation(
        regulation=REGULATION_M_B,
        turn=1,
        player=0,
        own_side=Side(team=(_mine(),), active_slots=(0, None)),
        opponent_side=ObservedSide(
            revealed=(_foe("Hammer", fainted=True),), active_slots=(0, None)
        ),
    )
    fraction, _, _ = agent._incoming_threat(observation, 0, _mine())
    assert fraction == 0.0


def test_an_empty_field_threatens_nothing(agent):
    observation = Observation(
        regulation=REGULATION_M_B,
        turn=1,
        player=0,
        own_side=Side(team=(_mine(),), active_slots=(0, None)),
        opponent_side=ObservedSide(revealed=(), active_slots=(None, None)),
    )
    fraction, would_ko, _ = agent._incoming_threat(observation, 0, _mine())
    assert (fraction, would_ko) == (0.0, False)


def test_the_worst_of_two_active_opponents_is_what_counts(agent):
    both = _protect_score(
        agent, _observation(foes=(("Pillow", ()), ("Hammer", ())), foe_active=(0, 1))
    )
    only_weak = _protect_score(agent, _observation(foes=(("Pillow", ()),)))
    assert both > only_weak


# ----------------------------------------------------- discounted by the streak


def test_protecting_again_is_worth_much_less(agent):
    """Each consecutive use succeeds a third as often -- the engine's own rule."""
    first = _protect_score(agent, _observation(mine=_mine(streak=0)))
    second = _protect_score(agent, _observation(mine=_mine(streak=1)))
    third = _protect_score(agent, _observation(mine=_mine(streak=2)))
    assert first > second > third


def test_a_long_streak_makes_protect_a_bad_idea(agent):
    """It should fall below doing nothing, so the agent stops."""
    assert _protect_score(agent, _observation(mine=_mine(streak=3))) < 0


# --------------------------------------------------------------- explanations


def test_the_reason_says_what_it_would_block(agent):
    scored = agent.score_slot_action(_observation(), 0, MoveAction(move_index=0))
    assert "block" in scored.reasons[0]
    assert "Hammer" in scored.reasons[0]


def test_the_reason_admits_when_the_threat_is_only_assumed(agent):
    scored = agent.score_slot_action(_observation(), 0, MoveAction(move_index=0))
    assert "assumed" in scored.reasons[0]


def test_a_repeat_is_explained_as_likely_to_fail(agent):
    scored = agent.score_slot_action(
        _observation(mine=_mine(streak=1)), 0, MoveAction(move_index=0)
    )
    assert any("running" in reason for reason in scored.reasons)


# ------------------------------------------------------- the whole family, not one move


def test_spiky_shield_is_scored_like_protect(agent):
    """The old code matched the literal id "protect" and missed every relative."""
    dex = Dex.from_payload(
        {
            **PAYLOAD,
            "moves": {
                **PAYLOAD["moves"],
                "spikyshield": {
                    "name": "Spiky Shield", "type": "Normal", "category": "Status",
                    "basePower": 0, "accuracy": None, "priority": 4,
                    "target": "self", "flags": [],
                },
            },
        }
    )
    protective = HeuristicAgent(dex, name="test")
    observation = _observation(mine=_mine(moves=("spikyshield", "tackle")))
    scored = protective.score_slot_action(observation, 0, MoveAction(move_index=0))
    assert "block" in scored.reasons[0], "Spiky Shield must be priced as protection"
