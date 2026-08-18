"""Reference data pulled from the real engine.

Guards the seam where Showdown's vocabulary meets ours. Hand-copied enums drift
silently: the domain accepted every move target we had thought of, and Champions
turned out to use one more (`allies`, on Howl and Life Dew), which crashed the
tracker on a perfectly ordinary request. A unit test could not have caught it,
because the missing value was missing from the test data too.
"""

from champions_ai.dex import Dex
from champions_ai.domain.move_data import PROTECT_MOVES, STALL_MOVES, MoveData


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


def test_our_stall_move_list_matches_the_engine(bridge):
    """`STALL_MOVES` is a hand-copied engine fact, so it is checked against one.

    Getting it wrong is silent and reachable: Endure drives the same counter as
    Protect without blocking anything, and omitting it left the agent expecting
    a Protect to succeed where the engine gives it one chance in three.
    """
    dex = Dex.load(bridge)
    engine = {info.move_id for info in dex.moves.values() if info.stalling}
    assert engine, "the dex dump must actually carry the stallingMove flag"

    # Champions has a restricted move pool, so ours may legitimately name moves
    # this regulation omits -- but never the reverse.
    missing = sorted(engine - STALL_MOVES)
    assert not missing, f"STALL_MOVES is missing engine stalling moves: {missing}"


def test_protect_moves_are_stall_moves_that_actually_block(bridge):
    """Endure shares the counter but the hit still lands, so it must not be
    priced as damage avoided."""
    assert PROTECT_MOVES < STALL_MOVES
    assert "endure" not in PROTECT_MOVES
    assert "protect" in PROTECT_MOVES


def test_wide_and_quick_guard_do_not_touch_the_counter(bridge):
    """They protect a category of move and, since Gen 6, may be repeated."""
    dex = Dex.load(bridge)
    for move_id in ("wideguard", "quickguard"):
        assert not dex.get_move(move_id).stalling
        assert move_id not in STALL_MOVES
