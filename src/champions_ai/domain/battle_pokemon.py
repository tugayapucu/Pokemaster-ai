from pydantic import BaseModel, model_validator

from champions_ai.domain.boosts import Boosts
from champions_ai.domain.pokemon_set import PokemonSet


class BattlePokemon(BaseModel, frozen=True):
    """Immutable in-battle snapshot of a Pokemon -- not the declared team-sheet entry."""

    pokemon_set: PokemonSet
    current_hp: int
    max_hp: int
    status: str | None = None
    volatile_conditions: frozenset[str] = frozenset()
    boosts: Boosts = Boosts()
    current_ability: str | None = None
    current_item: str | None = None

    @model_validator(mode="after")
    def _check_hp(self) -> "BattlePokemon":
        if self.max_hp <= 0:
            raise ValueError(f"max_hp must be positive, got {self.max_hp}")
        if not 0 <= self.current_hp <= self.max_hp:
            raise ValueError(
                f"current_hp ({self.current_hp}) must be between 0 and max_hp ({self.max_hp})"
            )
        return self

    @classmethod
    def from_set(cls, pokemon_set: PokemonSet, max_hp: int) -> "BattlePokemon":
        return cls(
            pokemon_set=pokemon_set,
            current_hp=max_hp,
            max_hp=max_hp,
            current_ability=pokemon_set.ability,
            current_item=pokemon_set.item,
        )

    @property
    def fainted(self) -> bool:
        return self.current_hp <= 0

    @property
    def hp_fraction(self) -> float:
        return self.current_hp / self.max_hp

    def with_damage(self, amount: int) -> "BattlePokemon":
        return self.model_copy(update={"current_hp": max(0, self.current_hp - amount)})

    def with_heal(self, amount: int) -> "BattlePokemon":
        return self.model_copy(update={"current_hp": min(self.max_hp, self.current_hp + amount)})

    def with_status(self, status: str | None) -> "BattlePokemon":
        return self.model_copy(update={"status": status})
