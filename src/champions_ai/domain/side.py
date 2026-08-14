from pydantic import BaseModel, Field, model_validator

from champions_ai.domain.battle_pokemon import BattlePokemon


class Side(BaseModel, frozen=True):
    """One player's half of a battle: the Pokemon they brought, and which are on the field."""

    team: tuple[BattlePokemon, ...]
    active_slots: tuple[int | None, ...]
    side_conditions: dict[str, int] = Field(default_factory=dict)
    mega_used: bool = False

    @model_validator(mode="after")
    def _check_slots(self) -> "Side":
        if not self.team:
            raise ValueError("a side must have at least one Pokemon")
        occupied = [i for i in self.active_slots if i is not None]
        for index in occupied:
            if not 0 <= index < len(self.team):
                raise ValueError(
                    f"active slot index {index} is out of range for a team of {len(self.team)}"
                )
        if len(set(occupied)) != len(occupied):
            raise ValueError(f"the same Pokemon cannot occupy two slots at once: {occupied}")
        return self

    @property
    def active(self) -> tuple[BattlePokemon | None, ...]:
        return tuple(None if i is None else self.team[i] for i in self.active_slots)

    @property
    def has_usable_pokemon(self) -> bool:
        return any(not mon.fainted for mon in self.team)

    def is_active(self, index: int) -> bool:
        return index in self.active_slots

    def switchable_indices(self) -> tuple[int, ...]:
        """Bench Pokemon eligible to switch in: alive and not already on the field."""
        return tuple(
            i for i, mon in enumerate(self.team) if not mon.fainted and not self.is_active(i)
        )

    def with_pokemon_at(self, index: int, pokemon: BattlePokemon) -> "Side":
        updated = list(self.team)
        updated[index] = pokemon
        return self.model_copy(update={"team": tuple(updated)})

    def with_slot(self, slot: int, team_index: int | None) -> "Side":
        updated = list(self.active_slots)
        updated[slot] = team_index
        return self.model_copy(update={"active_slots": tuple(updated)})
