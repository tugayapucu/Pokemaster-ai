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


# Moves that drive the engine's shared "stall" counter (`stallingMove` in
# Showdown's move data): each consecutive use succeeds a third as often as the
# last. Verified against the engine by an integration test, because a
# hand-copied list of engine facts is precisely what drifts.
STALL_MOVES: frozenset[str] = frozenset(
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
        "endure",
        "matblock",
    }
)

# The subset that actually *blocks the hit on its user*, which is a different
# question from sharing the counter and the one an agent pricing "damage
# avoided" needs:
#
# - **Endure** shares the counter but does not block anything -- the hit lands
#   and the user survives on 1 HP, so valuing it as damage avoided is simply
#   wrong;
# - **Mat Block** shields the whole side rather than the user, and only on the
#   turn it switches in.
#
# Wide Guard, Quick Guard and Crafty Shield are absent from both sets: they
# protect against a category of move, and since Gen 6 they do not touch the
# stall counter at all.
PROTECT_MOVES: frozenset[str] = STALL_MOVES - {"endure", "matblock"}


# Moves the engine refuses unless this is the user's first turn on the field
# (`activeMoveActions > 1` in Showdown's `onTry`). This is a *runtime* failure,
# not something the request reports as disabled -- confirmed by a human in our
# own replay data selecting Fake Out on turn two and getting the failure hint.
# So an agent that does not track it will burn turns on a move that cannot work.
FIRST_TURN_MOVES: frozenset[str] = frozenset({"fakeout", "firstimpression", "matblock"})


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
