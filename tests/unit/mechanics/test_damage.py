"""Damage estimation.

The headline case is validated against the live engine: Charizard's
Flamethrower into Garchomp was predicted at 39-46 and observed at exactly
39-46 across 38 non-critical hits, boundaries included.
"""

import pytest

from champions_ai.dex import BaseStats, Dex, MoveInfo, SpeciesInfo, TypeChart
from champions_ai.mechanics import estimate_damage, is_spread_move

CHARIZARD = SpeciesInfo(
    species_id="charizard",
    name="Charizard",
    types=("Fire", "Flying"),
    base_stats=BaseStats(
        hp=78, attack=84, defense=78, special_attack=109, special_defense=85, speed=100
    ),
)
GARCHOMP = SpeciesInfo(
    species_id="garchomp",
    name="Garchomp",
    types=("Dragon", "Ground"),
    base_stats=BaseStats(
        hp=108, attack=130, defense=95, special_attack=80, special_defense=85, speed=102
    ),
)

FLAMETHROWER = MoveInfo(
    move_id="flamethrower", name="Flamethrower", type="Fire", category="Special",
    base_power=90, accuracy=100, priority=0, target="normal",
)
EARTHQUAKE = MoveInfo(
    move_id="earthquake", name="Earthquake", type="Ground", category="Physical",
    base_power=100, accuracy=100, priority=0, target="allAdjacent",
)
PROTECT = MoveInfo(
    move_id="protect", name="Protect", type="Normal", category="Status",
    base_power=0, accuracy=None, priority=4, target="self",
)
THUNDERBOLT = MoveInfo(
    move_id="thunderbolt", name="Thunderbolt", type="Electric", category="Special",
    base_power=90, accuracy=100, priority=0, target="normal",
)

CHART = {
    "Fire": {"Dragon": 0.5, "Ground": 1.0, "Fire": 0.5, "Flying": 1.0, "Electric": 1.0},
    "Ground": {"Dragon": 1.0, "Ground": 1.0, "Fire": 2.0, "Flying": 0.0, "Electric": 2.0},
    "Normal": {"Dragon": 1.0, "Ground": 1.0, "Fire": 1.0, "Flying": 1.0, "Electric": 1.0},
    "Electric": {"Dragon": 0.5, "Ground": 0.0, "Fire": 1.0, "Flying": 2.0, "Electric": 0.5},
}


@pytest.fixture
def dex() -> Dex:
    return Dex(
        species={"charizard": CHARIZARD, "garchomp": GARCHOMP},
        moves={m.move_id: m for m in (FLAMETHROWER, EARTHQUAKE, PROTECT, THUNDERBOLT)},
        types=("Fire", "Ground", "Normal", "Electric", "Dragon", "Flying"),
        type_chart=TypeChart(multipliers=CHART),
    )


def _flamethrower_into_garchomp(dex: Dex, **overrides):
    defaults = dict(
        attacker=CHARIZARD, attack_stat=161,
        defender=GARCHOMP, defense_stat=105, defender_hp=183,
    )
    return estimate_damage(dex, FLAMETHROWER, **{**defaults, **overrides})


def test_matches_the_engines_observed_range(dex):
    """Validated live: 38 non-crit hits landed in exactly 39-46."""
    estimate = _flamethrower_into_garchomp(dex)
    assert (estimate.minimum, estimate.maximum) == (39, 46)


def test_reports_the_resisted_multiplier(dex):
    assert _flamethrower_into_garchomp(dex).effectiveness == 0.5


def test_status_moves_do_no_damage(dex):
    estimate = estimate_damage(
        dex, PROTECT, attacker=CHARIZARD, attack_stat=161,
        defender=GARCHOMP, defense_stat=105, defender_hp=183,
    )
    assert estimate.maximum == 0
    assert not estimate.possible_ko


def test_immunity_yields_no_damage(dex):
    """Electric cannot touch a Ground type, however strong the attacker."""
    estimate = estimate_damage(
        dex, THUNDERBOLT, attacker=CHARIZARD, attack_stat=999,
        defender=GARCHOMP, defense_stat=1, defender_hp=183,
    )
    assert estimate.is_immune
    assert estimate.maximum == 0


def test_stab_increases_damage(dex):
    """Charizard is Fire, so Flamethrower gets STAB; a non-Fire attacker does not."""
    with_stab = _flamethrower_into_garchomp(dex).maximum
    without_stab = estimate_damage(
        dex, FLAMETHROWER, attacker=GARCHOMP, attack_stat=161,
        defender=GARCHOMP, defense_stat=105, defender_hp=183,
    ).maximum
    assert with_stab > without_stab


def test_spread_moves_are_reduced_in_doubles(dex):
    """A spread move hits each target for 75% in doubles, full power in singles.

    Garchomp rather than Charizard as the target: Charizard is Flying, so
    Earthquake does not touch it at all.
    """
    assert is_spread_move(EARTHQUAKE)
    doubles = estimate_damage(
        dex, EARTHQUAKE, attacker=GARCHOMP, attack_stat=182,
        defender=GARCHOMP, defense_stat=115, defender_hp=183, doubles=True,
    ).maximum
    singles = estimate_damage(
        dex, EARTHQUAKE, attacker=GARCHOMP, attack_stat=182,
        defender=GARCHOMP, defense_stat=115, defender_hp=183, doubles=False,
    ).maximum
    assert doubles < singles
    assert doubles == pytest.approx(singles * 0.75, abs=1)


def test_a_flying_type_is_untouched_by_earthquake(dex):
    """The immunity that made the first version of the test above wrong."""
    estimate = estimate_damage(
        dex, EARTHQUAKE, attacker=GARCHOMP, attack_stat=182,
        defender=CHARIZARD, defense_stat=98, defender_hp=153,
    )
    assert estimate.is_immune
    assert estimate.maximum == 0


def test_single_target_moves_are_not_reduced(dex):
    assert not is_spread_move(FLAMETHROWER)


def test_burn_halves_physical_damage_only(dex):
    burned_physical = estimate_damage(
        dex, EARTHQUAKE, attacker=GARCHOMP, attack_stat=182,
        defender=GARCHOMP, defense_stat=115, defender_hp=183, attacker_burned=True,
    ).maximum
    healthy_physical = estimate_damage(
        dex, EARTHQUAKE, attacker=GARCHOMP, attack_stat=182,
        defender=GARCHOMP, defense_stat=115, defender_hp=183,
    ).maximum
    assert burned_physical < healthy_physical

    burned_special = _flamethrower_into_garchomp(dex, attacker_burned=True).maximum
    assert burned_special == _flamethrower_into_garchomp(dex).maximum


def test_guaranteed_ko_needs_even_the_worst_roll(dex):
    """A move that only KOs on a high roll is a gamble, not a plan."""
    barely = _flamethrower_into_garchomp(dex, defender_hp=45)
    assert barely.possible_ko
    assert not barely.guaranteed_ko

    certain = _flamethrower_into_garchomp(dex, defender_hp=39)
    assert certain.guaranteed_ko
    assert certain.possible_ko


def test_average_fraction_is_capped_at_the_targets_remaining_hp(dex):
    assert _flamethrower_into_garchomp(dex, defender_hp=5).average_fraction == 1.0


def test_fraction_of_a_full_health_target_is_modest(dex):
    fraction = _flamethrower_into_garchomp(dex).average_fraction
    assert 0.2 < fraction < 0.3


def test_a_fainted_target_yields_no_fraction(dex):
    assert _flamethrower_into_garchomp(dex, defender_hp=0).average_fraction == 0.0
