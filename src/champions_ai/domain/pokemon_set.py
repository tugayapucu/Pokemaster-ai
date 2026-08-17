from pydantic import BaseModel, field_validator

from champions_ai.domain.stats import StatSpread


class PokemonSet(BaseModel, frozen=True):
    """A player-declared Pokemon before battle (team sheet entry), not a live in-battle Pokemon."""

    species: str
    level: int
    ability: str
    moves: tuple[str, ...]
    stats: StatSpread = StatSpread()
    nature: str | None = None
    item: str | None = None
    tera_type: str | None = None
    nickname: str | None = None

    @field_validator("moves")
    @classmethod
    def _check_moves(cls, moves: tuple[str, ...]) -> tuple[str, ...]:
        """Zero moves is allowed here, but not on a declared team.

        A set reconstructed from a replay only knows the moves it saw used, and
        a Pokemon that was sent out and switched straight back has none. That
        is an honest partial observation, not an invalid Pokemon. The "must
        have at least one move" rule belongs to a *team sheet*, so `Team`
        enforces it there.
        """
        if len(moves) > 4:
            raise ValueError(f"a Pokemon may have at most 4 moves, got {len(moves)}")
        if len(set(moves)) != len(moves):
            raise ValueError(f"moves must be unique, got {moves}")
        return moves

    @field_validator("level")
    @classmethod
    def _check_level(cls, level: int) -> int:
        if not 1 <= level <= 100:
            raise ValueError(f"level must be between 1 and 100, got {level}")
        return level
