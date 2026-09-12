"""Abilities that put weather up the moment their holder arrives.

Transcribed from `data/abilities.ts`. The table exists for two consumers: a
Mega whose forme carries one of these has its weather up before it attacks on
the turn it evolves, and Team Preview should eventually know what field its own
side creates. Both need the same fact, so it lives once, next to Mega Sol --
which is the ability most easily mistaken for a setter, and is not one.
"""

import pytest

from champions_ai.mechanics import weather_on_arrival


@pytest.mark.parametrize(
    ("ability", "weather"),
    [
        ("drought", "sunnyday"),
        ("drizzle", "raindance"),
        ("sandstream", "sandstorm"),
        ("snowwarning", "snowscape"),
        ("orichalcumpulse", "sunnyday"),
    ],
)
def test_each_setter_names_the_weather_the_engine_sets(ability, weather):
    assert weather_on_arrival(ability) == weather


def test_sand_spit_sets_sand_when_hit_not_on_arrival():
    assert weather_on_arrival("sandspit") is None


def test_mega_sol_reads_as_sun_but_sets_nothing():
    """The trap this table must not fall into: Mega Sol changes what its
    holder's own moves see, and the field is untouched."""
    assert weather_on_arrival("megasol") is None


@pytest.mark.parametrize("ability", [None, "", "intimidate"])
def test_everything_else_sets_nothing(ability):
    assert weather_on_arrival(ability) is None
