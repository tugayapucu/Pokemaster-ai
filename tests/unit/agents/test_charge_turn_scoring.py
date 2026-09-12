"""A charge move is not a hit on the turn it charges.

The scorer priced Solar Beam as a full hit whenever it was chosen. Outside the
sun the engine spends that turn charging and fires the next, so the same
choice commits two turns to one hit. The rules are `mechanics.charge`; these
tests are about the agent reading them.

Two moves below are identical in type, power and accuracy -- one carries the
`charge` flag and one does not -- so the flag is the only thing that can move a
score.
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
    StatSpread,
    TargetSlot,
)
from champions_ai.mechanics.charge import CHARGE_TURN_MULTIPLIER

TYPES = ("Grass", "Normal")
STATS = BaseStats(hp=90, attack=80, defense=90, special_attack=110, special_defense=90, speed=80)

SPROUT = SpeciesInfo(
    species_id="sprout", name="Sprout", types=("Grass",), base_stats=STATS, abilities=("Run Away",)
)
WALL = SpeciesInfo(
    species_id="wall", name="Wall", types=("Normal",),
    base_stats=BaseStats(
        hp=250, attack=50, defense=150, special_attack=50, special_defense=150, speed=30
    ),
    abilities=("Run Away",),
)


def _move(move_id, charge):
    return MoveInfo(
        move_id=move_id, name=move_id, type="Grass", category="Special",
        base_power=120, accuracy=100, priority=0, target="normal",
        flags=frozenset({"charge", "protect"} if charge else {"protect"}),
    )


MOVES = {"solarbeam": _move("solarbeam", True), "leafgust": _move("leafgust", False)}
DEX = Dex(
    species={s.species_id: s for s in (SPROUT, WALL)},
    moves=MOVES,
    types=TYPES,
    type_chart=TypeChart(multipliers={a: dict.fromkeys(TYPES, 1.0) for a in TYPES}),
)
AT_FOE = TargetSlot(side="foe", slot=0)


def _mon(species, move, item=None, locked=False):
    return BattlePokemon(
        pokemon_set=PokemonSet(
            species=species, level=50, ability="", moves=(move,),
            stats=StatSpread(special_attack=32), item=item,
        ),
        current_hp=180,
        max_hp=180,
        current_item=item,
        computed_stats={"hp": 180, "atk": 100, "def": 110, "spa": 150, "spd": 110, "spe": 100},
        choosable_moves=(move,),
        # The engine omits the target for a Pokemon locked mid-charge.
        choosable_move_targets=(None,) if locked else ("normal",),
        has_been_active=True,
    )


def _scored(move, *, weather=None, item=None, locked=False, **agent_kwargs):
    own = Side(
        team=tuple(_mon("Sprout", move, item=item, locked=locked) for _ in range(4)),
        active_slots=(0, 1),
    )
    foe = Side(team=tuple(_mon("Wall", "leafgust") for _ in range(4)), active_slots=(0, 1))
    state = BattleState(regulation=REGULATION_M_B, turn=3, sides=(own, foe), weather=weather)
    observation = Observation.from_battle_state(state, player=0)
    return HeuristicAgent(DEX, **agent_kwargs).score_slot_action(
        observation, 0, MoveAction(move_index=0, target=AT_FOE)
    )


def test_a_move_that_charges_this_turn_is_worth_one_hit_over_two_turns():
    charging = _scored("solarbeam").score
    immediate = _scored("leafgust").score
    assert charging == pytest.approx(immediate * CHARGE_TURN_MULTIPLIER)


def test_in_the_sun_it_fires_at_once_and_scores_as_a_hit():
    assert _scored("solarbeam", weather="sunnyday").score == pytest.approx(
        _scored("leafgust", weather="sunnyday").score
    )


def test_power_herb_skips_the_charge():
    assert _scored("solarbeam", item="powerherb").score == pytest.approx(
        _scored("leafgust", item="powerherb").score
    )


def test_the_locked_second_turn_is_the_hit():
    """A Pokemon mid-charge is sent its one move with no target. That turn it
    fires, and must not be halved a second time."""
    assert _scored("solarbeam", locked=True).score == pytest.approx(
        _scored("leafgust", locked=True).score
    )


def test_a_charging_hit_lands_on_nobody_this_turn():
    """Focus fire adds up what two slots do to one target *this turn*. A
    charging Pokemon does nothing to it yet, so it contributes nothing -- or the
    agent would count a knockout that cannot happen until next turn."""
    scored = _scored("solarbeam")
    assert scored.damage_fraction == 0.0
    assert scored.knockout_bonus == 0.0


def test_the_old_pricing_stays_constructible():
    assert _scored("solarbeam", charge_turns=False).score == pytest.approx(
        _scored("leafgust", charge_turns=False).score
    )
