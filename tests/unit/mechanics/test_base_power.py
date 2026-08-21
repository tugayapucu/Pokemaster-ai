"""Base power for moves the engine computes at run time.

Eleven moves in the Champions dex carry a zero static base power because the
engine works it out per hit. `is_damaging` was `base_power > 0`, so all eleven
were classed as *status moves* and scored at a flat support value -- Low Kick
and Grass Knot among them.

Every formula is transcribed from `basePowerCallback` in the engine's moves.ts.
The thresholds are in kilograms while the engine works in hectograms, so the
factor of ten is the easiest thing here to get wrong and the tests pin it.
"""

import pytest

from champions_ai.dex import BaseStats, MoveInfo, SpeciesInfo
from champions_ai.mechanics import dynamic_base_power
from champions_ai.mechanics.base_power import UNMODELLED_DEFAULT


def _move(move_id, base_power=0, category="Physical"):
    return MoveInfo(
        move_id=move_id, name=move_id, type="Normal", category=category,
        base_power=base_power, accuracy=100, priority=0, target="normal",
        dynamic_power=base_power == 0,
    )


def _species(name, weight):
    return SpeciesInfo(
        species_id=name.lower(), name=name, types=("Normal",),
        base_stats=BaseStats(hp=100, attack=100, defense=100,
                             special_attack=100, special_defense=100, speed=100),
        weight_kg=weight,
    )


HEAVY = _species("Heavy", 460.0)     # Snorlax-like
MEDIUM = _species("Medium", 48.0)    # Alakazam-like
FEATHER = _species("Feather", 4.0)


def test_a_normal_move_keeps_its_static_power():
    """Safe to call for every move, not only the special ones."""
    assert dynamic_base_power(_move("tackle", base_power=40)) == 40


@pytest.mark.parametrize(
    ("weight", "expected"),
    [(460.0, 120), (150.0, 100), (60.0, 80), (30.0, 60), (12.0, 40), (4.0, 20)],
)
def test_low_kick_scales_with_the_targets_weight_in_kilograms(weight, expected):
    """The engine's thresholds are hectograms; ours are kilograms. Getting that
    factor of ten wrong would misprice every weight move by two brackets."""
    assert dynamic_base_power(_move("lowkick"), defender=_species("X", weight)) == expected


def test_grass_knot_uses_the_same_brackets_as_low_kick():
    assert dynamic_base_power(_move("grassknot"), defender=HEAVY) == dynamic_base_power(
        _move("lowkick"), defender=HEAVY
    )


@pytest.mark.parametrize(
    ("attacker_weight", "expected"),
    [(250.0, 120), (200.0, 100), (150.0, 80), (100.0, 60), (60.0, 40)],
)
def test_heavy_slam_scales_with_the_weight_ratio(attacker_weight, expected):
    power = dynamic_base_power(
        _move("heavyslam"), attacker=_species("A", attacker_weight), defender=MEDIUM
    )
    assert power == expected


@pytest.mark.parametrize(
    ("hp_fraction", "expected"),
    [(0.01, 200), (0.08, 150), (0.15, 100), (0.3, 80), (0.6, 40), (1.0, 20)],
)
def test_flail_hits_hardest_at_low_health(hp_fraction, expected):
    assert dynamic_base_power(_move("flail"), attacker_hp_fraction=hp_fraction) == expected


def test_reversal_reads_the_same_way_as_flail():
    assert dynamic_base_power(_move("reversal"), attacker_hp_fraction=0.05) == 150


def test_gyro_ball_rewards_being_slower():
    slow = dynamic_base_power(_move("gyroball"), attacker_speed=50, defender_speed=200)
    fast = dynamic_base_power(_move("gyroball"), attacker_speed=200, defender_speed=50)
    assert slow > fast


def test_gyro_ball_is_capped():
    assert dynamic_base_power(_move("gyroball"), attacker_speed=1, defender_speed=500) == 150


def test_electro_ball_rewards_being_faster():
    fast = dynamic_base_power(_move("electroball"), attacker_speed=400, defender_speed=50)
    slow = dynamic_base_power(_move("electroball"), attacker_speed=50, defender_speed=400)
    assert fast == 150
    assert slow == 40


def test_a_move_we_cannot_compute_falls_back_rather_than_reading_as_zero():
    """Beat Up and Spit Up depend on state we do not track. A middling value
    keeps them scored as the attacks they are, which is the whole point."""
    assert dynamic_base_power(_move("beatup")) == UNMODELLED_DEFAULT
    assert dynamic_base_power(_move("spitup")) == UNMODELLED_DEFAULT


def test_missing_context_never_produces_zero_power():
    """Zero would put the move back to being treated as a status move."""
    for move_id in ("lowkick", "heavyslam", "gyroball", "electroball"):
        assert dynamic_base_power(_move(move_id)) > 0


def test_a_dynamic_move_counts_as_damaging():
    assert _move("lowkick").is_damaging
    assert not _move("protect", category="Status").is_damaging
