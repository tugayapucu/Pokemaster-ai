"""Abilities that put a terrain up the moment their holder arrives.

Transcribed from `data/abilities.ts`. The companion of `weather_on_arrival`:
Team Preview needs both to know what field its own side creates.
"""

import pytest

from champions_ai.mechanics.abilities import terrain_on_arrival


@pytest.mark.parametrize(
    ("ability", "terrain"),
    [
        ("electricsurge", "electricterrain"),
        ("grassysurge", "grassyterrain"),
        ("mistysurge", "mistyterrain"),
        ("psychicsurge", "psychicterrain"),
        ("hadronengine", "electricterrain"),
    ],
)
def test_each_surge_names_the_terrain_the_engine_sets(ability, terrain):
    assert terrain_on_arrival(ability) == terrain


def test_seed_sower_sets_its_terrain_when_hit_not_on_arrival():
    assert terrain_on_arrival("seedsower") is None


@pytest.mark.parametrize("ability", [None, "", "intimidate", "drizzle"])
def test_everything_else_sets_no_terrain(ability):
    """Drizzle included: a weather setter is not a terrain setter."""
    assert terrain_on_arrival(ability) is None
