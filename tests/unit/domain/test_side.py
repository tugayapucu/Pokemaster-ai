import pytest
from pydantic import ValidationError

from champions_ai.domain import BattlePokemon, PokemonSet, Side


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


def _side(**overrides) -> Side:
    defaults = dict(
        team=tuple(_mon(f"species{i}") for i in range(4)),
        active_slots=(0, 1),
    )
    return Side(**{**defaults, **overrides})


def test_active_returns_the_pokemon_in_each_slot():
    side = _side()
    assert [mon.pokemon_set.species for mon in side.active] == ["species0", "species1"]


def test_empty_slot_is_allowed_after_a_faint():
    side = _side(active_slots=(0, None))
    assert side.active[1] is None


def test_rejects_out_of_range_slot_index():
    with pytest.raises(ValidationError):
        _side(active_slots=(0, 9))


def test_rejects_same_pokemon_in_two_slots():
    with pytest.raises(ValidationError):
        _side(active_slots=(2, 2))


def test_rejects_empty_team():
    with pytest.raises(ValidationError):
        Side(team=(), active_slots=())


def test_switchable_excludes_active_and_fainted():
    team = (_mon("a"), _mon("b"), _mon("c", hp=0), _mon("d"))
    side = Side(team=team, active_slots=(0, 1))
    assert side.switchable_indices() == (3,)


def test_has_usable_pokemon_is_false_when_all_fainted():
    team = tuple(_mon(f"species{i}", hp=0) for i in range(4))
    assert not Side(team=team, active_slots=(0, 1)).has_usable_pokemon


def test_with_pokemon_at_does_not_mutate_original():
    side = _side()
    updated = side.with_pokemon_at(0, _mon("species0", hp=25))
    assert updated.team[0].current_hp == 25
    assert side.team[0].current_hp == 100


def test_with_slot_replaces_only_that_slot():
    side = _side()
    updated = side.with_slot(1, 3)
    assert updated.active_slots == (0, 3)
    assert side.active_slots == (0, 1)
