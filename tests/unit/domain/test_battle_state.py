import pytest
from pydantic import ValidationError

from champions_ai.domain import REGULATION_M_B, BattlePokemon, BattleState, PokemonSet, Side


def _mon(species: str, hp: int = 100) -> BattlePokemon:
    return BattlePokemon(
        pokemon_set=PokemonSet(
            species=species,
            level=50,
            ability="someability",
            moves=("tackle",),
        ),
        current_hp=hp,
        max_hp=100,
    )


def _side(prefix: str, hps: tuple[int, ...] = (100, 100, 100, 100)) -> Side:
    return Side(
        team=tuple(_mon(f"{prefix}{i}", hp=hp) for i, hp in enumerate(hps)),
        active_slots=(0, 1),
    )


def _state(**overrides) -> BattleState:
    defaults = dict(
        regulation=REGULATION_M_B,
        turn=1,
        sides=(_side("p1"), _side("p2")),
    )
    return BattleState(**{**defaults, **overrides})


def test_valid_doubles_state():
    state = _state()
    assert state.turn == 1
    assert len(state.sides) == 2
    assert not state.is_terminal
    assert state.winner is None


def test_rejects_wrong_slot_count_for_doubles():
    singles_shaped = Side(team=tuple(_mon(f"x{i}") for i in range(4)), active_slots=(0,))
    with pytest.raises(ValidationError):
        _state(sides=(singles_shaped, _side("p2")))


def test_rejects_team_size_that_does_not_match_picked_team_size():
    too_many = Side(team=tuple(_mon(f"x{i}") for i in range(6)), active_slots=(0, 1))
    with pytest.raises(ValidationError):
        _state(sides=(too_many, _side("p2")))


def test_rejects_negative_turn():
    with pytest.raises(ValidationError):
        _state(turn=-1)


def test_terminal_when_one_side_is_wiped_out():
    state = _state(sides=(_side("p1", hps=(0, 0, 0, 0)), _side("p2")))
    assert state.is_terminal
    assert state.winner == 1


def test_no_winner_when_both_sides_are_wiped_out():
    state = _state(sides=(_side("p1", hps=(0, 0, 0, 0)), _side("p2", hps=(0, 0, 0, 0))))
    assert state.is_terminal
    assert state.winner is None


def test_with_side_does_not_mutate_original():
    state = _state()
    updated = state.with_side(0, _side("p1", hps=(50, 100, 100, 100)))
    assert updated.sides[0].team[0].current_hp == 50
    assert state.sides[0].team[0].current_hp == 100


def test_round_trips_through_json():
    state = _state(weather="sand", field_conditions={"trickroom": 3})
    restored = BattleState.model_validate_json(state.model_dump_json())
    assert restored == state
