"""What a held item does to a hit.

Champions carries a restricted item list, so this is a much smaller table than
the full game would need: Choice Band, Choice Specs, Assault Vest, Eviolite and
the Arceus plates are all absent from this dex.

Life Orb is the anchor. It was measured at **1.304** across 144 real hits on
item-holding control teams before it was modelled, and at 0.979 afterwards,
which is the check that this table is read rather than merely present.
"""

import pytest

from champions_ai.dex import BaseStats, MoveInfo, SpeciesInfo
from champions_ai.mechanics.items import (
    attack_multiplier,
    base_power_multiplier,
    damage_multiplier,
    defender_multiplier,
    speed_multiplier,
)


def _move(move_id, move_type="Normal", category="Physical"):
    return MoveInfo(
        move_id=move_id, name=move_id, type=move_type, category=category,
        base_power=80, accuracy=100, priority=0, target="normal",
    )


def _species(name, base_species=None):
    return SpeciesInfo(
        species_id=name.lower(), name=name, types=("Normal",),
        base_stats=BaseStats(hp=100, attack=100, defense=100,
                             special_attack=100, special_defense=100, speed=100),
        base_species=base_species or name,
    )


# ------------------------------------------------------------- base power


def test_a_type_boosting_item_raises_only_its_own_type():
    assert base_power_multiplier("charcoal", _move("ember", "Fire")) == 1.2
    assert base_power_multiplier("charcoal", _move("tackle", "Normal")) == 1.0


@pytest.mark.parametrize(("item", "typing"), [
    ("blackbelt", "Fighting"), ("blackglasses", "Dark"), ("charcoal", "Fire"),
    ("dragonfang", "Dragon"), ("fairyfeather", "Fairy"), ("hardstone", "Rock"),
    ("magnet", "Electric"), ("metalcoat", "Steel"), ("miracleseed", "Grass"),
    ("mysticwater", "Water"), ("nevermeltice", "Ice"), ("poisonbarb", "Poison"),
    ("sharpbeak", "Flying"), ("silkscarf", "Normal"), ("silverpowder", "Bug"),
    ("softsand", "Ground"), ("spelltag", "Ghost"), ("twistedspoon", "Psychic"),
])
def test_every_type_has_its_item(item, typing):
    """One per type, extracted from the engine rather than typed from memory."""
    assert base_power_multiplier(item, _move("x", typing)) == 1.2


def test_muscle_band_and_wise_glasses_split_by_category():
    assert base_power_multiplier("muscleband", _move("x", category="Physical")) == 1.1
    assert base_power_multiplier("muscleband", _move("x", category="Special")) == 1.0
    assert base_power_multiplier("wiseglasses", _move("x", category="Special")) == 1.1
    assert base_power_multiplier("wiseglasses", _move("x", category="Physical")) == 1.0


def test_no_item_changes_nothing():
    assert base_power_multiplier(None, _move("tackle")) == 1.0
    assert base_power_multiplier("leftovers", _move("tackle")) == 1.0


# --------------------------------------------------------- the attacking stat


def test_light_ball_only_works_for_the_species_named():
    assert attack_multiplier("lightball", _species("Pikachu")) == 2.0
    assert attack_multiplier("lightball", _species("Raichu")) == 1.0
    assert attack_multiplier("lightball", None) == 1.0


def test_light_ball_reaches_a_cosmetic_forme():
    """`itemUser` names the base species, and Pikachu has a great many formes."""
    assert attack_multiplier("lightball", _species("Pikachu-Hoenn", "Pikachu")) == 2.0


# ------------------------------------------------------------ final damage


def test_life_orb_is_the_engines_one_point_three():
    """`chainModify([5324, 4096])`, and measured at 1.304 over 144 real hits."""
    assert damage_multiplier("lifeorb", effectiveness=1.0) == 1.3
    assert damage_multiplier("lifeorb", effectiveness=0.5) == 1.3


def test_expert_belt_only_pays_on_a_super_effective_hit():
    assert damage_multiplier("expertbelt", effectiveness=2.0) == 1.2
    assert damage_multiplier("expertbelt", effectiveness=1.0) == 1.0
    assert damage_multiplier("expertbelt", effectiveness=0.5) == 1.0


# ------------------------------------------------------- the defender's item


def test_a_resist_berry_halves_a_super_effective_hit_of_its_type():
    fire = _move("flamethrower", "Fire", "Special")
    assert defender_multiplier("occaberry", fire, effectiveness=2.0) == 0.5
    assert defender_multiplier("occaberry", fire, effectiveness=1.0) == 1.0


def test_a_resist_berry_ignores_a_move_of_another_type():
    water = _move("surf", "Water", "Special")
    assert defender_multiplier("occaberry", water, effectiveness=2.0) == 1.0


def test_chilan_berry_halves_any_normal_move():
    """The exception: nothing is weak to Normal, so requiring super-effective
    would make it do nothing at all."""
    normal = _move("bodyslam", "Normal")
    assert defender_multiplier("chilanberry", normal, effectiveness=1.0) == 0.5
    assert defender_multiplier("chilanberry", _move("surf", "Water"), effectiveness=1.0) == 1.0


# -------------------------------------------------------------------- speed


def test_choice_scarf_and_iron_ball():
    assert speed_multiplier("choicescarf") == 1.5
    assert speed_multiplier("ironball") == 0.5
    assert speed_multiplier("lifeorb") == 1.0
    assert speed_multiplier(None) == 1.0
