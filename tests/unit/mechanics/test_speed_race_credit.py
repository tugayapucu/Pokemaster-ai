"""A partial credit for the hit that moving first denies.

0055 credited the whole denied hit in races longer than one hit, and speed then
outweighed the entire damage trade in 35% of pool pairings. `race_credit` scales
that credit; 0056 sweeps it. The endpoints must be exactly the two rules already
measured: 0 is the one-hit rule, 1 is 0055's.
"""

import pytest

from champions_ai.mechanics.matchup import order_edge

FAST, SLOW = 120, 100


def _edge(offence, defence, ours, theirs, credit, our_ko=0.0, their_ko=0.0):
    return order_edge(
        offence, defence, our_ko, their_ko, ours, theirs,
        beyond_knockouts=True, race_credit=credit,
    )


def test_half_credit_is_half_the_denied_hit():
    """Two hits each, faster: 0055 credits their whole 0.6; half credit is 0.3."""
    assert _edge(0.6, 0.6, FAST, SLOW, 0.5) == pytest.approx(0.3)
    assert _edge(0.6, 0.6, SLOW, FAST, 0.5) == pytest.approx(-0.3)


@pytest.mark.parametrize(
    ("offence", "defence", "our_ko", "their_ko", "ours", "theirs"),
    [
        (0.6, 0.6, 0.0, 0.0, FAST, SLOW),
        (0.6, 0.4, 0.0, 0.0, FAST, SLOW),
        (1.0, 0.3, 0.5, 0.0, FAST, SLOW),
        (0.3, 1.0, 0.0, 1.0, SLOW, FAST),
    ],
)
def test_zero_credit_is_the_one_hit_rule_exactly(offence, defence, our_ko, their_ko, ours, theirs):
    one_hit = order_edge(offence, defence, our_ko, their_ko, ours, theirs)
    assert _edge(offence, defence, ours, theirs, 0.0, our_ko, their_ko) == one_hit


def test_full_credit_is_the_0055_rule_exactly():
    assert _edge(0.6, 0.6, FAST, SLOW, 1.0) == order_edge(
        0.6, 0.6, 0.0, 0.0, FAST, SLOW, beyond_knockouts=True
    )


@pytest.mark.parametrize("credit", [0.0, 0.25, 0.5, 1.0])
def test_a_one_hit_race_ignores_the_credit(credit):
    assert _edge(1.0, 0.3, FAST, SLOW, credit, our_ko=0.5) == pytest.approx(0.5 * 0.3)


@pytest.mark.parametrize("credit", [-0.1, 1.5])
def test_a_credit_outside_zero_to_one_is_refused(credit):
    with pytest.raises(ValueError):
        _edge(0.6, 0.6, FAST, SLOW, credit)
