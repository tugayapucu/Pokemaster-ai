"""After You, Quash and the trapping moves.

None of these has an effect of its own -- they buy an ordering, or they deny a
retreat -- so all of them scored the flat support value. They are priced here
in currencies that already exist: After You is worth the turn our partner
would otherwise lose, Quash is worth the hit our partner pre-empts, and Block
is worth exactly what we price our *own* escape at, because that is what it
denies.

Humans picked none of the four in 500 battles, so the corpus cannot settle any
of it. These check the wiring instead.
"""

import pytest

from champions_ai.agents import HeuristicAgent
from champions_ai.dex import BaseStats, Dex, MoveInfo, SpeciesInfo, TypeChart
from champions_ai.domain import (
    REGULATION_M_B,
    BattlePokemon,
    BattleState,
    MoveAction,
    Observation,
    PokemonSet,
    Side,
    TargetSlot,
)

MACHAMP = SpeciesInfo(
    species_id="machamp", name="Machamp", types=("Fighting",),
    base_stats=BaseStats(hp=90, attack=130, defense=80, special_attack=65,
                         special_defense=85, speed=55),
)
GENGAR = SpeciesInfo(
    species_id="gengar", name="Gengar", types=("Ghost", "Poison"),
    base_stats=BaseStats(hp=60, attack=65, defense=60, special_attack=130,
                         special_defense=75, speed=110),
)
SNORLAX = SpeciesInfo(
    species_id="snorlax", name="Snorlax", types=("Normal",),
    base_stats=BaseStats(hp=160, attack=110, defense=65, special_attack=65,
                         special_defense=110, speed=30),
)

MOVES = {
    "closecombat": MoveInfo(move_id="closecombat", name="Close Combat",
                            type="Fighting", category="Physical", base_power=120,
                            accuracy=100, priority=0, target="normal"),
    "ember": MoveInfo(move_id="ember", name="Ember", type="Fire",
                      category="Special", base_power=40, accuracy=100,
                      priority=0, target="normal"),
    "afteryou": MoveInfo(move_id="afteryou", name="After You", type="Normal",
                         category="Status", base_power=0, accuracy=None,
                         priority=0, target="normal"),
    "quash": MoveInfo(move_id="quash", name="Quash", type="Dark",
                      category="Status", base_power=0, accuracy=None,
                      priority=0, target="normal"),
    "block": MoveInfo(move_id="block", name="Block", type="Normal",
                      category="Status", base_power=0, accuracy=None,
                      priority=0, target="normal"),
}

TYPES = ("Fire", "Water", "Electric", "Grass", "Poison", "Dragon", "Ground",
         "Flying", "Normal", "Fighting", "Ghost", "Dark", "Psychic")


def _chart() -> TypeChart:
    table = {attacking: dict.fromkeys(TYPES, 1.0) for attacking in TYPES}
    table["Fighting"].update({"Normal": 2.0, "Ghost": 0.0})
    table["Fire"].update({"Normal": 1.0})
    return TypeChart(multipliers=table)


@pytest.fixture
def dex() -> Dex:
    return Dex(
        species={s.species_id: s for s in (MACHAMP, GENGAR, SNORLAX)},
        moves=MOVES,
        types=TYPES,
        type_chart=_chart(),
    )


@pytest.fixture
def agent(dex) -> HeuristicAgent:
    return HeuristicAgent(dex)


def _mon(species, moves, *, hp=200, max_hp=200, speed=100):
    return BattlePokemon(
        pokemon_set=PokemonSet(species=species, level=50, ability="", moves=moves),
        current_hp=hp,
        max_hp=max_hp,
        computed_stats={"hp": max_hp, "atk": 140, "def": 90, "spa": 140,
                        "spd": 90, "spe": speed},
        choosable_moves=moves,
        choosable_move_targets=tuple(MOVES[m].target for m in moves),
        has_been_active=True,
    )


OUR_MOVES = ("afteryou", "quash", "block", "ember")
ALLY_MOVES = ("closecombat", "ember")


