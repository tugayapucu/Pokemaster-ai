"""A recharge move is priced as the turn it costs, not as a free hit.

Two moves identical in type, power and accuracy -- one carries the `recharge`
flag -- so the flag is the only thing that can move a score. Unlike a charge
move, the hit lands this turn, so what focus fire reads must not change.
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

STATS = BaseStats(hp=90, attack=80, defense=90, special_attack=110, special_defense=90, speed=80)
WALL = BaseStats(hp=250, attack=50, defense=150, special_attack=50, special_defense=150, speed=30)


def _move(move_id, recharge, accuracy):
    return MoveInfo(
        move_id=move_id, name=move_id, type="Normal", category="Special",
        base_power=150, accuracy=accuracy, priority=0, target="normal",
        flags=frozenset({"recharge", "protect"} if recharge else {"protect"}),
    )


DEX = Dex(
    species={
        "blaster": SpeciesInfo(species_id="blaster", name="Blaster", types=("Normal",),
                               base_stats=STATS, abilities=("Run Away",)),
        "wall": SpeciesInfo(species_id="wall", name="Wall", types=("Normal",),
                            base_stats=WALL, abilities=("Run Away",)),
    },
    moves={
        "megablast": _move("megablast", True, 90),
        "plainblast": _move("plainblast", False, 90),
    },
    types=("Normal",),
    type_chart=TypeChart(multipliers={"Normal": {"Normal": 1.0}}),
)


def _mon(species, move):
    return BattlePokemon(
        pokemon_set=PokemonSet(species=species, level=50, ability="", moves=(move,),
                               stats=StatSpread(special_attack=32)),
        current_hp=180, max_hp=180,
        computed_stats={"hp": 180, "atk": 100, "def": 110, "spa": 150, "spd": 110, "spe": 100},
        choosable_moves=(move,),
        choosable_move_targets=("normal",),
        has_been_active=True,
    )


def _scored(move, **agent_kwargs):
    own = Side(team=tuple(_mon("Blaster", move) for _ in range(4)), active_slots=(0, 1))
    foe = Side(team=tuple(_mon("Wall", "plainblast") for _ in range(4)), active_slots=(0, 1))
    state = BattleState(regulation=REGULATION_M_B, turn=3, sides=(own, foe))
    observation = Observation.from_battle_state(state, player=0)
    return HeuristicAgent(DEX, **agent_kwargs).score_slot_action(
        observation, 0, MoveAction(move_index=0, target=TargetSlot(side="foe", slot=0))
    )


def test_a_recharge_move_is_worth_its_hit_over_the_turns_it_commits():
    assert _scored("megablast").score == pytest.approx(_scored("plainblast").score / 1.9)


def test_the_hit_still_lands_this_turn_for_focus_fire():
    recharge, plain = _scored("megablast"), _scored("plainblast")
    assert recharge.damage_fraction == pytest.approx(plain.damage_fraction)
    assert recharge.knockout_bonus == pytest.approx(plain.knockout_bonus)


def test_the_old_pricing_stays_constructible():
    assert _scored("megablast", recharge_turns=False).score == pytest.approx(
        _scored("plainblast", recharge_turns=False).score
    )
