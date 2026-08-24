"""Moves that decide their own type when they are used.

Four in this dex, and each read the *wrong row of the type chart* until now.
The type is not cosmetic: it decides effectiveness, immunity and whether STAB
applies, so a Weather Ball in sun is a Fire move that is super effective
against a Grass type the chart would have called neutral.
"""

import pytest

from champions_ai.dex import BaseStats, MoveInfo, SpeciesInfo
from champions_ai.mechanics import dynamic_base_power, effective_type


def _move(move_id, move_type="Normal", base_power=50, modifies=True):
    return MoveInfo(
        move_id=move_id, name=move_id, type=move_type, category="Special",
        base_power=base_power, accuracy=100, priority=0, target="normal",
        modifies_type=modifies,
    )


def _species(name, *types, base=None):
    return SpeciesInfo(
        species_id=name.lower(), name=name, types=types or ("Normal",),
        base_stats=BaseStats(hp=100, attack=100, defense=100,
                             special_attack=100, special_defense=100, speed=100),
        base_species=base or name,
    )


# ------------------------------------------------------------- Weather Ball


@pytest.mark.parametrize("weather, expected", [
    ("sunnyday", "Fire"), ("desolateland", "Fire"),
    ("raindance", "Water"), ("primordialsea", "Water"),
    ("sandstorm", "Rock"), ("snowscape", "Ice"), ("hail", "Ice"),
    (None, "Normal"),
])
def test_weather_ball_takes_the_weathers_type(weather, expected):
    assert effective_type(_move("weatherball"), weather=weather) == expected


def test_weather_ball_also_doubles_its_power_in_weather():
    """A separate engine hook from the type change, so a separate rule."""
    move = _move("weatherball")
    assert dynamic_base_power(move, weather="sunnyday") == 100
    assert dynamic_base_power(move, weather=None) == 50


# ------------------------------------------------------------ Terrain Pulse


@pytest.mark.parametrize("terrain, expected", [
    ("electricterrain", "Electric"), ("grassyterrain", "Grass"),
    ("mistyterrain", "Fairy"), ("psychicterrain", "Psychic"),
    (None, "Normal"),
])
def test_terrain_pulse_takes_the_terrains_type(terrain, expected):
    assert effective_type(_move("terrainpulse"), terrain=terrain) == expected


# ------------------------------------------------ the forme-dependent pair


@pytest.mark.parametrize("forme, expected", [
    ("Tauros-Paldea-Combat", "Fighting"),
    ("Tauros-Paldea-Blaze", "Fire"),
    ("Tauros-Paldea-Aqua", "Water"),
    # The ordinary Tauros keeps the move's own type.
    ("Tauros", "Normal"),
])
def test_raging_bull_depends_on_which_tauros(forme, expected):
    move = _move("ragingbull", move_type="Normal", base_power=90)
    assert effective_type(move, attacker=_species(forme, "Normal")) == expected


def test_aura_wheel_depends_on_which_morpeko():
    move = _move("aurawheel", move_type="Electric", base_power=110)
    assert effective_type(move, attacker=_species("Morpeko", "Electric")) == "Electric"
    assert effective_type(
        move, attacker=_species("Morpeko-Hangry", "Electric")
    ) == "Dark"


# ------------------------------------------------------------------- guards


def test_an_ordinary_move_keeps_its_own_type():
    """Safe to call for every move, so callers need not know the special four."""
    plain = _move("flamethrower", move_type="Fire", modifies=False)
    assert effective_type(plain, weather="raindance", terrain="grassyterrain") == "Fire"


def test_a_flagged_move_with_no_matching_condition_keeps_its_type():
    assert effective_type(_move("weatherball"), weather="somethingnew") == "Normal"
    assert effective_type(_move("ragingbull"), attacker=None) == "Normal"
