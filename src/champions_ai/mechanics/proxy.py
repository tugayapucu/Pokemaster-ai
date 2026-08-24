"""Moves that stand in for another move.

Four moves in this dex do not have an effect of their own -- they borrow one.
Copycat repeats whatever went last, Sleep Talk picks from our own moveset,
Instruct makes an ally go again, Spite takes PP off what the target just used.

All four were unscoreable until the tracker learned which move went last, and
they are worth exactly what the move they stand in for is worth: a Copycat
after an Earthquake is an Earthquake, and pricing it as a generic support move
was wrong by however much an Earthquake is worth.

The engine already publishes which moves refuse to be borrowed, as flags on
the move. Those flags have been in the dump since the dump existed and nothing
read them, which is the recurring shape of bug in this project -- so they are
read here rather than re-derived.
"""

from collections.abc import Iterable

from champions_ai.dex import MoveInfo

# A move carrying the matching flag refuses to be borrowed by that mechanic.
COPYCAT_REFUSED = "failcopycat"
SLEEP_TALK_REFUSED = "nosleeptalk"
INSTRUCT_REFUSED = "failinstruct"

# Copycat, Sleep Talk and Instruct all carry their own refusal flag, so none of
# them can borrow itself. Copycat *can* borrow Sleep Talk, though, so borrowing
# is bounded by a depth rather than by trusting the flags to close every loop.
MAX_BORROW_DEPTH = 2

COPYCAT = "copycat"
SLEEP_TALK = "sleeptalk"
INSTRUCT = "instruct"
SPITE = "spite"
BORROWING_MOVES = frozenset({COPYCAT, SLEEP_TALK, INSTRUCT, SPITE})

# Instruct cannot restart something already in progress: a move that charges,
# recharges or locks its user in has no clean point to repeat from.
INSTRUCT_UNREPEATABLE_FLAGS = frozenset({"charge", "recharge"})


def copycat_borrows(last_move_used: MoveInfo | None) -> MoveInfo | None:
    """What Copycat would turn into, or None if it fails.

    Copycat reads the *field's* last move, not the user's, so it happily
    repeats the opponent's attack -- which is most of what makes it worth a
    slot and none of what a flat support value said about it.
    """
    if last_move_used is None or COPYCAT_REFUSED in last_move_used.flags:
        return None
    return last_move_used


def sleep_talk_candidates(
    moves: Iterable[MoveInfo], *, asleep: bool
) -> tuple[MoveInfo, ...]:
    """The moves Sleep Talk might pick, uniformly at random.

    Empty while awake, because the engine simply refuses the move -- that is a
    legality fact, and an agent that does not know it will happily throw away
    a turn on a Sleep Talk it cannot use.
    """
    if not asleep:
        return ()
    return tuple(m for m in moves if SLEEP_TALK_REFUSED not in m.flags)


def instruct_repeats(last_move: MoveInfo | None) -> MoveInfo | None:
    """What the instructed ally would be made to use again, or None if it fails."""
    if last_move is None or INSTRUCT_REFUSED in last_move.flags:
        return None
    if INSTRUCT_UNREPEATABLE_FLAGS & set(last_move.flags):
        return None
    return last_move


def spite_removes(last_move: MoveInfo | None) -> MoveInfo | None:
    """What Spite would take PP from, or None if it fails."""
    return last_move



def gains_from_repeating(move: MoveInfo) -> bool:
    """Whether using this move a second time in the same turn is worth anything.

    Instruct fires the repeat *immediately*, not next turn, and most support
    moves gain nothing from that: a second Protect in one turn fails outright,
    a second Tailwind re-sets what is already up, and a second Trick Room
    actively undoes the first. Damage adds up and stat stages stack, so those
    two are the ones worth doubling -- which is also what the move is played
    for in practice.

    Found by measuring: without this, the best-scoring repeat for one ally in
    the corpus came out as its Protect, at 310 points for an effect worth
    nothing.
    """
    return bool(move.is_damaging or move.boosts or move.self_boosts)
