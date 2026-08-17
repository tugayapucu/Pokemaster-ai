"""Move target types, which gate legal-action generation.

The vocabulary is copied from Showdown rather than invented, so the failure
mode is omission: a target the engine uses and we do not accept makes the
tracker reject the engine's own request payload.
"""

import pytest
from pydantic import ValidationError

from champions_ai.domain.move_data import TARGETS_REQUIRING_CHOICE, MoveData

# Showdown's complete MoveTarget union, from sim/dex-moves.ts.
SHOWDOWN_TARGETS = (
    "adjacentAlly",
    "adjacentAllyOrSelf",
    "adjacentFoe",
    "all",
    "allAdjacent",
    "allAdjacentFoes",
    "allies",
    "allySide",
    "allyTeam",
    "any",
    "foeSide",
    "normal",
    "randomNormal",
    "scripted",
    "self",
)


@pytest.mark.parametrize("target", SHOWDOWN_TARGETS)
def test_every_showdown_target_is_accepted(target):
    assert MoveData(move_id="x", target=target).target == target


def test_allies_is_accepted():
    """Howl and Life Dew are legal Champions moves and both target `allies`.

    This was missing, so the tracker raised a ValidationError while reading a
    perfectly ordinary request -- the crash needed only an opponent holding
    Life Dew.
    """
    assert MoveData(move_id="lifedew", target="allies").target == "allies"


def test_allies_needs_no_target_choice():
    """It hits the whole side, so the player is not asked to aim it."""
    assert not MoveData(move_id="howl", target="allies").requires_target_choice


def test_an_unknown_target_is_rejected():
    with pytest.raises(ValidationError):
        MoveData(move_id="x", target="adjacentEverything")


def test_targets_requiring_choice_are_all_real_targets():
    assert TARGETS_REQUIRING_CHOICE <= set(SHOWDOWN_TARGETS)