def _observation(
    *,
    ally_hp: int = 200,
    ally_speed: int = 100,
    foe: str = "Snorlax",
    foe_hp: int = 200,
    foe_speed: int = 200,
) -> Observation:
    own = Side(
        team=(
            _mon("Machamp", OUR_MOVES, speed=50),
            _mon("Machamp", ALLY_MOVES, hp=ally_hp, speed=ally_speed),
            _mon("Machamp", OUR_MOVES),
            _mon("Machamp", OUR_MOVES),
        ),
        active_slots=(0, 1),
    )
    opponent = Side(
        team=(
            _mon(foe, ("closecombat", "ember"), hp=foe_hp,
                 max_hp=max(foe_hp, 200), speed=foe_speed),
            _mon("Snorlax", ("ember",), speed=10),
            _mon("Snorlax", ("ember",)),
            _mon("Snorlax", ("ember",)),
        ),
        active_slots=(0, 1),
    )
    state = BattleState(regulation=REGULATION_M_B, turn=3, sides=(own, opponent))
    return Observation.from_battle_state(state, player=0)


AT_ALLY = TargetSlot(side="ally", slot=1)
AT_FOE = TargetSlot(side="foe", slot=0)


def _scored(agent, observation, index, target):
    return agent.score_slot_action(
        observation, 0, MoveAction(move_index=index, target=target)
    )


# --- After You ----------------------------------------------------------


def test_after_you_is_worthless_when_our_partner_was_going_first(agent):
    observation = _observation(ally_speed=400, foe_speed=10)
    scored = _scored(agent, observation, 0, AT_ALLY)
    assert scored.score == 0.0
    assert "going first anyway" in scored.reasons[0]


def test_after_you_is_worthless_when_our_partner_survives_anyway(agent):
    """It changes the ordering either way; what it *buys* is only nameable
    when the partner would otherwise lose its turn to a knockout."""
    observation = _observation(ally_hp=200, ally_speed=10, foe_speed=400)
    scored = _scored(agent, observation, 0, AT_ALLY)
    assert scored.score == 0.0
    assert "survives either way" in scored.reasons[0]


def test_after_you_buys_the_turn_a_doomed_partner_would_lose(agent):
    observation = _observation(ally_hp=8, ally_speed=10, foe_speed=400)
    scored = _scored(agent, observation, 0, AT_ALLY)
    assert scored.score > 0
    assert "knocked out" in scored.reasons[0]


# --- Quash --------------------------------------------------------------


def test_quash_is_worthless_when_we_cannot_remove_the_target(agent):
    observation = _observation(foe_hp=4000, ally_speed=10, foe_speed=400)
    scored = _scored(agent, observation, 1, AT_FOE)
    assert scored.score == 0.0
    assert "cannot remove" in scored.reasons[0]


def test_quash_is_worth_the_hit_it_pre_empts(agent):
    observation = _observation(foe_hp=1, ally_speed=10, foe_speed=400)
    scored = _scored(agent, observation, 1, AT_FOE)
    assert scored.score > 0
    assert "back of the turn" in scored.reasons[0]


# --- trapping -----------------------------------------------------------


def test_block_stops_a_weakened_opponent_escaping(agent):
    observation = _observation(foe_hp=20)
    scored = _scored(agent, observation, 2, AT_FOE)
    assert scored.score > 0
    assert "escaping" in scored.reasons[0]


def test_block_buys_nothing_against_something_healthy(agent):
    """It was not leaving, so denying the retreat denies nothing."""
    observation = _observation(foe_hp=200)
    scored = _scored(agent, observation, 2, AT_FOE)
    assert scored.score == 0.0


def test_a_ghost_type_cannot_be_trapped(agent):
    """`trapped: 3` in the engine's type chart -- the same mechanism that makes
    Ghosts immune to Normal and Fighting."""
    observation = _observation(foe="Gengar", foe_hp=20)
    scored = _scored(agent, observation, 2, AT_FOE)
    assert scored.score == 0.0
    assert "cannot be trapped" in scored.reasons[0]
