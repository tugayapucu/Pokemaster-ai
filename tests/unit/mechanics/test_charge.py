"""Charge moves: when the turn is spent charging, and when the engine skips it.

Every case below is a line of `data/moves.ts`, `data/items.ts` or
`Pokemon.effectiveWeather()` at the pinned build. The mechanics are exact, so
these are tested as facts; only the 0.5 that prices a charging turn is a
modelling choice, and its test pins the derivation rather than a tuned value.
"""

import pytest

from champions_ai.dex import MoveInfo
from champions_ai.mechanics.charge import CHARGE_TURN_MULTIPLIER, charges_this_turn


def _move(move_id, move_type="Grass", charge=True):
    return MoveInfo(
        move_id=move_id, name=move_id, type=move_type, category="Special",
        base_power=120, accuracy=100, priority=0, target="normal",
        flags=frozenset({"charge", "protect"} if charge else {"protect"}),
    )


SOLAR_BEAM = _move("solarbeam")
ELECTRO_SHOT = _move("electroshot", "Electric")
METEOR_BEAM = _move("meteorbeam", "Rock")
ORDINARY = _move("energyball", charge=False)


def test_a_move_without_the_flag_never_charges():
    assert not charges_this_turn(ORDINARY, weather=None)


@pytest.mark.parametrize("weather", [None, "raindance", "sandstorm", "snowscape"])
def test_solar_beam_charges_outside_the_sun(weather):
    """Rain, sand and snow also halve it -- `base_power` does that part -- but
    none of them skips the charge."""
    assert charges_this_turn(SOLAR_BEAM, weather=weather)


@pytest.mark.parametrize("weather", ["sunnyday", "desolateland"])
def test_solar_beam_fires_at_once_in_the_sun(weather):
    assert not charges_this_turn(SOLAR_BEAM, weather=weather)


def test_electro_shot_is_skipped_by_rain_not_by_sun():
    assert not charges_this_turn(ELECTRO_SHOT, weather="raindance")
    assert not charges_this_turn(ELECTRO_SHOT, weather="primordialsea")
    assert charges_this_turn(ELECTRO_SHOT, weather="sunnyday")


@pytest.mark.parametrize("weather", [None, "sunnyday", "raindance"])
def test_meteor_beam_always_charges(weather):
    assert charges_this_turn(METEOR_BEAM, weather=weather)


@pytest.mark.parametrize("move", [SOLAR_BEAM, ELECTRO_SHOT, METEOR_BEAM])
def test_power_herb_skips_every_charge(move):
    assert not charges_this_turn(move, weather=None, item="powerherb")


def test_utility_umbrella_hides_the_sun_from_its_holder():
    assert charges_this_turn(SOLAR_BEAM, weather="sunnyday", item="utilityumbrella")


def test_mega_sol_brings_its_own_sun_except_to_electro_shot():
    """`effectiveWeather()` returns sun for a Mega Sol user unless the move is
    Electro Shot -- and it is checked before the umbrella."""
    assert not charges_this_turn(SOLAR_BEAM, weather=None, ability="megasol")
    assert not charges_this_turn(
        SOLAR_BEAM, weather=None, ability="megasol", item="utilityumbrella"
    )
    assert charges_this_turn(ELECTRO_SHOT, weather=None, ability="megasol")
    assert not charges_this_turn(ELECTRO_SHOT, weather="raindance", ability="megasol")


def test_the_second_turn_always_fires():
    assert not charges_this_turn(METEOR_BEAM, weather=None, already_charging=True)


def test_a_charging_turn_is_priced_at_one_hit_over_two_turns():
    """Two turns committed, one hit delivered. If this changes, the reason
    should be a measured one, not a tuned one."""
    assert CHARGE_TURN_MULTIPLIER == 0.5
