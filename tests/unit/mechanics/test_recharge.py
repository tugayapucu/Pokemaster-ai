"""Recharge moves: the hit now, then a turn of nothing -- but only if it hit.

`self: { volatileStatus: 'mustrecharge' }` is applied by `selfDrops`, which
skips targets the move did not hit. So a miss costs no recharge and a hit does,
knockout included. The price follows: expected damage p * D over expected
turns 1 + p, which is 1 / (1 + p) of an ordinary move per turn.
"""

import pytest

from champions_ai.dex import MoveInfo
from champions_ai.mechanics.charge import recharge_multiplier


def _move(accuracy, recharge=True):
    return MoveInfo(
        move_id="megablast", name="Mega Blast", type="Normal", category="Special",
        base_power=150, accuracy=accuracy, priority=0, target="normal",
        flags=frozenset({"recharge", "protect"} if recharge else {"protect"}),
    )


def test_an_ordinary_move_costs_nothing_extra():
    assert recharge_multiplier(_move(100, recharge=False)) == 1.0


def test_a_move_that_cannot_miss_is_worth_half_per_turn():
    """Two turns for one hit, every time: the charge move's price exactly."""
    assert recharge_multiplier(_move(100)) == pytest.approx(0.5)


def test_a_move_that_can_miss_is_worth_a_little_more_than_half():
    """A miss wastes one turn rather than two, which is what lifts it above
    half: 0.9 * D over 1.9 expected turns."""
    assert recharge_multiplier(_move(90)) == pytest.approx(1 / 1.9)
    assert recharge_multiplier(_move(90)) > recharge_multiplier(_move(100))
