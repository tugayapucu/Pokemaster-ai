from pydantic import BaseModel, model_validator

from champions_ai.domain.boosts import Boosts
from champions_ai.domain.pokemon_set import PokemonSet
from champions_ai.domain.regulation import SpecialMechanic


class BattlePokemon(BaseModel, frozen=True):
    """Immutable in-battle snapshot of a Pokemon -- not the declared team-sheet entry."""

    pokemon_set: PokemonSet
    current_hp: int
    max_hp: int
    status: str | None = None
    volatile_conditions: frozenset[str] = frozenset()
    # Consecutive turns this Pokemon has just used Protect or a relative.
    # Symmetric with ObservedPokemon: our own streak governs whether
    # protecting again is worth a turn just as much as an opponent's does.
    protect_streak: int = 0
    # Turns out, counting this one. Zero means unknown, not new.
    turns_on_field: int = 0
    boosts: Boosts = Boosts()
    current_ability: str | None = None
    current_item: str | None = None

    # Final stats as the engine computes them, for our own side only -- an
    # opponent's are hidden. Excludes HP, which the engine reports separately
    # and which `max_hp` already carries.
    computed_stats: dict[str, int] | None = None
    # The moves this Pokemon may actually pick from right now, as the engine
    # lists them. Usually the full moveset, but a Pokemon locked mid-Solar Beam
    # or by Encore/Choice gets a trimmed list -- and move indices in a
    # submitted choice refer to *this* list, not the declared moveset.
    # None means not currently choosing (benched, or an opponent).
    choosable_moves: tuple[str, ...] | None = None

    # Parallel to choosable_moves: the target type the engine reports for each,
    # or None where it reports none. A Pokemon locked mid-charge has its target
    # already fixed, and the engine signals that by omitting the field --
    # submitting one anyway is rejected, so this must not fall back to the
    # move's usual target type.
    choosable_move_targets: tuple[str | None, ...] | None = None

    # Parallel to choosable_moves when present, else to pokemon_set.moves.
    # None means "not tracked" -- honest for opponents, whose PP is unknowable.
    move_pp: tuple[int, ...] | None = None

    # Availability as the engine reports it, per ADR 0003, rather than derived
    # from game data. Covers Choice lock, Encore, Taunt, Disable and Torment
    # without this project reimplementing any of them.
    disabled_moves: frozenset[str] = frozenset()
    available_specials: frozenset[SpecialMechanic] = frozenset()

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
        if self.move_pp is not None and len(self.move_pp) != len(self.selectable_moves):
            raise ValueError(
                f"move_pp has {len(self.move_pp)} entries "
                f"but {len(self.selectable_moves)} moves are selectable"
            )
        return self

    @property
    def selectable_moves(self) -> tuple[str, ...]:
        """What a choice's move index refers to: the engine's list when active."""
        return self.choosable_moves if self.choosable_moves is not None else self.pokemon_set.moves

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
