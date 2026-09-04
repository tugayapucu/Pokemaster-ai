"""What a score gap is worth, and where the calibration refuses to answer.

The refusals are the important half. A number on screen next to a move is read
as authoritative, so the two cases 0041 never measured -- a difference spread
across both slots, and an action the scorer ranked above its own pick -- return
None rather than a plausible-looking guess.
"""

from champions_ai.recommendation.calibration import BANDS, Cost, cost_of_gap


def test_the_three_measured_bands():
    assert cost_of_gap(0).band == "close"
    assert cost_of_gap(59).band == "close"
    assert cost_of_gap(60).band == "behind"
    assert cost_of_gap(249).band == "behind"
    assert cost_of_gap(250).band == "well behind"
    assert cost_of_gap(10_000).band == "well behind"


def test_points_rise_with_the_gap():
    """The whole finding, in one assertion: a bigger gap costs more."""
    close = cost_of_gap(10).points
    behind = cost_of_gap(150).points
    far = cost_of_gap(400).points

    assert close < behind < far


def test_a_two_slot_difference_is_refused():
    """0041 varied one slot at a time. Two is a sum nobody checked adds up.

    5.8% of shortlist entries in practice, so this is a real case and not a
    hypothetical -- and guessing there would put an unmeasured number on screen
    beside a measured one, indistinguishable to a reader.
    """
    assert cost_of_gap(150, slots_differing=2) is None
    assert cost_of_gap(150, slots_differing=0) is None
    assert cost_of_gap(150, slots_differing=1) is not None


def test_an_action_scored_above_the_pick_is_refused():
    """The joint scorer can produce this: a slot action can score higher on its
    own while the pair scores worse. 0041 saw it on 7% of candidates and
    measured nothing there."""
    assert cost_of_gap(-1) is None
    assert cost_of_gap(-200) is None


def test_the_wording_does_not_overclaim_at_the_bottom_band():
    """One point is inside the noise of the measurement it came from, so the
    close band must not read as a precise quantity."""
    assert str(cost_of_gap(10)) == "about level with the top choice"
    assert "behind" in str(cost_of_gap(150))
    assert "behind" in str(cost_of_gap(400))


def test_points_are_whole_numbers():
    """The held-out spread on the middle band was -6.6% to -2.8%. Printing a
    decimal would claim a tenth of a point the measurement cannot support."""
    for _, _, points in BANDS:
        assert isinstance(points, int)


def test_cost_is_comparable_and_frozen():
    assert Cost(band="close", points=1) == Cost(band="close", points=1)
    assert cost_of_gap(10) == cost_of_gap(20)
