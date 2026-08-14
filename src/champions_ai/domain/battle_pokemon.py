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
    # Parallel to pokemon_set.moves. None means "not tracked" -- honest for
    # opponent Pokemon, whose PP a player cannot see.
    move_pp: tuple[int, ...] | None = None

    # What the *opponent* has learned about this Pokemon. Part of battle truth,
    # not a view concern: revelation is symmetric (if a move was used, it was
    # seen), and Observation masking reads these to decide what it may expose.
    revealed_moves: frozenset[str] = frozenset()
    ability_revealed: bool = False
    item_revealed: bool = False
    has_been_active: bool = False

    @model_validator(mode="after")
    def _check_hp(self) -> "BattlePokemon":
        if self.max_hp <= 0:
            raise ValueError(f"max_hp must be positive, got {self.max_hp}")
        if not 0 <= self.current_hp <= self.max_hp:
            raise ValueError(
                f"current_hp ({self.current_hp}) must be between 0 and max_hp ({self.max_hp})"
            )
        if self.move_pp is not None and len(self.move_pp) != len(self.pokemon_set.moves):
            raise ValueError(
                f"move_pp has {len(self.move_pp)} entries "
                f"but the Pokemon has {len(self.pokemon_set.moves)} moves"
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

    @property
    def hp_percent(self) -> int:
        """HP as a percentage, exactly as Champions shows it to the opponent.

        Floor, not round, with a floor of 1 while alive -- matching
        `Math.floor(100 * hp / maxhp) || 1` in the champions branch of
        Pokemon.getHealth(). Rounding would disagree with the protocol by a
        point and make parsed and computed values silently differ.
        """
        if self.fainted:
            return 0
        return max(1, self.current_hp * 100 // self.max_hp)

    def with_damage(self, amount: int) -> "BattlePokemon":
        return self.model_copy(update={"current_hp": max(0, self.current_hp - amount)})

    def with_heal(self, amount: int) -> "BattlePokemon":
        return self.model_copy(update={"current_hp": min(self.max_hp, self.current_hp + amount)})

    def with_status(self, status: str | None) -> "BattlePokemon":
        return self.model_copy(update={"status": status})

    def with_revealed_move(self, move: str) -> "BattlePokemon":
        return self.model_copy(update={"revealed_moves": self.revealed_moves | {move}})
