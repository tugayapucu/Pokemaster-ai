"""Reference data pulled from the real engine.

Guards the seam where Showdown's vocabulary meets ours. Hand-copied enums drift
silently: the domain accepted every move target we had thought of, and Champions
turned out to use one more (`allies`, on Howl and Life Dew), which crashed the
tracker on a perfectly ordinary request. A unit test could not have caught it,
because the missing value was missing from the test data too.
"""

from champions_ai.dex import Dex
from champions_ai.domain.move_data import MoveData


def test_every_move_target_in_the_dex_is_one_we_accept(bridge):
    dex = Dex.load(bridge)
    unknown = sorted(
        {
            info.target
            for info in dex.moves.values()
            if not _accepted(info.move_id, info.target)
        }
    )
    assert not unknown, f"MoveTargetType is missing target types the engine uses: {unknown}"


def _accepted(move_id: str, target: str) -> bool:
    try:
        MoveData(move_id=move_id, target=target)
    except ValueError:
        return False
    return True


def test_the_dex_actually_loaded(bridge):
    """Guards against the test above passing vacuously on an empty dump."""
    dex = Dex.load(bridge)
    assert len(dex.species) > 100
    assert len(dex.moves) > 100
