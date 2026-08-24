"""What types a Pokemon has right now, and whether it is on the ground.

Found by measurement rather than by reading the rules. A control run of the
damage harness read 90.0% instead of the usual 95%, and one mechanic explained
every large mismatch in it: Roost strips the user's Flying type for the turn.

The run-to-run swing in that harness was never noise. It was whether the
randomly generated team happened to draw a Pokemon that Roosts.
"""

import pytest

from champions_ai.mechanics import effective_types, is_grounded

ALTARIA = ("Dragon", "Flying")
CORVIKNIGHT = ("Flying", "Steel")
GARCHOMP = ("Dragon", "Ground")


def test_roost_strips_the_flying_type():
    assert effective_types(ALTARIA, ["roost"]) == ("Dragon",)
    assert effective_types(CORVIKNIGHT, ["roost"]) == ("Steel",)


def test_a_pure_flying_type_becomes_normal_rather_than_typeless():
    assert effective_types(("Flying",), ["roost"]) == ("Normal",)


def test_without_roost_nothing_changes():
    assert effective_types(ALTARIA, []) == ALTARIA
    assert effective_types(ALTARIA, ["protect", "confusion"]) == ALTARIA


def test_the_types_are_untouched_for_a_non_flyer():
    assert effective_types(GARCHOMP, ["roost"]) == GARCHOMP


# ------------------------------------------------------------------ grounding


def test_a_flying_type_is_not_grounded():
    assert not is_grounded(ALTARIA)
    assert is_grounded(GARCHOMP)


def test_roosting_puts_a_flyer_on_the_ground():
    """The two questions are the same one, which is why they share a module."""
    assert is_grounded(effective_types(ALTARIA, ["roost"]))


def test_levitate_and_an_air_balloon_lift_a_grounded_type():
    assert not is_grounded(GARCHOMP, ability="levitate")
    assert not is_grounded(GARCHOMP, item="airballoon")


@pytest.mark.parametrize("kwargs", [
    {"item": "ironball"},
    {"field_conditions": ["gravity"]},
    {"volatiles": ["smackdown"]},
    {"volatiles": ["ingrain"]},
])
def test_some_things_drag_anything_back_down(kwargs):
    """These override the type and the ability, which is the point of them."""
    assert is_grounded(ALTARIA, **kwargs)
    assert is_grounded(GARCHOMP, ability="levitate", **kwargs)
