"""What a status move is worth.

All 175 status moves in this dex except Protect used to score a flat 12.0, so
Swords Dance, Thunder Wave, Recover and Trick Room were indistinguishable --
and a *redundant* one scored the same as a fresh one.

The prices are not new inventions: a stat stage uses STAT_STAGE_VALUE, a
status uses STATUS_VALUE and healing uses SUSTAIN_WEIGHT, which are the same
numbers the damaging path already uses for the same things.
"""

import pytest

from champions_ai.agents.heuristic import STATUS_MOVE_VALUE, HeuristicAgent
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
)

# Two sets, because a Pokemon may hold only four moves.
SELF_MOVES = ("swordsdance", "recover", "thunderwave", "tailwind")
FOE_MOVES = ("growl", "taunt")


def _status_move(move_id, **extra):
    return {
        "name": move_id, "type": "Normal", "category": "Status", "basePower": 0,
        "accuracy": 100, "priority": 0, "target": "self",
        "flags": [], "secondaries": [], **extra,
    }


def _stats(**over):
    base = {"hp": 100, "atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100}
    base.update(over)
    return base


DEX = Dex.from_payload({
    "species": {
        "ours": {"name": "Ours", "types": ["Normal"], "baseStats": _stats(),
                 "abilities": [], "weightkg": 1.0, "baseSpecies": "Ours"},
        "theirs": {"name": "Theirs", "types": ["Normal"], "baseStats": _stats(),
                   "abilities": [], "weightkg": 1.0, "baseSpecies": "Theirs"},
        # Electric types cannot be paralysed.
        "sparky": {"name": "Sparky", "types": ["Electric"], "baseStats": _stats(),
                   "abilities": [], "weightkg": 1.0, "baseSpecies": "Sparky"},
    },
    "moves": {
        "swordsdance": _status_move("swordsdance", boosts={"atk": 2}),
        "recover": _status_move("recover", heal=[1, 2]),
        "thunderwave": _status_move(
            "thunderwave", target="normal", status="par", type="Electric"
        ),
        "tailwind": _status_move("tailwind", target="allySide", sideCondition="tailwind"),
        "growl": _status_move("growl", target="allAdjacentFoes", boosts={"atk": -1}),
        "taunt": _status_move("taunt", target="normal", volatileStatus="taunt"),
    },
    "types": ["Normal", "Electric"],
    "chart": {
        "Normal": {"Normal": 1.0, "Electric": 1.0},
        "Electric": {"Normal": 1.0, "Electric": 0.5},
    },
})

INDEX = {move_id: i for i, move_id in enumerate(SELF_MOVES)}
INDEX.update({move_id: i for i, move_id in enumerate(FOE_MOVES)})


def _moveset(move_id):
    return FOE_MOVES if move_id in FOE_MOVES else SELF_MOVES


def _observation(
    *,
    our_boosts=None,
    their_boosts=None,
    our_hp=200,
    their_status=None,
    their_volatiles=(),
    our_side_conditions=None,
    foe="Theirs",
    moves=SELF_MOVES,
):
    mine = BattlePokemon(
        pokemon_set=PokemonSet(species="Ours", level=50, ability="x", moves=moves),
        current_hp=our_hp, max_hp=200,
        computed_stats={"atk": 150, "def": 100, "spa": 150, "spd": 100, "spe": 100},
        choosable_moves=moves,
        boosts=our_boosts or Boosts(),
    )
    return Observation(
        regulation=REGULATION_M_B, turn=2, player=0,
        own_side=Side(
            team=(mine,), active_slots=(0, None),
            side_conditions=dict(our_side_conditions or {}),
        ),
        opponent_side=ObservedSide(
            revealed=(ObservedPokemon(
                species=foe, level=50, hp_percent=100, fainted=False,
                status=their_status, boosts=their_boosts or Boosts(),
                volatile_conditions=frozenset(their_volatiles),
            ),),
            active_slots=(0, None),
        ),
    )


@pytest.fixture
def agent():
    return HeuristicAgent(DEX, name="test")


def _score(agent, move_id, **kwargs):
    observation = _observation(moves=_moveset(move_id), **kwargs)
    return agent.score_slot_action(
        observation, 0, MoveAction(move_index=INDEX[move_id])
    ).score


# ------------------------------------------------------------------ boosts


def test_swords_dance_is_worth_the_two_stages_it_gives(agent):
    """Priced with STAT_STAGE_VALUE, the same as a +2 rider on an attack."""
    assert _score(agent, "swordsdance") == pytest.approx(2 * 0.12 * 100)


def test_a_boost_is_worth_only_the_headroom_that_is_left(agent):
    """At +5 a Swords Dance buys one stage, and at +6 it buys none. Without
    this the agent boosts forever, because a redundant boost scored the same
    as a fresh one."""
    full = _score(agent, "swordsdance")
    nearly = _score(agent, "swordsdance", our_boosts=Boosts(attack=5))
    maxed = _score(agent, "swordsdance", our_boosts=Boosts(attack=6))
    assert nearly == pytest.approx(full / 2)
    assert maxed == 0.0


def test_dropping_their_stat_is_worth_something(agent):
    assert _score(agent, "growl") > 0


def test_dropping_a_stat_already_at_the_floor_is_worth_nothing(agent):
    assert _score(agent, "growl", their_boosts=Boosts(attack=-6)) == 0.0


# ------------------------------------------------------------------ status


def test_thunder_wave_is_worth_what_paralysis_is_worth(agent):
    """The same STATUS_VALUE the rider path uses -- 0.35 of a health bar."""
    assert _score(agent, "thunderwave") == pytest.approx(0.35 * 100)


def test_thunder_wave_into_an_electric_type_is_worth_nothing(agent):
    assert _score(agent, "thunderwave", foe="Sparky") == 0.0


def test_a_second_status_never_lands(agent):
    assert _score(agent, "thunderwave", their_status="brn") == 0.0


# ------------------------------------------------------------------ healing


def test_recover_is_worth_the_hp_it_actually_restores(agent):
    """Clamped to what is missing, in the same currency as a drain."""
    half_gone = _score(agent, "recover", our_hp=100)
    quarter_gone = _score(agent, "recover", our_hp=150)
    assert half_gone > quarter_gone > 0


def test_recover_at_full_health_is_worth_nothing(agent):
    """It used to score 12.0, exactly as much as one at death's door."""
    assert _score(agent, "recover", our_hp=200) == 0.0


# ------------------------------------------------------------ side conditions


def test_tailwind_is_worth_setting(agent):
    assert _score(agent, "tailwind") > STATUS_MOVE_VALUE


def test_tailwind_already_up_is_worth_nothing(agent):
    """The check that stops the agent re-setting its own Tailwind every turn."""
    assert _score(agent, "tailwind", our_side_conditions={"tailwind": 0}) == 0.0


# ---------------------------------------------------------------- volatiles


def test_taunt_is_worth_inflicting(agent):
    assert _score(agent, "taunt") > 0


def test_taunt_on_an_already_taunted_target_is_worth_nothing(agent):
    assert _score(agent, "taunt", their_volatiles=("taunt",)) == 0.0
