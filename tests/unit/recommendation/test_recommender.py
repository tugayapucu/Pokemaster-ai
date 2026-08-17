"""Ranking actions for a human to read."""

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
from champions_ai.recommendation import Recommender, describe_joint_action

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
    "surf": MoveInfo(move_id="surf", name="Surf", type="Water", category="Special",
                     base_power=90, accuracy=100, priority=0, target="normal"),
    "protect": MoveInfo(move_id="protect", name="Protect", type="Normal",
                        category="Status", base_power=0, accuracy=None,
                        priority=4, target="self"),
}

TYPES = ("Fire", "Water", "Grass", "Poison", "Flying", "Normal")


@pytest.fixture
def dex() -> Dex:
    table = {a: dict.fromkeys(TYPES, 1.0) for a in TYPES}
    table["Fire"].update({"Grass": 2.0, "Water": 0.5, "Fire": 0.5})
    table["Water"].update({"Fire": 2.0, "Grass": 0.5})
    return Dex(
        species={s.species_id: s for s in (CHARIZARD, VENUSAUR)},
        moves=MOVES,
        types=TYPES,
        type_chart=TypeChart(multipliers=table),
    )


def _mon(species: str, hp: int = 150) -> BattlePokemon:
    moves = ("flamethrower", "surf", "protect")
    return BattlePokemon(
        pokemon_set=PokemonSet(species=species, level=50, ability="a", moves=moves),
        current_hp=hp,
        max_hp=150,
        computed_stats={"atk": 120, "def": 100, "spa": 150, "spd": 100, "spe": 120},
        choosable_moves=moves,
        choosable_move_targets=("normal", "normal", "self"),
        has_been_active=True,
    )


@pytest.fixture
def observation() -> Observation:
    own = Side(
        team=(_mon("Charizard"), _mon("Venusaur"), _mon("Charizard"), _mon("Venusaur")),
        active_slots=(0, 1),
    )
    foe = Side(
        team=(_mon("Venusaur"), _mon("Charizard"), _mon("Venusaur"), _mon("Charizard")),
        active_slots=(0, 1),
    )
    state = BattleState(regulation=REGULATION_M_B, turn=4, sides=(own, foe))
    return Observation.from_battle_state(state, player=0)


def _actions() -> list[JointAction]:
    return [
        JointAction(slot_actions=(
            MoveAction(move_index=0, target=TargetSlot(side="foe", slot=0)), PassAction())),
        JointAction(slot_actions=(
            MoveAction(move_index=1, target=TargetSlot(side="foe", slot=0)), PassAction())),
        JointAction(slot_actions=(MoveAction(move_index=2), PassAction())),
        JointAction(slot_actions=(SwitchAction(team_index=2), PassAction())),
    ]


def test_ranks_the_best_action_first(dex, observation):
    """Fire into a Grass type should lead."""
    advice = Recommender(dex).recommend(observation, _actions())
    assert "Flamethrower" in advice.best.description
    assert advice.best.rank == 1


def test_confidences_are_ordered_and_sum_to_one(dex, observation):
    advice = Recommender(dex).recommend(observation, _actions())
    confidences = [entry.confidence for entry in advice.recommendations]
    assert confidences == sorted(confidences, reverse=True)
    assert sum(confidences) + advice.remainder_confidence == pytest.approx(1.0)


def test_descriptions_name_the_move_not_an_index(dex, observation):
    advice = Recommender(dex).recommend(observation, _actions())
    assert "move 1" not in advice.best.description
    assert "Charizard:" in advice.best.description


def test_targets_say_whose_pokemon_they_are(dex, observation):
    """Both sides field a Charizard here, so a bare species name is ambiguous."""
    action = JointAction(slot_actions=(
        MoveAction(move_index=0, target=TargetSlot(side="foe", slot=1)), PassAction()))
    description = describe_joint_action(observation, action, dex=dex)
    assert "the opposing Charizard" in description


def test_ally_targets_are_marked_as_ours(dex, observation):
    action = JointAction(slot_actions=(
        MoveAction(move_index=0, target=TargetSlot(side="ally", slot=1)), PassAction()))
    assert "your Venusaur" in describe_joint_action(observation, action, dex=dex)


def test_switches_name_the_incoming_pokemon(dex, observation):
    action = JointAction(slot_actions=(SwitchAction(team_index=2), PassAction()))
    assert "switch to Charizard" in describe_joint_action(observation, action, dex=dex)


def test_the_best_recommendation_carries_its_reasons(dex, observation):
    advice = Recommender(dex).recommend(observation, _actions())
    assert advice.best.reasons
    assert "Flamethrower" in advice.explain_best()


def test_indistinguishable_actions_are_collapsed(dex, observation):
    """Two actions the scorer rates identically say nothing different."""
    duplicate = JointAction(slot_actions=(
        MoveAction(move_index=0, target=TargetSlot(side="foe", slot=0), special="mega"),
        PassAction()))
    advice = Recommender(dex).recommend(observation, [*_actions(), duplicate])
    descriptions = [entry.description for entry in advice.recommendations]
    assert len(descriptions) == len(set(descriptions))
    assert sum("Flamethrower -> the opposing Venusaur" in d for d in descriptions) == 1


def test_a_decisive_position_reads_as_clear(dex, observation):
    advice = Recommender(dex).recommend(observation, _actions())
    assert advice.is_clear
    assert advice.best.confidence > 0.4


def test_shortlist_is_capped_and_the_remainder_is_accounted_for(dex, observation):
    advice = Recommender(dex, top_k=2).recommend(observation, _actions())
    assert len(advice.recommendations) == 2
    shown = sum(entry.confidence for entry in advice.recommendations)
    assert shown + advice.remainder_confidence == pytest.approx(1.0)


def test_render_is_human_readable(dex, observation):
    rendered = Recommender(dex).recommend(observation, _actions()).render()
    assert rendered.startswith("Recommended actions")
    assert "1." in rendered
    assert "%" in rendered


def test_considered_reports_the_full_action_space(dex, observation):
    advice = Recommender(dex, top_k=2).recommend(observation, _actions())
    assert advice.considered == len(_actions())


def test_empty_action_list_is_rejected(dex, observation):
    with pytest.raises(ValueError):
        Recommender(dex).recommend(observation, [])


def test_recommendation_matches_what_the_agent_would_play(dex, observation):
    """Advice and play must agree, or the recommender is describing someone else."""
    agent = HeuristicAgent(dex)
    actions = _actions()
    advice = Recommender(dex, agent=agent).recommend(observation, actions)
    assert agent.select_action(observation, actions) == advice.best.action
