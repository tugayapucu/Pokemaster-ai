from pydantic import BaseModel, field_validator

from champions_ai.domain.pokemon_set import PokemonSet

MAX_TEAM_SIZE = 6


class Team(BaseModel, frozen=True):
    pokemon: tuple[PokemonSet, ...]

    @field_validator("pokemon")
    @classmethod
    def _check_size(cls, pokemon: tuple[PokemonSet, ...]) -> tuple[PokemonSet, ...]:
        if not 1 <= len(pokemon) <= MAX_TEAM_SIZE:
            raise ValueError(
                f"a team must have between 1 and {MAX_TEAM_SIZE} Pokemon, got {len(pokemon)}"
            )
        species = [p.species for p in pokemon]
        if len(set(species)) != len(species):
            raise ValueError(f"species must be unique on a team (Species Clause), got {species}")
        return pokemon

    def __len__(self) -> int:
        return len(self.pokemon)
