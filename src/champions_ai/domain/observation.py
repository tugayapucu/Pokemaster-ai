from pydantic import BaseModel, Field

from champions_ai.domain.battle_pokemon import BattlePokemon
from champions_ai.domain.battle_state import BattleState
from champions_ai.domain.boosts import Boosts
from champions_ai.domain.regulation import Regulation
from champions_ai.domain.side import Side


class ObservedPokemon(BaseModel, frozen=True):
    """An opponent's Pokemon as a player sees it.

    Structurally incapable of carrying secrets: there is no field for the
    underlying PokemonSet, exact HP, max HP, or Stat Points, so a masking bug
    cannot leak them -- it can only fail to populate something already public.
    """

    species: str
    level: int
    hp_percent: int
    fainted: bool
    status: str | None = None
    boosts: Boosts = Boosts()
    volatile_conditions: frozenset[str] = frozenset()
    # Consecutive turns this Pokemon has just used Protect or a relative.
    # Each successive use is far more likely to fail, so an agent weighing
    # another one needs the count, not merely "it protected at some point".
    protect_streak: int = 0
    revealed_moves: frozenset[str] = frozenset()
    revealed_ability: str | None = None
    revealed_item: str | None = None

    @classmethod
    def from_battle_pokemon(cls, mon: BattlePokemon) -> "ObservedPokemon":
        return cls(
            species=mon.pokemon_set.species,
            level=mon.pokemon_set.level,
            hp_percent=mon.hp_percent,
            fainted=mon.fainted,
            status=mon.status,
            boosts=mon.boosts,
            volatile_conditions=mon.volatile_conditions,
            protect_streak=mon.protect_streak,
            revealed_moves=mon.revealed_moves,
            revealed_ability=mon.current_ability if mon.ability_revealed else None,
            revealed_item=mon.current_item if mon.item_revealed else None,
        )


class ObservedSide(BaseModel, frozen=True):
    """The opponent's side: only Pokemon seen so far, plus a count of those still unseen."""

    revealed: tuple[ObservedPokemon, ...] = ()
    active_slots: tuple[int | None, ...] = ()
    unrevealed_count: int = 0
    side_conditions: dict[str, int] = Field(default_factory=dict)
    mega_used: bool = False

    @classmethod
    def from_side(cls, side: Side) -> "ObservedSide":
        # Only Pokemon that have been on the field are known to exist at all --
        # which 4 of the declared 6 were brought is itself hidden information.
        seen_indices = [i for i, mon in enumerate(side.team) if mon.has_been_active]
        position = {team_index: rank for rank, team_index in enumerate(seen_indices)}
        return cls(
            revealed=tuple(ObservedPokemon.from_battle_pokemon(side.team[i]) for i in seen_indices),
            active_slots=tuple(
                None if i is None else position[i] for i in side.active_slots
            ),
            unrevealed_count=len(side.team) - len(seen_indices),
            side_conditions=dict(side.side_conditions),
            mega_used=side.mega_used,
        )


class Observation(BaseModel, frozen=True):
    """What one player legally knows. Agents and models consume this, never BattleState."""

    regulation: Regulation
    turn: int
    player: int
    own_side: Side
    opponent_side: ObservedSide
    weather: str | None = None
    terrain: str | None = None
    field_conditions: dict[str, int] = Field(default_factory=dict)

    @classmethod
    def from_battle_state(cls, state: BattleState, player: int) -> "Observation":
        if player not in (0, 1):
            raise ValueError(f"player must be 0 or 1, got {player}")
        return cls(
            regulation=state.regulation,
            turn=state.turn,
            player=player,
            own_side=state.sides[player],
            opponent_side=ObservedSide.from_side(state.sides[1 - player]),
            weather=state.weather,
            terrain=state.terrain,
            field_conditions=dict(state.field_conditions),
        )
