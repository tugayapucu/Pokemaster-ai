import pytest
from pydantic import ValidationError

from champions_ai.domain import PokemonSet, StatSpread


def _make(**overrides):
    defaults = dict(
        species="garchomp",
        level=50,
        ability="roughskin",
        moves=("earthquake", "protect", "stoneedge", "swordsdance"),
        stats=StatSpread(hp=20, attack=24, special_defense=22),
        item="sitrusberry",
    )
    return PokemonSet(**{**defaults, **overrides})


def test_valid_pokemon_set():
    mon = _make()
    assert mon.species == "garchomp"
    assert len(mon.moves) == 4


def test_rejects_zero_moves():
    with pytest.raises(ValidationError):
        _make(moves=())


def test_rejects_more_than_four_moves():
    with pytest.raises(ValidationError):
        _make(moves=("a", "b", "c", "d", "e"))


def test_rejects_duplicate_moves():
    with pytest.raises(ValidationError):
        _make(moves=("protect", "protect"))


def test_rejects_level_out_of_range():
    with pytest.raises(ValidationError):
        _make(level=101)
    with pytest.raises(ValidationError):
        _make(level=0)


def test_item_and_tera_type_are_optional():
    mon = _make(item=None, tera_type=None)
    assert mon.item is None
    assert mon.tera_type is None


def test_round_trips_through_json():
    mon = _make()
    restored = PokemonSet.model_validate_json(mon.model_dump_json())
    assert restored == mon
