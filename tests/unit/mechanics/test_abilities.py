"""What an ability does to a hit.

Abilities were the largest single source of damage error left: measured
against the engine on fully random teams the model read **80.1%**, against
92.5% with items but inert abilities and 96-99% on the control.

The values were read off the residual before being written down, the same way
Life Orb was:

    hugepower     1.950  (n=54)    engine says x2
    hustle        1.472  (n=45)    x1.5
    toughclaws    1.243  (n=22)    x1.3 on contact
    ironfist      1.158  (n=59)    x1.2 on punches, so not every move
    adaptability  1.319  (n=60)    STAB 1.5 -> 2.0, which is 1.333
"""

import pytest

from champions_ai.dex import MoveInfo
from champions_ai.mechanics.abilities import (
    attack_multiplier,
    base_power_multiplier,
    defence_multiplier,
    rewritten_type,
    stab_multiplier,
    taken_multiplier,
)


def _move(move_id="hit", *, move_type="Normal", category="Physical",
          base_power=80, flags=(), secondaries=(), recoil=None):
    return MoveInfo(
        move_id=move_id, name=move_id, type=move_type, category=category,
        base_power=base_power, accuracy=100, priority=0, target="normal",
        flags=frozenset(flags), secondaries=tuple(secondaries), recoil=recoil,
    )


# ------------------------------------------------------- the attacking stat


@pytest.mark.parametrize("ability, expected", [
    ("hugepower", 2.0), ("purepower", 2.0), ("hustle", 1.5), ("levitate", 1.0),
])
def test_the_unconditional_attack_multipliers(ability, expected):
    assert attack_multiplier(ability, _move()) == expected


def test_a_pinch_ability_needs_both_the_type_and_the_health():
    fire = _move(move_type="Fire", category="Special")
    assert attack_multiplier("blaze", fire, hp_fraction=0.2) == 1.5
    assert attack_multiplier("blaze", fire, hp_fraction=0.9) == 1.0
    assert attack_multiplier("blaze", _move(), hp_fraction=0.2) == 1.0


def test_guts_needs_a_status_and_a_physical_move():
    assert attack_multiplier("guts", _move(), status="brn") == 1.5
    assert attack_multiplier("guts", _move(), status=None) == 1.0
    assert attack_multiplier("guts", _move(category="Special"), status="brn") == 1.0


def test_solar_power_needs_the_sun():
    special = _move(category="Special")
    assert attack_multiplier("solarpower", special, weather="sunnyday") == 1.5
    assert attack_multiplier("solarpower", special, weather="raindance") == 1.0


# ------------------------------------------------------------- base power


@pytest.mark.parametrize("ability, flag, expected", [
    ("ironfist", "punch", 1.2),
    ("toughclaws", "contact", 1.3),
    ("strongjaw", "bite", 1.5),
    ("megalauncher", "pulse", 1.5),
    ("sharpness", "slicing", 1.5),
])
def test_the_flag_abilities_only_pay_on_their_flag(ability, flag, expected):
    assert base_power_multiplier(ability, _move(flags=[flag]), base_power=80) == expected
    assert base_power_multiplier(ability, _move(flags=["sound"]), base_power=80) == 1.0


def test_technician_only_raises_a_weak_move():
    assert base_power_multiplier("technician", _move(base_power=60), base_power=60) == 1.5
    assert base_power_multiplier("technician", _move(base_power=61), base_power=61) == 1.0


def test_sheer_force_needs_a_rider_to_trade_away():
    from champions_ai.dex import SecondaryEffect
    rider = _move(secondaries=[SecondaryEffect(chance=30, status="brn")])
    assert base_power_multiplier("sheerforce", rider, base_power=80) == 1.3
    assert base_power_multiplier("sheerforce", _move(), base_power=80) == 1.0


def test_reckless_raises_the_moves_that_hurt_their_user():
    assert base_power_multiplier("reckless", _move(recoil=(33, 100)), base_power=80) == 1.2
    assert base_power_multiplier("reckless", _move(), base_power=80) == 1.0


# ------------------------------------------------------------------- STAB


def test_adaptability_makes_stab_worth_two():
    assert stab_multiplier("adaptability", has_stab=True) == 2.0
    assert stab_multiplier(None, has_stab=True) == 1.5
    assert stab_multiplier("adaptability", has_stab=False) == 1.0


def test_an_ate_ability_rewrites_a_normal_move():
    assert rewritten_type("pixilate", _move(move_type="Normal")) == "Fairy"
    assert rewritten_type("pixilate", _move(move_type="Fire")) is None


def test_the_ate_abilities_leave_the_self_typing_moves_alone():
    """Weather Ball and Terrain Pulse decide their own type already, and the
    engine exempts them by name."""
    assert rewritten_type("pixilate", _move("weatherball", move_type="Normal")) is None
    assert rewritten_type("pixilate", _move("terrainpulse", move_type="Normal")) is None


def test_liquid_voice_turns_a_sound_move_to_water():
    assert rewritten_type("liquidvoice", _move(flags=["sound"])) == "Water"
    assert rewritten_type("liquidvoice", _move()) is None


# ---------------------------------------------------------- taking the hit


def test_an_absorbing_ability_makes_the_hit_not_land():
    """Zero is a different statement from "not much", which is why the
    immunities live with the reductions rather than in a separate check."""
    ground = _move(move_type="Ground")
    assert taken_multiplier("levitate", ground, effectiveness=2.0) == 0.0
    assert taken_multiplier("flashfire", _move(move_type="Fire"), effectiveness=1.0) == 0.0
    assert taken_multiplier("levitate", _move(move_type="Water"), effectiveness=1.0) == 1.0


def test_multiscale_only_works_from_full_health():
    assert taken_multiplier("multiscale", _move(), effectiveness=1.0, at_full_hp=True) == 0.5
    assert taken_multiplier("multiscale", _move(), effectiveness=1.0, at_full_hp=False) == 1.0


def test_filter_and_friends_only_blunt_a_super_effective_hit():
    for ability in ("filter", "solidrock", "prismarmor"):
        assert taken_multiplier(ability, _move(), effectiveness=2.0) == 0.75
        assert taken_multiplier(ability, _move(), effectiveness=1.0) == 1.0


def test_fluffy_cuts_both_ways():
    assert taken_multiplier("fluffy", _move(flags=["contact"]), effectiveness=1.0) == 0.5
    assert taken_multiplier("fluffy", _move(move_type="Fire"), effectiveness=1.0) == 2.0


def test_thick_fat_halves_the_two_types_it_names():
    for typing in ("Fire", "Ice"):
        assert taken_multiplier("thickfat", _move(move_type=typing), effectiveness=1.0) == 0.5
    assert taken_multiplier("thickfat", _move(move_type="Water"), effectiveness=1.0) == 1.0


def test_fur_coat_only_thickens_against_physical():
    assert defence_multiplier("furcoat", _move()) == 2.0
    assert defence_multiplier("furcoat", _move(category="Special")) == 1.0
