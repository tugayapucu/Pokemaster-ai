import pytest

from champions_ai.domain import (
    REGULATION_M_B,
    BattlePokemon,
    BattleState,
    MoveAction,
    MoveData,
    Observation,
    PassAction,
    PokemonSet,
    Side,
    SwitchAction,
    legal_joint_actions,
    legal_slot_actions,
)

MOVES = {
    "tackle": MoveData(move_id="tackle", target="normal"),
    "earthquake": MoveData(move_id="earthquake", target="allAdjacent"),
    "protect": MoveData(move_id="protect", target="self"),
    "helpinghand": MoveData(move_id="helpinghand", target="adjacentAlly"),
    "heatwave": MoveData(move_id="heatwave", target="allAdjacentFoes"),
}


def _mon(species: str, moves: tuple[str, ...] = ("tackle", "protect"), **overrides):
    defaults = dict(
        pokemon_set=PokemonSet(species=species, level=50, ability="a", moves=moves),
        current_hp=100,
        max_hp=100,
        has_been_active=True,
    )
    return BattlePokemon(**{**defaults, **overrides})


def _observation(own: Side, opponent: Side | None = None, player: int = 0) -> Observation:
    opponent = opponent or Side(
        team=tuple(_mon(f"foe{i}") for i in range(4)), active_slots=(0, 1)
    )
    sides = (own, opponent) if player == 0 else (opponent, own)
    state = BattleState(regulation=REGULATION_M_B, turn=1, sides=sides)
    return Observation.from_battle_state(state, player=player)


def _own_side(**overrides) -> Side:
    defaults = dict(
        team=tuple(_mon(f"own{i}") for i in range(4)),
        active_slots=(0, 1),
    )
    return Side(**{**defaults, **overrides})


def test_normal_move_offers_every_live_target_including_the_ally():
    obs = _observation(_own_side())
    actions = legal_slot_actions(obs, 0, MOVES)
    tackle_targets = {
        (a.target.side, a.target.slot)
        for a in actions
        if isinstance(a, MoveAction) and a.move_index == 0
    }
    assert tackle_targets == {("foe", 0), ("foe", 1), ("ally", 1)}


def test_self_targeting_move_yields_exactly_one_action_with_no_target():
    obs = _observation(_own_side())
    protects = [a for a in legal_slot_actions(obs, 0, MOVES) if getattr(a, "move_index", None) == 1]
    assert len(protects) == 1
    assert protects[0].target is None


def test_spread_move_is_not_offered_per_target():
    own = _own_side(team=(_mon("a", moves=("heatwave",)), *_own_side().team[1:]))
    obs = _observation(own)
    moves = [a for a in legal_slot_actions(obs, 0, MOVES) if isinstance(a, MoveAction)]
    assert len(moves) == 1
    assert moves[0].target is None


def test_fainted_foe_is_not_a_valid_target():
    opponent = Side(
        team=(_mon("foe0", current_hp=0), *[_mon(f"foe{i}") for i in range(1, 4)]),
        active_slots=(0, 1),
    )
    obs = _observation(_own_side(), opponent)
    targets = {
        (a.target.side, a.target.slot)
        for a in legal_slot_actions(obs, 0, MOVES)
        if isinstance(a, MoveAction) and a.target is not None
    }
    assert ("foe", 0) not in targets
    assert ("foe", 1) in targets


def test_ally_targeting_move_disappears_when_partner_is_gone():
    own = _own_side(
        team=(_mon("a", moves=("helpinghand",)), *_own_side().team[1:]),
        active_slots=(0, None),
    )
    obs = _observation(own)
    assert not [a for a in legal_slot_actions(obs, 0, MOVES) if isinstance(a, MoveAction)]


def test_switches_offered_for_healthy_benched_pokemon_only():
    own = _own_side(
        team=(_mon("a"), _mon("b"), _mon("c", current_hp=0), _mon("d")),
        active_slots=(0, 1),
    )
    obs = _observation(own)
    actions = legal_slot_actions(obs, 0, MOVES)
    assert {a.team_index for a in actions if isinstance(a, SwitchAction)} == {3}


def test_trapped_pokemon_cannot_switch_but_can_still_move():
    own = _own_side(
        team=(_mon("a", volatile_conditions=frozenset({"trapped"})), *_own_side().team[1:]),
    )
    obs = _observation(own)
    actions = legal_slot_actions(obs, 0, MOVES)
    assert not [a for a in actions if isinstance(a, SwitchAction)]
    assert [a for a in actions if isinstance(a, MoveAction)]


def test_zero_pp_move_is_excluded():
    own = _own_side(
        team=(_mon("a", moves=("tackle", "protect"), move_pp=(0, 5)), *_own_side().team[1:]),
    )
    obs = _observation(own)
    used = {a.move_index for a in legal_slot_actions(obs, 0, MOVES) if isinstance(a, MoveAction)}
    assert used == {1}


def test_empty_slot_may_only_switch_someone_in():
    own = _own_side(active_slots=(0, None))
    actions = legal_slot_actions(_observation(own), 1, MOVES)
    assert actions
    assert all(isinstance(a, SwitchAction) for a in actions)


def test_empty_slot_with_no_bench_left_passes():
    own = _own_side(
        team=(_mon("a"), _mon("b", current_hp=0), _mon("c", current_hp=0), _mon("d", current_hp=0)),
        active_slots=(0, None),
    )
    actions = legal_slot_actions(_observation(own), 1, MOVES)
    assert actions == [PassAction()]


def test_unknown_move_data_raises_rather_than_silently_dropping_the_move():
    own = _own_side(team=(_mon("a", moves=("mysterymove",)), *_own_side().team[1:]))
    with pytest.raises(KeyError):
        legal_slot_actions(_observation(own), 0, MOVES)


def test_joint_actions_cover_both_slots_and_stay_legal():
    obs = _observation(_own_side())
    joint = legal_joint_actions(obs, MOVES)
    assert joint
    assert all(len(j) == 2 for j in joint)


def test_joint_actions_exclude_both_slots_switching_to_the_same_pokemon():
    own = _own_side(
        team=(_mon("a"), _mon("b"), _mon("c", current_hp=0), _mon("d")),
        active_slots=(0, 1),
    )
    joint = legal_joint_actions(_observation(own), MOVES)
    for action in joint:
        switch_targets = [a.team_index for a in action.slot_actions if isinstance(a, SwitchAction)]
        assert len(set(switch_targets)) == len(switch_targets)


def test_generator_never_offers_mega_while_species_data_is_unavailable():
    obs = _observation(_own_side())
    for action in legal_joint_actions(obs, MOVES):
        assert not any(isinstance(a, MoveAction) and a.mega for a in action.slot_actions)
