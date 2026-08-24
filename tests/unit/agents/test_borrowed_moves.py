"""Copycat, Sleep Talk, Instruct and Spite, scored as what they stand in for.

All four took the flat support value until the tracker learned which move went
last, so a Copycat after an Earthquake was worth exactly as much as a Copycat
on turn one -- when the first *is* an Earthquake and the second simply fails.

Humans picked one of these four seven times in 500 battles, all of them
Instruct, so the corpus cannot settle any of this. These check the wiring
against the engine's rules instead.
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

CHARIZARD = SpeciesInfo(
    species_id="charizard", name="Charizard", types=("Fire", "Flying"),
    base_stats=BaseStats(hp=78, attack=84, defense=78, special_attack=109,
                         special_defense=85, speed=100),
)
VENUSAUR = SpeciesInfo(
    species_id="venusaur", name="Venusaur", types=("Grass", "Poison"),
    base_stats=BaseStats(hp=80, attack=82, defense=83, special_attack=100,
                         special_defense=100, speed=80),
)

MOVES = {
    "flamethrower": MoveInfo(move_id="flamethrower", name="Flamethrower", type="Fire",
                             category="Special", base_power=90, accuracy=100,
                             priority=0, target="normal"),
    "ember": MoveInfo(move_id="ember", name="Ember", type="Fire", category="Special",
                      base_power=40, accuracy=100, priority=0, target="normal"),
    "protect": MoveInfo(move_id="protect", name="Protect", type="Normal",
                        category="Status", base_power=0, accuracy=None,
                        priority=4, target="self",
                        flags=frozenset({"failcopycat"})),
    "copycat": MoveInfo(move_id="copycat", name="Copycat", type="Normal",
                        category="Status", base_power=0, accuracy=None,
                        priority=0, target="self",
                        flags=frozenset({"failcopycat", "nosleeptalk",
                                         "failinstruct"})),
    "sleeptalk": MoveInfo(move_id="sleeptalk", name="Sleep Talk", type="Normal",
                          category="Status", base_power=0, accuracy=None,
                          priority=0, target="self",
                          flags=frozenset({"nosleeptalk", "failcopycat",
                                           "failinstruct"})),
    "instruct": MoveInfo(move_id="instruct", name="Instruct", type="Psychic",
                         category="Status", base_power=0, accuracy=None,
                         priority=0, target="normal",
                         flags=frozenset({"failinstruct"})),
}

TYPES = ("Fire", "Water", "Electric", "Grass", "Poison", "Dragon", "Ground",
         "Flying", "Normal", "Fighting", "Psychic")


def _chart() -> TypeChart:
    table = {attacking: dict.fromkeys(TYPES, 1.0) for attacking in TYPES}
    table["Fire"].update({"Grass": 2.0, "Water": 0.5, "Fire": 0.5})
    return TypeChart(multipliers=table)


@pytest.fixture
def dex() -> Dex:
    return Dex(
        species={s.species_id: s for s in (CHARIZARD, VENUSAUR)},
        moves=MOVES,
        types=TYPES,
        type_chart=_chart(),
    )


@pytest.fixture
def agent(dex) -> HeuristicAgent:
    return HeuristicAgent(dex)


def _mon(
    species: str,
    moves: tuple[str, ...],
    *,
    status: str | None = None,
    speed: int = 120,
    last_move: str | None = None,
) -> BattlePokemon:
    return BattlePokemon(
        pokemon_set=PokemonSet(species=species, level=50, ability="a", moves=moves),
        current_hp=150,
        max_hp=150,
        status=status,
        computed_stats={"atk": 120, "def": 100, "spa": 150, "spd": 100, "spe": speed},
        choosable_moves=moves,
        choosable_move_targets=tuple(MOVES[m].target for m in moves),
        last_move=last_move,
        has_been_active=True,
    )


def _observation(
    own_moves: tuple[str, ...] = ("copycat", "ember", "protect"),
    *,
    last_move_used: str | None = None,
    own_status: str | None = None,
    ally_moves: tuple[str, ...] = ("flamethrower", "protect"),
    ally_speed: int = 60,
    ally_last_move: str | None = None,
) -> Observation:
    own = Side(
        team=(
            _mon("Charizard", own_moves, status=own_status, speed=120),
            _mon("Venusaur", ally_moves, speed=ally_speed, last_move=ally_last_move),
            _mon("Charizard", own_moves),
            _mon("Venusaur", own_moves),
        ),
        active_slots=(0, 1),
    )
    opponent = Side(
        team=tuple(
            _mon(species, ("flamethrower", "protect"))
            for species in ("Venusaur", "Venusaur", "Charizard", "Charizard")
        ),
        active_slots=(0, 1),
    )
    state = BattleState(
        regulation=REGULATION_M_B,
        turn=3,
        sides=(own, opponent),
        last_move_used=last_move_used,
    )
    return Observation.from_battle_state(state, player=0)


def _score(agent, observation, index: int, slot: int = 0, target=None) -> float:
    action = MoveAction(move_index=index, target=target)
    return agent.score_slot_action(observation, slot, action).score


def _reasons(agent, observation, index: int, slot: int = 0, target=None):
    action = MoveAction(move_index=index, target=target)
    return agent.score_slot_action(observation, slot, action).reasons


AT_FOE = TargetSlot(side="foe", slot=0)


# --- Copycat ------------------------------------------------------------


def test_copycat_is_worth_what_it_copies(agent):
    """A Copycat after a Flamethrower is a Flamethrower, and one after an
    Ember is an Ember. Before this it was the same flat number either way."""
    strong = _observation(last_move_used="flamethrower")
    weak = _observation(last_move_used="ember")
    assert _score(agent, strong, 0, target=AT_FOE) > _score(agent, weak, 0, target=AT_FOE)


def test_copycat_fails_before_anybody_has_moved(agent):
    observation = _observation(last_move_used=None)
    assert _score(agent, observation, 0, target=AT_FOE) == 0.0
    assert "no move for Copycat" in _reasons(agent, observation, 0, target=AT_FOE)[0]


def test_copycat_will_not_copy_a_move_the_engine_protects(agent):
    """Protect carries `failcopycat`, so a Copycat after one does nothing."""
    observation = _observation(last_move_used="protect")
    assert _score(agent, observation, 0, target=AT_FOE) == 0.0


def test_copycat_says_what_it_copied(agent):
    observation = _observation(last_move_used="flamethrower")
    assert _reasons(agent, observation, 0, target=AT_FOE)[0] == "copies Flamethrower"


# --- Sleep Talk ---------------------------------------------------------


def test_sleep_talk_is_worthless_while_awake(agent):
    observation = _observation(own_moves=("sleeptalk", "ember", "protect"))
    assert _score(agent, observation, 0, target=AT_FOE) == 0.0


def test_sleep_talk_is_worth_the_average_of_what_it_might_pick(agent):
    """Not the best of them. Taking the maximum would make Sleep Talk look
    like a free copy of our strongest hit, which is the obvious mistake."""
    observation = _observation(
        own_moves=("sleeptalk", "flamethrower", "ember"), own_status="slp"
    )
    flamethrower = _score(agent, observation, 1, target=AT_FOE)
    ember = _score(agent, observation, 2, target=AT_FOE)
    talk = _score(agent, observation, 0, target=AT_FOE)
    assert ember < talk < flamethrower


# --- Instruct -----------------------------------------------------------


def test_instruct_prices_what_the_ally_is_about_to_do(agent):
    """The ally is faster here, so it has already moved by the time Instruct
    resolves -- which is the normal case, and the whole reason the move is
    played. What gets repeated is what we expect it to pick *now*, not the
    stale move from last turn."""
    observation = _observation(
        own_moves=("instruct", "ember", "protect"),
        ally_speed=200,
        ally_last_move="flamethrower",
    )
    reasons = _reasons(agent, observation, 0, target=TargetSlot(side="ally", slot=1))
    assert "goes twice" in reasons[0]


def test_instruct_reads_the_last_move_only_when_the_ally_moves_after_us(agent):
    observation = _observation(
        own_moves=("instruct", "ember", "protect"),
        ally_speed=10,
        ally_last_move="flamethrower",
    )
    reasons = _reasons(agent, observation, 0, target=TargetSlot(side="ally", slot=1))
    assert reasons[0] == "our Venusaur uses Flamethrower again"


def test_instruct_fails_on_an_ally_that_has_not_moved(agent):
    observation = _observation(
        own_moves=("instruct", "ember", "protect"), ally_speed=10, ally_last_move=None
    )
    assert _score(agent, observation, 0, target=TargetSlot(side="ally", slot=1)) == 0.0


def test_instructing_an_opponent_is_a_cost_not_a_benefit(agent):
    """The move's target is `normal`, so the engine offers it across the field
    too -- and doing that hands them a free attack."""
    observation = _observation(own_moves=("instruct", "ember", "protect"))
    assert _score(agent, observation, 0, target=AT_FOE) < 0
