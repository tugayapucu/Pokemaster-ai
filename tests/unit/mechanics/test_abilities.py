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
    extra_hit_multiplier,
    linked_hits,
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


# --- Parental Bond -------------------------------------------------------


def _bond_move(move_id="crunch", **kwargs):
    fields = dict(
        move_id=move_id, name=move_id.title(), type="Dark", category="Physical",
        base_power=80, accuracy=100, priority=0, target="normal",
    )
    fields.update(kwargs)
    return MoveInfo(**fields)


def test_parental_bond_adds_a_quarter_not_a_half():
    """The engine scales the *second* hit, and in this generation by 0.25:

        const bondModifier = this.battle.gen > 6 ? 0.25 : 0.5;

    so the pair comes to 1.25x, not the 1.5x the older games gave. Measured at
    1.200 across 92 hits before being written down.
    """
    assert extra_hit_multiplier(
        "parentalbond", _bond_move(), is_spread=False
    ) == 1.25


def test_parental_bond_leaves_status_moves_alone():
    assert extra_hit_multiplier(
        "parentalbond", _bond_move(category="Status", base_power=0, accuracy=None),
        is_spread=False,
    ) == 1.0


def test_parental_bond_does_not_stack_with_a_multi_hit_move():
    assert extra_hit_multiplier(
        "parentalbond", _bond_move(multihit=[2, 5]), is_spread=False
    ) == 1.0


def test_parental_bond_does_not_apply_to_a_spread_move():
    """`move.spreadHit` in the engine's `onPrepareHit`."""
    assert extra_hit_multiplier(
        "parentalbond", _bond_move(target="allAdjacentFoes"), is_spread=True
    ) == 1.0


def test_parental_bond_respects_the_engines_flags():
    for flag in ("noparentalbond", "charge", "futuremove"):
        assert extra_hit_multiplier(
            "parentalbond", _bond_move(flags=frozenset({flag})), is_spread=False
        ) == 1.0


def test_anything_else_gets_one_hit():
    assert extra_hit_multiplier("hugepower", _bond_move(), is_spread=False) == 1.0
    assert extra_hit_multiplier(None, _bond_move(), is_spread=False) == 1.0


# --- Skill Link ----------------------------------------------------------


def test_skill_link_forces_the_maximum_hit_count():
    """"2-5, averaging 3.167" becomes a flat 5 -- a 1.58x multiplier on those
    moves, and it also deletes the hit-count uncertainty that dominates our
    predicted range for them."""
    bullet_seed = _bond_move(
        "bulletseed", type="Grass", base_power=25, multihit=(2, 5)
    )
    assert linked_hits("skilllink", bullet_seed) == 5


def test_skill_link_leaves_a_fixed_multi_hit_move_alone():
    """Double Kick already always hits twice; there is no roll to remove."""
    double_kick = _bond_move("doublekick", base_power=30, multihit=2)
    assert linked_hits("skilllink", double_kick) is None


def test_skill_link_does_nothing_to_a_single_hit_move():
    assert linked_hits("skilllink", _bond_move()) is None


def test_without_skill_link_the_count_still_rolls():
    bullet_seed = _bond_move(
        "bulletseed", type="Grass", base_power=25, multihit=(2, 5)
    )
    assert linked_hits("technician", bullet_seed) is None
    assert linked_hits(None, bullet_seed) is None


def test_fire_mane_is_not_a_pinch_ability():
    """It was filed with Blaze on the strength of the name. The engine has no
    HP condition -- `if (move.type === 'Fire') return this.chainModify(1.5)` --
    so it is x1.5 always, on both attacking stats.

    Caught by Pyroar-Mega reading 65.2% accuracy against a *perfect* median of
    1.003: the signature of an effect that is conditional in the model and
    unconditional in the game.
    """
    ember = _bond_move("ember", type="Fire", category="Special", base_power=40)
    assert attack_multiplier("firemane", ember, hp_fraction=1.0) == 1.5
    assert attack_multiplier("firemane", ember, hp_fraction=0.2) == 1.5


def test_fire_mane_still_only_helps_fire_moves():
    assert attack_multiplier("firemane", _bond_move(), hp_fraction=1.0) == 1.0


def test_blaze_really_is_a_pinch_ability():
    """The contrast that makes the Fire Mane fix meaningful."""
    ember = _bond_move("ember", type="Fire", category="Special", base_power=40)
    assert attack_multiplier("blaze", ember, hp_fraction=1.0) == 1.0
    assert attack_multiplier("blaze", ember, hp_fraction=0.2) == 1.5


def test_skill_link_narrows_the_predicted_range_not_just_its_centre():
    """The point of a certainty is that it removes uncertainty.

    The first version of this set the expected hit count and left `hit_range`
    alone, so a Pokemon that always lands five hits still carried a
    two-to-five prediction -- wide enough to be nearly unfalsifiable. The
    commit message claimed the range was narrowed; the code had not done it.
    """
    from champions_ai.dex import BaseStats, Dex, SpeciesInfo, TypeChart
    from champions_ai.mechanics.damage import estimate_damage

    bullet_seed = MoveInfo(
        move_id="bulletseed", name="Bullet Seed", type="Grass",
        category="Physical", base_power=25, accuracy=100, priority=0,
        target="normal", multihit=(2, 5),
    )
    types = ("Grass", "Normal")
    species = SpeciesInfo(
        species_id="breloom", name="Breloom", types=("Grass",),
        base_stats=BaseStats(hp=60, attack=130, defense=80,
                             special_attack=60, special_defense=60, speed=70),
    )
    dex = Dex(
        species={species.species_id: species},
        moves={bullet_seed.move_id: bullet_seed},
        types=types,
        type_chart=TypeChart(multipliers={a: dict.fromkeys(types, 1.0) for a in types}),
    )

    def estimate(ability):
        return estimate_damage(
            dex, bullet_seed, attacker=species, attack_stat=150,
            defender=species, defense_stat=100, defender_hp=400,
            doubles=False, attacker_ability=ability,
        )

    linked = estimate("skilllink")
    rolled = estimate(None)
    assert linked.maximum - linked.minimum < rolled.maximum - rolled.minimum
    # ...and it sits at the top, because five hits is the most it could roll.
    assert linked.maximum == rolled.maximum
    assert linked.minimum > rolled.minimum
