"""Status and stat changes -- what a move does besides damage.

The moves this matters most for are the ones whose base power actively
misleads: Nuzzle is 20 BP and always paralyses, Zap Cannon buys guaranteed
paralysis with 50% accuracy.
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

TYPES = ["Normal", "Electric", "Fire"]


def _move(name, move_type="Normal", power=100, secondary=None, **extra):
    """Built in the *normalised* shape `Dex.from_payload` consumes.

    Showdown's raw data uses a singular `secondary`; the bridge flattens it to
    a `secondaries` list, so payload fixtures must use the flattened form.
    """
    return {
        "name": name, "type": move_type, "category": "Physical", "basePower": power,
        "accuracy": 100, "priority": 0, "target": "normal", "flags": [],
        "secondaries": [secondary] if secondary else [],
        **extra,
    }


def _mon(name, types):
    return {
        "name": name, "types": list(types),
        "baseStats": {"hp": 120, "atk": 120, "def": 80, "spa": 120, "spd": 80, "spe": 100},
        "abilities": [], "weightkg": 1.0, "baseSpecies": name,
    }


PAYLOAD = {
    "species": {
        "attacker": _mon("Attacker", ("Normal",)),
        "plainfoe": _mon("Plainfoe", ("Normal",)),
        "electricfoe": _mon("Electricfoe", ("Electric",)),
    },
    "moves": {
        "plain": _move("Plain"),
        "shocker": _move("Shocker", secondary={"chance": 100, "status": "par"}),
        "maybeburn": _move("Maybeburn", secondary={"chance": 10, "status": "brn"}),
        "slower": _move("Slower", secondary={"chance": 100, "boosts": {"spe": -1}}),
        "reckless": _move("Reckless", selfBoosts={"def": -1, "spd": -1}),
        "pumped": _move("Pumped", secondary={"chance": 100, "selfBoosts": {"atk": 1}}),
    },
    "types": TYPES,
    "chart": {a: dict.fromkeys(TYPES, 1.0) for a in TYPES},
}
DEX = Dex.from_payload(PAYLOAD)
# Four at a time: a Pokemon may not carry more, and the validator enforces it.
STATUS_SET = ("plain", "shocker", "maybeburn", "slower")
BOOST_SET = ("plain", "reckless", "pumped")


def _observation(foe="Plainfoe", foe_status=None, moves=STATUS_SET):
    mine = BattlePokemon(
        pokemon_set=PokemonSet(species="Attacker", level=50, ability="x", moves=moves),
        current_hp=195, max_hp=195,
        computed_stats={"atk": 140, "def": 100, "spa": 140, "spd": 100, "spe": 120},
        choosable_moves=moves,
    )
    return Observation(
        regulation=REGULATION_M_B, turn=1, player=0,
        own_side=Side(team=(mine,), active_slots=(0, None)),
        opponent_side=ObservedSide(
            revealed=(ObservedPokemon(species=foe, level=50, hp_percent=100,
                                      fainted=False, status=foe_status),),
            active_slots=(0, None),
        ),
    )


@pytest.fixture
def agent():
    return HeuristicAgent(DEX, name="test")


def _score(agent, observation, move):
    index = observation.own_side.team[0].selectable_moves.index(move)
    return agent.score_slot_action(
        observation, 0,
        MoveAction(move_index=index, target=TargetSlot(side="foe", slot=0)),
    )


def test_a_guaranteed_status_beats_an_identical_plain_move(agent):
    observation = _observation()
    assert _score(agent, observation, "shocker").score > _score(agent, observation, "plain").score


def test_a_likely_status_is_worth_more_than_an_unlikely_one(agent):
    observation = _observation()
    assert _score(agent, observation, "shocker").score > _score(agent, observation, "maybeburn").score


def test_a_status_the_target_cannot_take_is_worth_nothing(agent):
    """Electric types cannot be paralysed, so the rider must not be priced."""
    observation = _observation(foe="Electricfoe")
    assert _score(agent, observation, "shocker").score == pytest.approx(
        _score(agent, observation, "plain").score
    )


def test_a_status_cannot_stack_on_an_already_statused_target(agent):
    observation = _observation(foe_status="brn")
    assert _score(agent, observation, "shocker").score == pytest.approx(
        _score(agent, observation, "plain").score
    )


def test_dropping_the_targets_speed_is_worth_something(agent):
    observation = _observation()
    assert _score(agent, observation, "slower").score > _score(agent, observation, "plain").score
    assert any("drops their spe" in r for r in _score(agent, observation, "slower").reasons)


def test_raising_our_own_stat_is_worth_something(agent):
    observation = _observation(moves=BOOST_SET)
    assert _score(agent, observation, "pumped").score > _score(agent, observation, "plain").score


def test_a_self_inflicted_defence_drop_costs_less_when_nothing_threatens_us(agent):
    """It is a bill that only arrives if we are still there to be hit.

    Charging Close Combat full price for its own -1 Def/-1 SpD made the agent
    avoid one of the format's best attacks.
    """
    threatened = _observation(foe="Plainfoe", moves=BOOST_SET)
    # A fainted opponent threatens nothing at all.
    safe = Observation(
        regulation=REGULATION_M_B, turn=1, player=0,
        own_side=threatened.own_side,
        opponent_side=ObservedSide(
            revealed=(ObservedPokemon(species="Plainfoe", level=50, hp_percent=0, fainted=True),),
            active_slots=(None, None),
        ),
    )
    penalty_when_threatened = (
        _score(agent, threatened, "plain").score - _score(agent, threatened, "reckless").score
    )
    penalty_when_safe = (
        _score(agent, safe, "plain").score - _score(agent, safe, "reckless").score
    )
    assert penalty_when_threatened > penalty_when_safe
    assert penalty_when_safe == pytest.approx(0.0, abs=1e-9)


def test_the_reason_names_the_status_and_its_certainty(agent):
    reasons = _score(agent, _observation(), "shocker").reasons
    assert any("always inflicts par" in r for r in reasons)
    reasons = _score(agent, _observation(), "maybeburn").reasons
    assert any("10% inflicts brn" in r for r in reasons)
