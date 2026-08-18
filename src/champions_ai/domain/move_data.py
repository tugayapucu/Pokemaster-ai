from typing import Literal

from pydantic import BaseModel

# Showdown's move target vocabulary, kept verbatim so the eventual data adapter
# is a straight copy rather than a lossy translation.
MoveTargetType = Literal[
    "normal",
    "any",
    "adjacentFoe",
    "adjacentAlly",
    "adjacentAllyOrSelf",
    "self",
    "allAdjacentFoes",
    "allAdjacent",
    "all",
    "foeSide",
    "allySide",
    # Every active Pokemon on the user's side, as distinct from `allyTeam`,
    # which reaches the bench too. Champions has Howl and Life Dew, so this is
    # reachable in ordinary play -- omitting it made the tracker reject the
    # engine's own request payload the moment either was active.
    "allies",
    "allyTeam",
    "randomNormal",
    "scripted",
]

# The only target types where the player picks a slot. Everything else either
# hits a fixed set (spread moves, field effects) or is chosen by the engine.
TARGETS_REQUIRING_CHOICE: frozenset[str] = frozenset(
    {"normal", "any", "adjacentFoe", "adjacentAlly", "adjacentAllyOrSelf"}
)


# Moves that drive the engine's "stall" counter: using one on consecutive turns
# makes it increasingly likely to fail. Vocabulary rather than logic, so it
# lives beside the move targets and both the tracker and any agent read it
# from here.
PROTECT_MOVES: frozenset[str] = frozenset(
    {
        "protect",
        "detect",
        "kingsshield",
        "spikyshield",
        "banefulbunker",
        "obstruct",
        "silktrap",
        "burningbulwark",
        "maxguard",
    }
)


class MoveData(BaseModel, frozen=True):
    """The minimum a move must expose for legal-action generation.

    Deliberately not a full move model -- power, accuracy, type, and effects
    are irrelevant to *whether an action is legal* and belong with the damage
    calculator instead.
    """

    move_id: str
    target: MoveTargetType

    @property
    def requires_target_choice(self) -> bool:
        return self.target in TARGETS_REQUIRING_CHOICE
