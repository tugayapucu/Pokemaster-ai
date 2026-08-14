"""Parsing Showdown's export format -- what players actually paste."""

import pytest

from champions_ai.data import parse_pokemon_set, parse_showdown_team

BASIC = """
Charizard @ Charizardite Y
Ability: Blaze
Level: 50
EVs: 32 SpA / 32 Spe
Timid Nature
- Heat Wave
- Solar Beam
- Protect
- Flamethrower
""".strip()


def test_reads_the_fields_the_domain_models():
    mon = parse_pokemon_set(BASIC)
    assert mon.species == "Charizard"
    assert mon.item == "Charizardite Y"
    assert mon.ability == "Blaze"
    assert mon.level == 50
    assert mon.nature == "Timid"
    assert mon.moves == ("Heat Wave", "Solar Beam", "Protect", "Flamethrower")


def test_ev_line_carries_champions_stat_points():
    """Champions' Stat Points occupy the EV line of the export format (ADR 0002)."""
    stats = parse_pokemon_set(BASIC).stats
    assert stats.special_attack == 32
    assert stats.speed == 32
    assert stats.total == 64


def test_all_six_stat_abbreviations_map_correctly():
    text = "X\nAbility: A\nEVs: 1 HP / 2 Atk / 3 Def / 4 SpA / 5 SpD / 6 Spe\n- Tackle"
    stats = parse_pokemon_set(text).stats
    assert (stats.hp, stats.attack, stats.defense) == (1, 2, 3)
    assert (stats.special_attack, stats.special_defense, stats.speed) == (4, 5, 6)


def test_item_is_optional():
    mon = parse_pokemon_set("Garchomp\nAbility: Rough Skin\n- Earthquake")
    assert mon.item is None
    assert mon.species == "Garchomp"


def test_nickname_is_separated_from_species():
    mon = parse_pokemon_set("Chomper (Garchomp) @ Life Orb\nAbility: Rough Skin\n- Earthquake")
    assert mon.species == "Garchomp"
    assert mon.nickname == "Chomper"
    assert mon.item == "Life Orb"


def test_gender_marker_is_not_mistaken_for_a_nickname():
    mon = parse_pokemon_set("Incineroar (M) @ Sitrus Berry\nAbility: Intimidate\n- Fake Out")
    assert mon.species == "Incineroar"
    assert mon.nickname is None


def test_tera_type_is_read():
    mon = parse_pokemon_set("X\nAbility: A\nTera Type: Steel\n- Tackle")
    assert mon.tera_type == "Steel"


def test_unknown_lines_are_ignored_rather_than_rejected():
    """A team pasted from elsewhere should not fail to load over a line we don't use."""
    mon = parse_pokemon_set(
        "X @ Leftovers\nAbility: A\nShiny: Yes\nHappiness: 160\n"
        "IVs: 0 Atk\nEVs: 4 HP\n- Tackle"
    )
    assert mon.species == "X"
    assert mon.stats.hp == 4


def test_level_defaults_when_absent():
    assert parse_pokemon_set("X\nAbility: A\n- Tackle").level == 50
    assert parse_pokemon_set("X\nAbility: A\nLevel: 100\n- Tackle").level == 100


def test_parses_a_whole_team_split_on_blank_lines():
    text = BASIC + "\n\n" + "Garchomp @ Life Orb\nAbility: Rough Skin\n- Earthquake"
    team = parse_showdown_team(text)
    assert len(team) == 2
    assert [mon.species for mon in team.pokemon] == ["Charizard", "Garchomp"]


def test_tolerates_extra_blank_lines_between_sets():
    text = BASIC + "\n\n\n\n" + "Garchomp\nAbility: Rough Skin\n- Earthquake"
    assert len(parse_showdown_team(text)) == 2


def test_empty_text_is_an_error():
    with pytest.raises(ValueError):
        parse_showdown_team("   \n\n  ")
