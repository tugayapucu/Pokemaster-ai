"""Terrain only reaches what is standing on it.

`is_grounded` was written, exported, and called by nothing — the same shape as
most of the bugs in this project. Five rules were applying terrain bonuses to
Flying types and Levitate users that the engine exempts.

One asymmetry is worth stating loudly, because getting it backwards would be
invisible in ordinary play and wrong exactly where it matters: **Rising Voltage
reads the target's footing**, every other rule here reads the attacker's.

    risingvoltage    if (isTerrain('electricterrain') && target.isGrounded())
    terrainpulse     onModifyType(move, pokemon) { if (!pokemon.isGrounded()) return; }
    expandingforce   if (isTerrain('psychicterrain') && source.isGrounded())
    mistyexplosion   if (isTerrain('mistyterrain') && source.isGrounded())
    electricterrain  if (move.type === 'Electric' && attacker.isGrounded())
"""

from champions_ai.dex import MoveInfo
from champions_ai.mechanics.base_power import conditional_multiplier, dynamic_base_power
from champions_ai.mechanics.move_type import effective_type


def _move(move_id, **kwargs):
    fields = dict(
        move_id=move_id, name=move_id.title(), type="Normal",
        category="Special", base_power=80, accuracy=100, priority=0,
        target="normal",
    )
    fields.update(kwargs)
    return MoveInfo(**fields)


THUNDERBOLT = _move("thunderbolt", type="Electric", base_power=90)
EXPANDING_FORCE = _move("expandingforce", type="Psychic", base_power=80)
MISTY_EXPLOSION = _move("mistyexplosion", type="Fairy", base_power=100)
RISING_VOLTAGE = _move("risingvoltage", type="Electric", base_power=70)
TERRAIN_PULSE = _move("terrainpulse", base_power=50, modifies_type=True)


# --- the attacker's footing ----------------------------------------------


def test_electric_terrain_only_boosts_a_grounded_attacker():
    grounded = conditional_multiplier(
        THUNDERBOLT, terrain="electricterrain", attacker_grounded=True
    )
    flying = conditional_multiplier(
        THUNDERBOLT, terrain="electricterrain", attacker_grounded=False
    )
    assert grounded > flying
    assert flying == 1.0


def test_expanding_force_only_grows_for_a_grounded_user():
    grounded = conditional_multiplier(
        EXPANDING_FORCE, terrain="psychicterrain", attacker_grounded=True
    )
    flying = conditional_multiplier(
        EXPANDING_FORCE, terrain="psychicterrain", attacker_grounded=False
    )
    assert grounded > flying == 1.0


def test_misty_explosion_only_grows_for_a_grounded_user():
    grounded = conditional_multiplier(
        MISTY_EXPLOSION, terrain="mistyterrain", attacker_grounded=True
    )
    flying = conditional_multiplier(
        MISTY_EXPLOSION, terrain="mistyterrain", attacker_grounded=False
    )
    assert grounded > flying == 1.0


def test_terrain_pulse_keeps_its_type_when_the_user_is_airborne():
    grounded = effective_type(
        TERRAIN_PULSE, terrain="electricterrain", attacker_grounded=True
    )
    flying = effective_type(
        TERRAIN_PULSE, terrain="electricterrain", attacker_grounded=False
    )
    assert grounded == "Electric"
    assert flying == "Normal"


# --- the one that reads the other side -----------------------------------


def test_rising_voltage_follows_the_targets_footing_not_the_users():
    """The asymmetry. A Levitating attacker still doubles it; a Flying target
    still escapes it."""
    def power(attacker_grounded, defender_grounded):
        return dynamic_base_power(
            RISING_VOLTAGE,
            terrain="electricterrain",
            attacker_grounded=attacker_grounded,
            defender_grounded=defender_grounded,
        )

    # Two independent engine hooks stack here, which is what makes this a
    # good test of the asymmetry: the *doubling* follows the target's footing
    # (`basePowerCallback`), the *1.3 type bonus* follows the attacker's
    # (Electric Terrain's `onBasePower`). Rising Voltage is Electric, so a
    # grounded attacker collects both.
    assert power(True, True) == 182       # 70 x2 (target) x1.3 (attacker)
    assert power(False, True) == 140      # x2 only: attacker is airborne
    assert power(True, False) == 91       # x1.3 only: target is airborne
    assert power(False, False) == 70      # neither


def test_rising_voltage_is_ordinary_off_electric_terrain():
    assert dynamic_base_power(RISING_VOLTAGE, terrain=None) == 70


# --- the default stays kind ----------------------------------------------


def test_a_caller_that_does_not_know_gets_the_common_case():
    """Both flags default to True. Most Pokemon are on the ground, so a caller
    without footing information should keep the bonus rather than silently
    lose it for everyone."""
    assert conditional_multiplier(THUNDERBOLT, terrain="electricterrain") > 1.0
    assert effective_type(TERRAIN_PULSE, terrain="electricterrain") == "Electric"
