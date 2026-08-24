"""Moves that land more than once, and moves that always crit.

Fourteen moves in this dex hit repeatedly and we predicted a single hit, so
Icicle Spear and Bullet Seed were scored at roughly a third of what they do.
The harness could not catch it either: it took the first damage line of a run
and threw the rest away, so the prediction and the measurement were wrong in
the same direction.
"""

import pytest

from champions_ai.dex import MoveInfo
from champions_ai.mechanics import critical_chance, expected_hits, hit_range


def _move(move_id, *, multihit=None, multiaccuracy=False, accuracy=100,
          crit_ratio=None, always_crits=None):
    return MoveInfo(
        move_id=move_id, name=move_id, type="Normal", category="Physical",
        base_power=25, accuracy=accuracy, priority=0, target="normal",
        multihit=multihit, multiaccuracy=multiaccuracy,
        crit_ratio=crit_ratio, always_crits=always_crits,
    )


def test_an_ordinary_move_lands_once():
    assert expected_hits(_move("tackle")) == 1.0
    assert hit_range(_move("tackle")) == (1, 1)


def test_a_two_to_five_hit_move_averages_three_point_one():
    """The engine samples 35/35/15/15 for 2/3/4/5, not uniformly, so the
    midpoint of the range would overstate it."""
    spear = _move("iciclespear", multihit=(2, 5))
    assert expected_hits(spear) == pytest.approx(3.1)
    assert hit_range(spear) == (2, 5)


def test_a_fixed_count_is_exact():
    assert expected_hits(_move("dualwingbeat", multihit=2)) == 2.0
    assert hit_range(_move("dualwingbeat", multihit=2)) == (2, 2)


def test_a_multiaccuracy_move_stops_at_the_first_miss():
    """Triple Axel rolls for each hit, so a 90% move lands 0.9 + 0.81 + 0.729
    times rather than three."""
    axel = _move("tripleaxel", multihit=3, multiaccuracy=True, accuracy=90)
    assert expected_hits(axel) == pytest.approx(2.439)


def test_the_range_still_spans_the_whole_run():
    """A knockout claim has to hold for the fewest hits the move can get."""
    assert hit_range(_move("populationbomb", multihit=10)) == (10, 10)
    assert hit_range(_move("bulletseed", multihit=(2, 5))) == (2, 5)


# ------------------------------------------------------------- critical hits


def test_the_ordinary_crit_chance():
    assert critical_chance(_move("tackle")) == pytest.approx(1 / 24)
    assert critical_chance(_move("tackle", crit_ratio=1)) == pytest.approx(1 / 24)


@pytest.mark.parametrize("ratio, chance", [(2, 1 / 8), (3, 1 / 2), (4, 1.0)])
def test_a_widened_crit_stage(ratio, chance):
    assert critical_chance(_move("stoneedge", crit_ratio=ratio)) == pytest.approx(chance)


def test_a_move_that_always_crits_is_a_certainty_not_a_chance():
    """Frost Breath, Storm Throw and Flower Trick. The calibration excluded
    them as "crits" rather than predicting them as the certainties they are."""
    assert critical_chance(_move("frostbreath", always_crits=True)) == 1.0
