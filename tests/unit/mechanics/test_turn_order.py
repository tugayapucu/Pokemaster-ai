"""Who acts first.

The heuristic's version consulted priority for *our* move and never for
theirs, and treated every negative priority as zero. Priority is a static
field on every move, dumped from the engine, running +5 to -7 in this dex --
we had the number all along and only asked whether it was above zero.

Transcribed from `comparePriority` and `getActionSpeed`: priority descending,
then Speed descending, ties at random, and Trick Room reversing the Speed half
by ordering on `10000 - speed`.
"""

import pytest

from champions_ai.mechanics import effective_speed, moves_first

# --------------------------------------------------------------- speed itself


def test_stat_stages_reach_the_speed_used_for_ordering():
    """The request reports Speed without stages applied, the same gap that
    made our own Swords Dance raise nothing."""
    assert effective_speed(100, boost_stage=2) == 200
    assert effective_speed(100, boost_stage=-1) == 66
    assert effective_speed(100, boost_stage=0) == 100


def test_tailwind_doubles_speed():
    assert effective_speed(100, tailwind=True) == 200


def test_paralysis_halves_speed():
    assert effective_speed(100, paralysed=True) == 50


def test_paralysis_is_applied_after_everything_else():
    """The engine sets `onModifySpePriority: -101` to guarantee this, and its
    own comment says paralysis occurs after all other Speed modifiers.

    On these numbers both orders agree, so the test pins the pipeline on a
    case where rounding could separate them.
    """
    # +1 is a 1.5x stage: 65 -> 97 -> 194 with Tailwind -> 97 paralysed.
    assert effective_speed(65, boost_stage=1, tailwind=True, paralysed=True) == 97
    # Halving first would give 32 -> 48 -> 96, one lower.
    assert effective_speed(65, boost_stage=1, tailwind=True, paralysed=True) != 96


# ------------------------------------------------------------------- the rule


def test_higher_priority_wins_regardless_of_speed():
    assert moves_first(3, 50, 0, 200) == 1.0
    assert moves_first(0, 200, 3, 50) == 0.0


def test_equal_priority_is_settled_by_speed():
    assert moves_first(0, 200, 0, 50) == 1.0
    assert moves_first(0, 50, 0, 200) == 0.0


def test_a_speed_tie_is_a_coin_flip():
    """The engine gathers every action that compares equal and shuffles them,
    so 0.5 is the honest answer rather than a hedge."""
    assert moves_first(0, 120, 0, 120) == 0.5
    assert moves_first(3, 120, 3, 120) == 0.5


def test_a_move_with_the_same_priority_is_not_beaten_by_ours():
    """Fake Out into a Fake Out is decided on Speed. Reading only our own
    priority made it read as guaranteed."""
    assert moves_first(3, 50, 3, 200) == 0.0
    assert moves_first(3, 200, 3, 50) == 1.0


@pytest.mark.parametrize("priority", [-3, -4, -5, -6, -7])
def test_negative_priority_loses_to_an_ordinary_move(priority):
    """Focus Punch, Avalanche, Counter, Dragon Tail and Trick Room all move
    last. Treating anything not above zero as zero scored every one of them as
    going first whenever its user was faster."""
    assert moves_first(priority, 200, 0, 50) == 0.0
    assert moves_first(0, 50, priority, 200) == 1.0


# ------------------------------------------------------------------ trick room


def test_trick_room_reverses_the_speed_half():
    assert moves_first(0, 50, 0, 200, trick_room=True) == 1.0
    assert moves_first(0, 200, 0, 50, trick_room=True) == 0.0


def test_trick_room_leaves_the_priority_half_alone():
    """It orders on `10000 - speed`, which never touches priority: a Fake Out
    still moves before an Extreme Speed under Trick Room."""
    assert moves_first(3, 50, 2, 200, trick_room=True) == 1.0
    assert moves_first(2, 50, 3, 200, trick_room=True) == 0.0


def test_a_speed_tie_is_still_a_tie_under_trick_room():
    assert moves_first(0, 120, 0, 120, trick_room=True) == 0.5
