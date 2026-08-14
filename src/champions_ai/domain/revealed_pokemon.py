from pydantic import BaseModel

from champions_ai.domain.pokemon_set import PokemonSet


class RevealedPokemon(BaseModel, frozen=True):
    """An opponent's Pokemon as seen at Team Preview -- masked, not the ground truth PokemonSet."""

    species: str
    level: int
    ability: str | None = None
    item: str | None = None
    moves: tuple[str, ...] | None = None
    nature: str | None = None
    tera_type: str | None = None

    @classmethod
    def from_set(cls, pokemon_set: PokemonSet, *, sheets_open: bool = False) -> "RevealedPokemon":
        if not sheets_open:
            return cls(species=pokemon_set.species, level=pokemon_set.level)
        return cls(
            species=pokemon_set.species,
            level=pokemon_set.level,
            ability=pokemon_set.ability,
            item=pokemon_set.item,
            moves=pokemon_set.moves,
            nature=pokemon_set.nature,
            tera_type=pokemon_set.tera_type,
        )
