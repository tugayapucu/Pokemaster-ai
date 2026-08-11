from pydantic import BaseModel, model_validator

MIN_STAGE = -6
MAX_STAGE = 6


class Boosts(BaseModel, frozen=True):
    """In-battle stat stage boosts, -6 to +6 per stat (rule is identical across Pokemon games)."""

    attack: int = 0
    defense: int = 0
    special_attack: int = 0
    special_defense: int = 0
    speed: int = 0
    accuracy: int = 0
    evasion: int = 0

    @model_validator(mode="after")
    def _check_range(self) -> "Boosts":
        for name, value in self.model_dump().items():
            if not MIN_STAGE <= value <= MAX_STAGE:
                raise ValueError(
                    f"{name} stage must be between {MIN_STAGE} and {MAX_STAGE}, got {value}"
                )
        return self

    def clamped_add(self, stat: str, delta: int) -> "Boosts":
        current = getattr(self, stat)
        new_value = max(MIN_STAGE, min(MAX_STAGE, current + delta))
        return self.model_copy(update={stat: new_value})
