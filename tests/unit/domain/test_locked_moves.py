"""Locked moves: the case that broke legal-action generation in a live battle.

A Pokemon charging Solar Beam gets a request listing only that move, with no
`pp` and no `target` field. Both omissions matter: treating a missing `pp` as
zero filters out the only legal move, and falling back to the move's usual
target type produces a choice the engine rejects.
"""

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
    legal_slot_actions,
)

MOVES = {"solarbeam": MoveData(move_id="solarbeam", target="normal")}


def _mon(species: str, **overrides) -> BattlePokemon:
    defaults = dict(
        pokemon_set=PokemonSet(
            species=species,
            level=50,
            ability="a",
            moves=("solarbeam", "protect"),
        ),
        current_hp=100,
        max_hp=100,
        has_been_active=True,
    )
    return BattlePokemon(**{**defaults, **overrides})


def _observation(own_first: BattlePokemon) -> Observation:
    own = Side(
        team=(own_first, _mon("b"), _mon("c"), _mon("d")),
        active_slots=(0, 1),
    )
    foe = Side(team=tuple(_mon(f"foe{i}") for i in range(4)), active_slots=(0, 1))
    state = BattleState(regulation=REGULATION_M_B, turn=2, sides=(own, foe))
    return Observation.from_battle_state(state, player=0)


def test_locked_move_is_offered_without_a_target():
    """The engine omits `target` while locked; submitting one is rejected."""
    locked = _mon(
        "a",
        choosable_moves=("solarbeam",),
        choosable_move_targets=(None,),
    )
    actions = legal_slot_actions(_observation(locked), 0, MOVES)
    moves = [a for a in actions if isinstance(a, MoveAction)]
    assert len(moves) == 1
    assert moves[0].move_index == 0
    assert moves[0].target is None


def test_missing_pp_does_not_read_as_no_pp_left():
    """A locked entry carries no `pp`; defaulting it to 0 would leave no legal move."""
    locked = _mon(
        "a",
        choosable_moves=("solarbeam",),
        choosable_move_targets=(None,),
        move_pp=None,
    )
    actions = legal_slot_actions(_observation(locked), 0, MOVES)
    assert not any(isinstance(a, PassAction) for a in actions)
    assert any(isinstance(a, MoveAction) for a in actions)


def test_engine_targets_win_over_the_moves_usual_behaviour():
    """MOVES says solarbeam targets 'normal'; the engine says none this turn."""
    locked = _mon("a", choosable_moves=("solarbeam",), choosable_move_targets=(None,))
    unlocked = _mon("a", choosable_moves=("solarbeam",), choosable_move_targets=("normal",))

    locked_moves = [
        a for a in legal_slot_actions(_observation(locked), 0, MOVES) if isinstance(a, MoveAction)
    ]
    unlocked_moves = [
        a for a in legal_slot_actions(_observation(unlocked), 0, MOVES) if isinstance(a, MoveAction)
    ]
    assert {m.target for m in locked_moves} == {None}
    assert all(m.target is not None for m in unlocked_moves)
    assert len(unlocked_moves) > len(locked_moves)


def test_move_indices_follow_the_engines_trimmed_list():
    """`move N` indexes the engine's list, not the declared four-move set."""
    locked = _mon(
        "a",
        pokemon_set=PokemonSet(
            species="a",
            level=50,
            ability="a",
            moves=("heatwave", "solarbeam", "protect", "flamethrower"),
        ),
        choosable_moves=("solarbeam",),
        choosable_move_targets=(None,),
    )
    actions = legal_slot_actions(_observation(locked), 0, MOVES)
    moves = [a for a in actions if isinstance(a, MoveAction)]
    # Solar Beam is index 1 of the declared set but index 0 of what may be chosen.
    assert [m.move_index for m in moves] == [0]


def test_move_data_is_still_used_when_the_engine_says_nothing():
    """Benched or unrequested Pokemon fall back to the supplied move data."""
    plain = _mon("a")
    actions = legal_slot_actions(_observation(plain), 0, {
        "solarbeam": MoveData(move_id="solarbeam", target="normal"),
        "protect": MoveData(move_id="protect", target="self"),
    })
    assert any(isinstance(a, MoveAction) and a.target is not None for a in actions)
