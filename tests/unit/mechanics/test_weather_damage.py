"""Weather in the damage estimate.

Verified against `onWeatherModifyDamage` and `onModifySpD`/`onModifyDef` in the
engine's conditions.ts rather than from memory. Two of the four weathers are not
damage multipliers at all -- sandstorm raises a Rock-type's Special Defense and
snow raises an Ice-type's Defense -- and conflating those with Sun and Rain
would apply them to the wrong side of the calculation.
"""


from champions_ai.dex import Dex
from champions_ai.mechanics import estimate_damage

TYPES = ["Fire", "Water", "Rock", "Ice", "Normal"]


def _species(name, types):
    return {
        "name": name, "types": list(types),
        "baseStats": {"hp": 120, "atk": 120, "def": 100, "spa": 120, "spd": 100, "spe": 100},
        "abilities": [], "weightkg": 1.0, "baseSpecies": name,
    }


def _move(name, move_type, category="Physical"):
    return {
        "name": name, "type": move_type, "category": category, "basePower": 100,
        "accuracy": 100, "priority": 0, "target": "normal", "flags": [], "secondaries": [],
    }


DEX = Dex.from_payload({
    "species": {
        "burny": _species("Burny", ("Fire",)),
        "splashy": _species("Splashy", ("Water",)),
        "rocky": _species("Rocky", ("Rock",)),
        "icy": _species("Icy", ("Ice",)),
        "plain": _species("Plain", ("Normal",)),
    },
    "moves": {
        "flame": _move("Flame", "Fire"),
        "splash": _move("Splash", "Water"),
        "flamebeam": _move("Flamebeam", "Fire", "Special"),
        "bonk": _move("Bonk", "Normal"),
        "beam": _move("Beam", "Normal", "Special"),
    },
    "types": TYPES,
    "chart": {a: dict.fromkeys(TYPES, 1.0) for a in TYPES},
})


def _damage(move_id, defender_id, weather=None, attacker_id="plain"):
    return estimate_damage(
        DEX, DEX.get_move(move_id),
        attacker=DEX.get_species(attacker_id), attack_stat=150,
        defender=DEX.get_species(defender_id), defense_stat=130, defender_hp=200,
        level=50, doubles=False, weather=weather,
    ).average


def test_sun_boosts_fire_and_suppresses_water():
    plain = _damage("flame", "plain")
    assert _damage("flame", "plain", "sunnyday") > plain
    assert _damage("splash", "plain", "sunnyday") < _damage("splash", "plain")


def test_rain_boosts_water_and_suppresses_fire():
    assert _damage("splash", "plain", "raindance") > _damage("splash", "plain")
    assert _damage("flame", "plain", "raindance") < _damage("flame", "plain")


def test_weather_leaves_an_unrelated_type_alone():
    for weather in ("sunnyday", "raindance"):
        assert _damage("bonk", "plain", weather) == _damage("bonk", "plain")


def test_sandstorm_shields_a_rock_type_from_special_moves_only():
    """It raises Special Defense; it is not a damage multiplier."""
    assert _damage("beam", "rocky", "sandstorm") < _damage("beam", "rocky")
    assert _damage("bonk", "rocky", "sandstorm") == _damage("bonk", "rocky")


def test_sandstorm_does_nothing_for_a_non_rock_defender():
    assert _damage("beam", "plain", "sandstorm") == _damage("beam", "plain")


def test_snow_shields_an_ice_type_from_physical_moves_only():
    assert _damage("bonk", "icy", "snowscape") < _damage("bonk", "icy")
    assert _damage("beam", "icy", "snowscape") == _damage("beam", "icy")


def test_snow_does_nothing_for_a_non_ice_defender():
    assert _damage("bonk", "plain", "snowscape") == _damage("bonk", "plain")


def test_the_primal_weathers_negate_the_opposing_type_outright():
    """Not in Reg M-B, but wrong-by-omission is what the table exists to avoid."""
    assert _damage("splash", "plain", "desolateland") == 0
    assert _damage("flame", "plain", "primordialsea") == 0


def test_an_unknown_weather_is_ignored_rather_than_guessed_at():
    """A new weather should cost accuracy, never correctness."""
    assert _damage("flame", "plain", "fogofwar") == _damage("flame", "plain")
    assert _damage("flame", "plain", None) == _damage("flame", "plain")
