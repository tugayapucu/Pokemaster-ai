"""Moves that ignore the damage formula.

Nine of them here, and every one carries a zero base power with no
`basePowerCallback` -- so `is_damaging` classed all nine as *status moves* and
the heuristic scored Seismic Toss, Night Shade and Super Fang as support. The
same silent failure as the eleven dynamic-power moves, through a third
mechanism.

Found by following the damage differential, where Super Fang showed up as
`predicted 0-0, engine dealt 76`.
"""

import pytest

from champions_ai.dex import MoveInfo
from champions_ai.mechanics import fixed_damage


def _move(move_id, *, fixed=None, callback=False, category="Physical"):
    return MoveInfo(
        move_id=move_id, name=move_id, type="Normal", category=category,
        base_power=0, accuracy=100, priority=0, target="normal",
        fixed_damage=fixed, damage_callback=callback,
    )


def test_a_normal_move_has_no_fixed_damage():
    """None means "use the formula", which is not the same as zero damage."""
    ordinary = MoveInfo(
        move_id="tackle", name="Tackle", type="Normal", category="Physical",
        base_power=40, accuracy=100, priority=0, target="normal",
    )
    assert fixed_damage(ordinary, level=50, defender_hp=200) is None


@pytest.mark.parametrize("move_id", ["seismictoss", "nightshade"])
def test_level_damage_is_exactly_the_level(move_id):
    move = _move(move_id, fixed="level")
    assert fixed_damage(move, level=50, defender_hp=200) == 50
    assert fixed_damage(move, level=100, defender_hp=200) == 100
    # And it does not care how healthy the target is.
    assert fixed_damage(move, level=50, defender_hp=17) == 50


def test_super_fang_halves_what_the_target_has_left():
    move = _move("superfang", callback=True)
    assert fixed_damage(move, level=50, defender_hp=200) == 100
    assert fixed_damage(move, level=50, defender_hp=101) == 50


def test_super_fang_always_does_at_least_one():
    """`clampIntRange(hp / 2, 1)` -- a target on its last point still takes a
    point, so the move never reads as harmless."""
    move = _move("superfang", callback=True)
    assert fixed_damage(move, level=50, defender_hp=1) == 1


def test_endeavor_brings_the_target_down_to_us():
    move = _move("endeavor", callback=True)
    assert fixed_damage(move, level=50, defender_hp=200, attacker_hp=30) == 170


def test_endeavor_does_nothing_when_we_are_the_healthier_one():
    move = _move("endeavor", callback=True)
    assert fixed_damage(move, level=50, defender_hp=30, attacker_hp=200) == 0


def test_final_gambit_deals_our_whole_remaining_bar():
    move = _move("finalgambit", callback=True, category="Special")
    assert fixed_damage(move, level=50, defender_hp=200, attacker_hp=140) == 140


@pytest.mark.parametrize(
    "move_id", ["counter", "mirrorcoat", "metalburst", "comeuppance"]
)
def test_a_reflecting_move_reads_as_damaging_even_at_zero(move_id):
    """They need the damage taken this turn, which nothing tracks, so zero is
    the honest answer. The part that was wrong is that they read as *status*
    moves and were scored as support."""
    move = _move(move_id, callback=True)
    assert fixed_damage(move, level=50, defender_hp=200) == 0
    assert move.is_damaging
