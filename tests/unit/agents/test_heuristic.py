"""The heuristic's reasoning, not just its win rate.

A high score can hide bad logic -- an agent that never Protects and always
clicks the strongest move beats Random too. These check the individual
judgements it claims to make.
"""

import pytest

from champions_ai.agents import HeuristicAgent
from champions_ai.dex import BaseStats, Dex, MoveInfo, SpeciesInfo, TypeChart
from champions_ai.domain import (
    REGULATION_M_B,
    BattlePokemon,
    BattleState,
    JointAction,
    MoveAction,
    Observation,
    PassAction,
    PokemonSet,
    Side,
    SwitchAction,
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
GARCHOMP = SpeciesInfo(
    species_id="garchomp", name="Garchomp", types=("Dragon", "Ground"),
    base_stats=BaseStats(hp=108, attack=130, defense=95, special_attack=80,
                         special_defense=85, speed=102),
)

MOVES = {
    "flamethrower": MoveInfo(move_id="flamethrower", name="Flamethrower", type="Fire",
                             category="Special", base_power=90, accuracy=100,
                             priority=0, target="normal"),
    "surf": MoveInfo(move_id="surf", name="Surf", type="Water", category="Special",
                     base_power=90, accuracy=100, priority=0, target="normal"),
    "thunderbolt": MoveInfo(move_id="thunderbolt", name="Thunderbolt", type="Electric",
                            category="Special", base_power=90, accuracy=100,
                            priority=0, target="normal"),
    "protect": MoveInfo(move_id="protect", name="Protect", type="Normal",
                        category="Status", base_power=0, accuracy=None,
                        priority=4, target="self"),
    "focusblast": MoveInfo(move_id="focusblast", name="Focus Blast", type="Fighting",
                           category="Special", base_power=120, accuracy=70,
                           priority=0, target="normal"),
    "dig": MoveInfo(move_id="dig", name="Dig", type="Ground", category="Physical",
                    base_power=80, accuracy=100, priority=0, target="normal"),
}

TYPES = ("Fire", "Water", "Electric", "Grass", "Poison", "Dragon", "Ground",
         "Flying", "Normal", "Fighting")


def _chart() -> TypeChart:
    """Only the interactions these tests rely on; everything else is neutral."""
    table = {attacking: dict.fromkeys(TYPES, 1.0) for attacking in TYPES}
    table["Fire"].update({"Grass": 2.0, "Water": 0.5, "Dragon": 0.5, "Fire": 0.5})
    table["Water"].update({"Fire": 2.0, "Ground": 2.0, "Grass": 0.5, "Dragon": 0.5})
    table["Electric"].update({"Flying": 2.0, "Ground": 0.0, "Grass": 0.5, "Dragon": 0.5})
    table["Fighting"].update({"Flying": 0.5, "Poison": 0.5})
    return TypeChart(multipliers=table)


@pytest.fixture
def dex() -> Dex:
    return Dex(
        species={s.species_id: s for s in (CHARIZARD, VENUSAUR, GARCHOMP)},
        moves=MOVES,
        types=TYPES,
        type_chart=_chart(),
    )


@pytest.fixture
def agent(dex) -> HeuristicAgent:
    return HeuristicAgent(dex)


def _mon(species: str, moves: tuple[str, ...], *, hp: int = 150, max_hp: int = 150,
         status: str | None = None) -> BattlePokemon:
    return BattlePokemon(
        pokemon_set=PokemonSet(species=species, level=50, ability="a", moves=moves),
        current_hp=hp,
        max_hp=max_hp,
        status=status,
        computed_stats={"atk": 120, "def": 100, "spa": 150, "spd": 100, "spe": 120},
        choosable_moves=moves,
        choosable_move_targets=tuple(MOVES[m].target for m in moves),
        has_been_active=True,
    )


def _observation(
    own_moves: tuple[str, ...] = ("flamethrower", "surf", "protect"),
    *,
    own_hp: int = 150,
    foes: tuple[str, ...] = ("Venusaur", "Garchomp"),
    foe_hp_percent: int = 100,
    own_status: str | None = None,
) -> Observation:
    own = Side(
        team=(
            _mon("Charizard", own_moves, hp=own_hp, status=own_status),
            _mon("Garchomp", own_moves),
            _mon("Venusaur", own_moves),
            _mon("Charizard", own_moves),
        ),
        active_slots=(0, 1),
    )
    opponent = Side(
        team=tuple(
            _mon(species, own_moves, hp=max(1, 150 * foe_hp_percent // 100))
            for species in (*foes, "Charizard", "Venusaur")
        ),
        active_slots=(0, 1),
    )
    state = BattleState(regulation=REGULATION_M_B, turn=3, sides=(own, opponent))
    return Observation.from_battle_state(state, player=0)


def _score(agent, observation, action, slot: int = 0) -> float:
    return agent.score_slot_action(observation, slot, action).score


def test_prefers_super_effective_over_resisted(agent):
    """Fire into Grass beats Water into Grass, same power and accuracy."""
    observation = _observation()
    fire = MoveAction(move_index=0, target=TargetSlot(side="foe", slot=0))
    water = MoveAction(move_index=1, target=TargetSlot(side="foe", slot=0))
    assert _score(agent, observation, fire) > _score(agent, observation, water)


def test_refuses_to_aim_a_damaging_move_at_its_partner(agent):
    observation = _observation()
    at_foe = MoveAction(move_index=0, target=TargetSlot(side="foe", slot=0))
    at_ally = MoveAction(move_index=0, target=TargetSlot(side="ally", slot=1))
    assert _score(agent, observation, at_ally) < 0
    assert _score(agent, observation, at_ally) < _score(agent, observation, at_foe)


def test_avoids_a_move_the_target_is_immune_to(agent):
    """Electric cannot touch Garchomp; even Protect is better than a wasted turn."""
    observation = _observation(own_moves=("thunderbolt", "protect", "surf"))
    at_garchomp = MoveAction(move_index=0, target=TargetSlot(side="foe", slot=1))
    protect = MoveAction(move_index=1)
    assert _score(agent, observation, at_garchomp) < 0
    assert _score(agent, observation, protect) > _score(agent, observation, at_garchomp)


def test_a_guaranteed_knockout_outranks_bigger_damage_elsewhere(agent):
    """Finishing something beats chipping something healthy."""
    observation = _observation(foes=("Venusaur", "Garchomp"), foe_hp_percent=5)
    finisher = MoveAction(move_index=0, target=TargetSlot(side="foe", slot=0))
    scored = agent.score_slot_action(observation, 0, finisher)
    assert scored.score > 100
    assert any("knockout" in reason for reason in scored.reasons)


def test_accuracy_discounts_a_strong_move(agent):
    """Focus Blast hits harder but misses 30% of the time."""
    observation = _observation(own_moves=("focusblast", "surf", "protect"))
    inaccurate = agent.score_slot_action(
        observation, 0, MoveAction(move_index=0, target=TargetSlot(side="foe", slot=0))
    )
    assert any("70%" in reason for reason in inaccurate.reasons)


def test_protect_is_worth_more_when_the_pokemon_is_nearly_dead(agent):
    healthy = _observation(own_hp=150)
    weakened = _observation(own_hp=20)
    protect = MoveAction(move_index=2)
    assert _score(agent, weakened, protect) > _score(agent, healthy, protect)


def test_switching_costs_a_turn_unless_the_pokemon_is_weakened(agent):
    healthy = _observation(own_hp=150)
    weakened = _observation(own_hp=20)
    switch = SwitchAction(team_index=2)
    assert _score(agent, healthy, switch) < 0
    assert _score(agent, weakened, switch) > _score(agent, healthy, switch)


def test_a_burned_attacker_devalues_physical_moves(agent):
    """Burn halves physical damage, so the score should fall with it."""
    healthy = _observation(own_moves=("dig", "surf", "protect"))
    burned = _observation(own_moves=("dig", "surf", "protect"), own_status="brn")
    attack = MoveAction(move_index=0, target=TargetSlot(side="foe", slot=0))
    assert _score(agent, burned, attack) < _score(agent, healthy, attack)


def test_burn_does_not_devalue_special_moves(agent):
    """Only physical damage is halved; a burned special attacker is unaffected."""
    healthy = _observation(own_moves=("surf", "dig", "protect"))
    burned = _observation(own_moves=("surf", "dig", "protect"), own_status="brn")
    attack = MoveAction(move_index=0, target=TargetSlot(side="foe", slot=0))
    assert _score(agent, burned, attack) == _score(agent, healthy, attack)


def test_selects_the_best_scoring_joint_action(agent):
    observation = _observation()
    good = JointAction(
        slot_actions=(
            MoveAction(move_index=0, target=TargetSlot(side="foe", slot=0)),
            PassAction(),
        )
    )
    bad = JointAction(
        slot_actions=(
            MoveAction(move_index=0, target=TargetSlot(side="ally", slot=1)),
            PassAction(),
        )
    )
    assert agent.select_action(observation, [bad, good]) is good


def test_explanations_are_human_readable(agent):
    observation = _observation()
    action = JointAction(
        slot_actions=(
            MoveAction(move_index=0, target=TargetSlot(side="foe", slot=0)),
            PassAction(),
        )
    )
    reasons = agent.explain(observation, action)
    assert reasons[0].reasons
    assert "Flamethrower" in reasons[0].reasons[0]
    assert any("super effective" in reason for reason in reasons[0].reasons)


def test_missing_dex_data_scores_neutrally_rather_than_last(dex):
    """A data gap should not masquerade as a judgement about the move."""
    agent = HeuristicAgent(dex)
    observation = _observation(own_moves=("flamethrower", "surf", "protect"))
    del dex.moves["flamethrower"]
    scored = agent.score_slot_action(
        observation, 0, MoveAction(move_index=0, target=TargetSlot(side="foe", slot=0))
    )
    assert scored.score == 0.0
    assert any("no data" in reason for reason in scored.reasons)
