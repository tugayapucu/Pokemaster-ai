"""The value of moving first, over a race of any length.

Moving first is worth the hit it denies: on the turn a side finishes the race,
the other side's attack that turn never lands. The old rule only counted a
one-hit race, which priced speed at nothing for a Pokemon that rarely knocks out
in one hit, however much faster it was.

`order_edge` is pure arithmetic, so each case below is exact.
"""

import math

import pytest

from champions_ai.mechanics.matchup import hits_to_knock_out, order_edge

FAST, SLOW = 120, 100


@pytest.mark.parametrize(
    ("fraction", "hits"),
    [(1.0, 1), (0.6, 2), (0.5, 2), (0.34, 3), (0.25, 4), (0.2, 5)],
)
def test_hits_to_knock_out(fraction, hits):
    """0.5 and 0.25 are the rounding traps: 1 / 0.5 must be 2, not 3."""
    assert hits_to_knock_out(fraction) == hits


def test_a_side_that_cannot_hurt_never_finishes():
    assert hits_to_knock_out(0.0) == math.inf


@pytest.mark.parametrize(
    ("offence", "defence", "our_ko", "their_ko", "ours", "theirs"),
    [
        (0.6, 0.6, 0.0, 0.0, FAST, SLOW),
        (0.6, 0.6, 0.0, 0.0, SLOW, FAST),
        (1.0, 0.3, 0.5, 0.0, FAST, SLOW),
        (0.3, 1.0, 0.0, 1.0, SLOW, FAST),
        (0.6, 0.4, 0.0, 0.0, FAST, FAST),
    ],
)
def test_off_is_the_old_rule_exactly(offence, defence, our_ko, their_ko, ours, theirs):
    if ours > theirs:
        old = our_ko * defence
    elif ours < theirs:
        old = -their_ko * offence
    else:
        old = 0.0
    assert order_edge(offence, defence, our_ko, their_ko, ours, theirs) == old


def _on(offence, defence, ours, theirs, our_ko=0.0, their_ko=0.0):
    return order_edge(
        offence, defence, our_ko, their_ko, ours, theirs, beyond_knockouts=True
    )


def test_two_hits_each_the_faster_side_denies_the_last_hit():
    """Two against two: moving first wins the race moving second would lose."""
    assert _on(0.6, 0.6, FAST, SLOW) == pytest.approx(0.6)
    assert _on(0.6, 0.6, SLOW, FAST) == pytest.approx(-0.6)


def test_needing_fewer_hits_the_faster_side_still_denies_one():
    """Two against three: we win either way, but first we take one hit fewer."""
    assert _on(0.6, 0.4, FAST, SLOW) == pytest.approx(0.4)


def test_needing_more_hits_speed_buys_nothing():
    """Three against two: they finish first whoever moves first."""
    assert _on(0.4, 0.6, FAST, SLOW) == 0.0


def test_a_one_hit_race_keeps_the_knockout_chance_rule():
    assert _on(1.0, 0.3, FAST, SLOW, our_ko=0.5) == pytest.approx(0.5 * 0.3)


def test_a_speed_tie_is_worth_nothing_either_way():
    assert _on(0.6, 0.6, FAST, FAST) == 0.0
