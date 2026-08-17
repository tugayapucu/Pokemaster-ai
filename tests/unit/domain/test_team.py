import pytest
from pydantic import ValidationError

from champions_ai.domain import PokemonSet, Team


def _mon(species: str) -> PokemonSet:
    return PokemonSet(
        species=species,
        level=50,
        ability="intimidate",
        moves=("tackle",),
    )


def test_valid_team_of_six():
    team = Team(pokemon=tuple(_mon(f"species{i}") for i in range(6)))
    assert len(team) == 6


def test_rejects_empty_team():
    with pytest.raises(ValidationError):
        Team(pokemon=())


def test_rejects_more_than_six():
    with pytest.raises(ValidationError):
        Team(pokemon=tuple(_mon(f"species{i}") for i in range(7)))


def test_rejects_duplicate_species():
    with pytest.raises(ValidationError):
        Team(pokemon=(_mon("garchomp"), _mon("garchomp")))


def test_rejects_a_pokemon_with_no_moves():
    """A declared team sheet must be complete, unlike a set rebuilt from a replay."""
    moveless = PokemonSet(species="ditto", level=50, ability="limber", moves=())
    with pytest.raises(ValidationError):
        Team(pokemon=(_mon("garchomp"), moveless))
