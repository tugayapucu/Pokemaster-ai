from pydantic import BaseModel, model_validator

MAX_PER_STAT = 32
MAX_TOTAL = 66


class StatSpread(BaseModel, frozen=True):
    """A Pokemon's Stat Points allocation (Champions' EV/IV replacement, see ADR 0002)."""

    hp: int = 0
    attack: int = 0
    defense: int = 0
    special_attack: int = 0
    special_defense: int = 0
    speed: int = 0

    @model_validator(mode="after")
    def _check_limits(self) -> "StatSpread":
        values = (
            self.hp,
            self.attack,
            self.defense,
            self.special_attack,
            self.special_defense,
            self.speed,
        )
        for value in values:
            if not 0 <= value <= MAX_PER_STAT:
                raise ValueError(f"stat points must be between 0 and {MAX_PER_STAT}, got {value}")
        total = sum(values)
        if total > MAX_TOTAL:
            raise ValueError(f"stat points total {total} exceeds the limit of {MAX_TOTAL}")
        return self
