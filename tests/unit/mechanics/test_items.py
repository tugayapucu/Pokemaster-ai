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
    is_removable,
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


# --------------------------------------------------- whether it can be taken


def _item(item_id, *, mega_stone=None):
    from champions_ai.dex import ItemInfo
    return ItemInfo(item_id=item_id, name=item_id, mega_stone=mega_stone)


def test_an_ordinary_item_can_be_taken():
    assert is_removable(_item("lifeorb"), _species("Garchomp"))


def test_nothing_held_is_not_removable():
    assert not is_removable(None, _species("Garchomp"))


def test_a_mega_stone_cannot_be_taken_off_the_species_it_evolves():
    """Seventy-five items in this dex refuse to be removed and every one is a
    Mega Stone. Champions teams are full of them, so pricing Knock Off on
    "holds anything" was wrong far more often than it was right."""
    stone = _item("alakazite", mega_stone="Alakazam")
    assert not is_removable(stone, _species("Alakazam"))


def test_a_mega_stone_can_be_taken_off_anyone_else():
    """The engine checks the stone against *this* holder, not in general."""
    stone = _item("alakazite", mega_stone="Alakazam")
    assert is_removable(stone, _species("Garchomp"))


def test_a_mega_stone_is_matched_against_the_base_species():
    """`megaStone` is keyed by base species, and the engine compares against
    `source.baseSpecies.baseSpecies` -- so a forme still cannot drop it."""
    stone = _item("charizarditey", mega_stone="Charizard")
    assert not is_removable(stone, _species("Charizard-Mega-Y", "Charizard"))


def test_an_unknown_holder_is_assumed_to_be_the_stones_owner():
    """The cautious guess: a stone is overwhelmingly on the Pokemon it
    belongs to, so assume no boost rather than an imaginary one."""
    assert not is_removable(_item("alakazite", mega_stone="Alakazam"), None)
    assert is_removable(_item("lifeorb"), None), "an ordinary item still comes off"


def test_sticky_hold_refuses_to_give_anything_up():
    assert not is_removable(_item("lifeorb"), _species("Hydrapple"), "stickyhold")
    assert is_removable(_item("lifeorb"), _species("Hydrapple"), "regenerator")
