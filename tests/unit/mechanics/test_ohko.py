"""One-hit knockout moves.

Fissure, Guillotine, Horn Drill and Sheer Cold all carry a zero base power,
no `basePowerCallback`, no `onBasePower` and no damage callback -- so
`is_damaging` classed all four as *status moves*. That is the **fourth**
distinct reason a move in this dex can have no base power, after the per-hit
callbacks, the situational multipliers and the fixed-damage callbacks.

The engine ignores every accuracy modifier for these and uses a flat 30,
dropping to 20 for Sheer Cold from a non-Ice user, plus the level difference
-- which is always zero in a format where everything is level 50. The named
type is outright immune, which a dumped accuracy of 30 cannot express.
"""

import pytest

from champions_ai.dex import BaseStats, MoveInfo, SpeciesInfo
from champions_ai.mechanics import fixed_damage, ohko_chance


def _move(move_id, ohko=None):
    return MoveInfo(
        move_id=move_id, name=move_id, type="Normal", category="Physical",
        base_power=0, accuracy=30, priority=0, target="normal", ohko=ohko,
    )


def _species(name, *types):
    return SpeciesInfo(
        species_id=name.lower(), name=name, types=types or ("Normal",),
        base_stats=BaseStats(hp=100, attack=100, defense=100,
                             special_attack=100, special_defense=100, speed=100),
    )


ORDINARY = _species("Garchomp", "Dragon", "Ground")
ICY = _species("Glaceon", "Ice")


def test_an_ohko_move_is_not_a_status_move():
    assert _move("fissure", ohko=True).is_damaging
    assert _move("sheercold", ohko="Ice").is_damaging


def test_an_ohko_move_deals_the_whole_remaining_bar():
    move = _move("fissure", ohko=True)
    assert fixed_damage(move, level=50, defender_hp=194) == 194
    assert fixed_damage(move, level=50, defender_hp=12) == 12


def test_the_plain_ohko_moves_land_three_times_in_ten():
    for move_id in ("fissure", "guillotine", "horndrill"):
        chance = ohko_chance(_move(move_id, ohko=True), attacker=ORDINARY, defender=ORDINARY)
        assert chance == pytest.approx(0.30)


def test_sheer_cold_is_less_accurate_from_a_non_ice_user():
    move = _move("sheercold", ohko="Ice")
    assert ohko_chance(move, attacker=ICY, defender=ORDINARY) == pytest.approx(0.30)
    assert ohko_chance(move, attacker=ORDINARY, defender=ORDINARY) == pytest.approx(0.20)


def test_the_named_type_is_immune():
    """Ice types cannot be hit by Sheer Cold at all, which a dumped accuracy
    of 30 has no way of saying."""
    move = _move("sheercold", ohko="Ice")
    assert ohko_chance(move, attacker=ORDINARY, defender=ICY) == 0.0
    assert ohko_chance(move, attacker=ICY, defender=ICY) == 0.0


def test_immunity_beats_the_users_own_type():
    """An Ice user still cannot Sheer Cold another Ice type."""
    assert ohko_chance(_move("sheercold", ohko="Ice"), attacker=ICY, defender=ICY) == 0.0


def test_an_ordinary_move_is_not_an_ohko():
    ordinary = MoveInfo(
        move_id="tackle", name="Tackle", type="Normal", category="Physical",
        base_power=40, accuracy=100, priority=0, target="normal",
    )
    assert ohko_chance(ordinary, attacker=ORDINARY, defender=ORDINARY) is None
    assert fixed_damage(ordinary, level=50, defender_hp=100) is None
