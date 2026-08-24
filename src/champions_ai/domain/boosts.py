from pydantic import BaseModel, model_validator

MIN_STAGE = -6
MAX_STAGE = 6

# Showdown's stat ids -> the fields below. HP is absent because it has no
# stage. Callers used to spell this out inline as `"attack" if physical else
# "special_attack"`, which cannot express a move that attacks with Defense.
BOOST_FIELDS = {
    "atk": "attack",
    "def": "defense",
    "spa": "special_attack",
    "spd": "special_defense",
    "spe": "speed",
    # Accuracy and evasion are stages too, and leaving them out meant the
    # tracker dropped `|-boost|...|accuracy|1` on the floor and the scorer
    # ignored the accuracy half of Coil and Hone Claws.
    "accuracy": "accuracy",
    "evasion": "evasion",
}


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

    @property
    def positive_total(self) -> int:
        """Sum of the positive stages, accuracy and evasion included.

        Showdown's `positiveBoosts()`, which is what Stored Power and Power
        Trip add 20 base power per point of.
        """
        return sum(value for value in self.model_dump().values() if value > 0)

    def stage(self, stat: str) -> int:
        """The stage on `stat`, named by Showdown's id.

        A stat with no stage -- HP, or an id we do not recognise -- reads as
        zero, so a caller gets "unboosted" rather than an AttributeError.
        """
        field = BOOST_FIELDS.get(stat)
        return getattr(self, field) if field else 0

    def clamped_add(self, stat: str, delta: int) -> "Boosts":
        current = getattr(self, stat)
        new_value = max(MIN_STAGE, min(MAX_STAGE, current + delta))
        return self.model_copy(update={stat: new_value})
