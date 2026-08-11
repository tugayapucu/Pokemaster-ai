import pytest
from pydantic import ValidationError

from champions_ai.domain import BattlePokemon, PokemonSet


def _set() -> PokemonSet:
    return PokemonSet(
        species="garchomp",
        level=50,
        ability="roughskin",
        moves=("earthquake", "protect"),
        item="sitrusberry",
    )


def test_from_set_starts_at_full_hp():
    mon = BattlePokemon.from_set(_set(), max_hp=176)
    assert mon.current_hp == 176
    assert mon.max_hp == 176
    assert not mon.fainted
    assert mon.hp_fraction == 1.0
    assert mon.current_ability == "roughskin"
    assert mon.current_item == "sitrusberry"


def test_with_damage_reduces_hp():
    mon = BattlePokemon.from_set(_set(), max_hp=176)
    damaged = mon.with_damage(50)
    assert damaged.current_hp == 126
    assert mon.current_hp == 176


def test_with_damage_cannot_go_below_zero():
    mon = BattlePokemon.from_set(_set(), max_hp=176)
    damaged = mon.with_damage(9000)
    assert damaged.current_hp == 0
    assert damaged.fainted


def test_with_heal_cannot_exceed_max_hp():
    mon = BattlePokemon.from_set(_set(), max_hp=176).with_damage(50)
    healed = mon.with_heal(9000)
    assert healed.current_hp == 176


def test_with_status_sets_and_clears():
    mon = BattlePokemon.from_set(_set(), max_hp=176)
    poisoned = mon.with_status("psn")
    assert poisoned.status == "psn"
    assert mon.status is None
    assert poisoned.with_status(None).status is None


def test_rejects_current_hp_above_max_hp():
    with pytest.raises(ValidationError):
        BattlePokemon(pokemon_set=_set(), current_hp=200, max_hp=176)


def test_rejects_non_positive_max_hp():
    with pytest.raises(ValidationError):
        BattlePokemon(pokemon_set=_set(), current_hp=0, max_hp=0)
