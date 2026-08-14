from pydantic import BaseModel, model_validator

STAT_NAMES = ("hp", "attack", "defense", "special_attack", "special_defense", "speed")


class StatSpread(BaseModel, frozen=True):
    """A Pokemon's Stat Points allocation (Champions' EV/IV replacement, see ADR 0002).

    Enforces only what is true of *any* regulation -- points can't be negative.
    The per-stat and total caps are regulation-specific and live on `Regulation`
    (`check_stat_spread`), so a future regulation that changes them changes one
    value rather than needing this class edited. Authoritative legality remains
    Showdown's (ADR 0001); these checks just fail fast on obvious mistakes.
    """

    hp: int = 0
    attack: int = 0
    defense: int = 0
    special_attack: int = 0
    special_defense: int = 0
    speed: int = 0

    @model_validator(mode="after")
    def _check_non_negative(self) -> "StatSpread":
        for name in STAT_NAMES:
            value = getattr(self, name)
            if value < 0:
                raise ValueError(f"{name} stat points must be non-negative, got {value}")
        return self

    @property
    def values(self) -> tuple[int, ...]:
        return tuple(getattr(self, name) for name in STAT_NAMES)

    @property
    def total(self) -> int:
        return sum(self.values)
