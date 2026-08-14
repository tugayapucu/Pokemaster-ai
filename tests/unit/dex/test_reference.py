"""Reference data types, tested against a hand-built dex (no Node needed)."""

import pytest

from champions_ai.dex import Dex, MoveInfo, SpeciesInfo, TypeChart, to_id

PAYLOAD = {
    "species": {
        "charizard": {
            "name": "Charizard",
            "types": ["Fire", "Flying"],
            "baseStats": {"hp": 78, "atk": 84, "def": 78, "spa": 109, "spd": 85, "spe": 100},
            "abilities": ["Blaze", "Solar Power"],
            "weightkg": 90.5,
            "baseSpecies": "Charizard",
        },
        "garchomp": {
            "name": "Garchomp",
            "types": ["Dragon", "Ground"],
            "baseStats": {"hp": 108, "atk": 130, "def": 95, "spa": 80, "spd": 85, "spe": 102},
            "abilities": ["Rough Skin"],
            "weightkg": 95.0,
            "baseSpecies": "Garchomp",
        },
    },
    "moves": {
        "heatwave": {
            "name": "Heat Wave",
            "type": "Fire",
            "category": "Special",
            "basePower": 95,
            "accuracy": 90,
            "priority": 0,
            "target": "allAdjacentFoes",
            "flags": ["protect", "wind"],
        },
        "protect": {
            "name": "Protect",
            "type": "Normal",
            "category": "Status",
            "basePower": 0,
            "accuracy": None,
            "priority": 4,
            "target": "self",
            "flags": [],
        },
        "swift": {
            "name": "Swift",
            "type": "Normal",
            "category": "Special",
            "basePower": 60,
            "accuracy": None,
            "priority": 0,
            "target": "allAdjacentFoes",
            "flags": [],
        },
    },
    "types": ["Fire", "Flying", "Water", "Rock", "Dragon", "Ground", "Normal", "Electric"],
    "chart": {
        "Fire": {"Fire": 0.5, "Flying": 1, "Water": 0.5, "Rock": 0.5, "Dragon": 0.5,
                 "Ground": 1, "Normal": 1, "Electric": 1},
        "Water": {"Fire": 2, "Flying": 1, "Water": 0.5, "Rock": 2, "Dragon": 0.5,
                  "Ground": 2, "Normal": 1, "Electric": 1},
        "Rock": {"Fire": 2, "Flying": 2, "Water": 1, "Rock": 1, "Dragon": 1,
                 "Ground": 0.5, "Normal": 1, "Electric": 1},
        "Electric": {"Fire": 1, "Flying": 2, "Water": 2, "Rock": 1, "Dragon": 0.5,
                     "Ground": 0, "Normal": 1, "Electric": 0.5},
        "Flying": {"Fire": 1, "Flying": 1, "Water": 1, "Rock": 0.5, "Dragon": 1,
                   "Ground": 1, "Normal": 1, "Electric": 0.5},
        "Dragon": {"Fire": 1, "Flying": 1, "Water": 1, "Rock": 1, "Dragon": 2,
                   "Ground": 1, "Normal": 1, "Electric": 1},
        "Ground": {"Fire": 2, "Flying": 0, "Water": 1, "Rock": 2, "Dragon": 1,
                   "Ground": 1, "Normal": 1, "Electric": 2},
        "Normal": {"Fire": 1, "Flying": 1, "Water": 1, "Rock": 0.5, "Dragon": 1,
                   "Ground": 1, "Normal": 1, "Electric": 1},
    },
}


@pytest.fixture
def dex() -> Dex:
    return Dex.from_payload(PAYLOAD)


def test_to_id_matches_showdown_normalisation():
    assert to_id("Heat Wave") == "heatwave"
    assert to_id("King's Rock") == "kingsrock"
    assert to_id("Porygon-Z") == "porygonz"


def test_species_carry_types_and_base_stats(dex):
    charizard = dex.get_species("Charizard")
    assert charizard.types == ("Fire", "Flying")
    assert charizard.base_stats.special_attack == 109
    assert charizard.base_stats.speed == 100


def test_lookup_accepts_display_names_and_ids(dex):
    assert dex.get_species("Charizard") is dex.get_species("charizard")
    assert dex.get_move("Heat Wave") is dex.get_move("heatwave")


def test_missing_entries_raise_rather_than_defaulting(dex):
    """A silent default would flatten every calculation involving it."""
    with pytest.raises(KeyError):
        dex.get_species("Mewtwo")
    with pytest.raises(KeyError):
        dex.get_move("Hyper Beam")


def test_move_fields(dex):
    heat_wave = dex.get_move("Heat Wave")
    assert heat_wave.type == "Fire"
    assert heat_wave.category == "Special"
    assert heat_wave.base_power == 95
    assert heat_wave.accuracy == 90
    assert heat_wave.is_damaging


def test_status_moves_are_not_damaging(dex):
    assert not dex.get_move("Protect").is_damaging


def test_never_missing_is_distinct_from_perfectly_accurate(dex):
    """Swift cannot be made to miss; a 100%-accurate move can."""
    swift = dex.get_move("Swift")
    assert swift.always_hits
    assert swift.hit_chance == 1.0
    assert dex.get_move("Heat Wave").hit_chance == 0.9
    assert not dex.get_move("Heat Wave").always_hits


def test_effectiveness_multiplies_across_dual_types(dex):
    """Rock hits Fire and Flying for 2x each -- the classic 4x on Charizard."""
    chart = dex.type_chart
    assert chart.effectiveness("Rock", ("Fire", "Flying")) == 4.0


def test_immunity_beats_a_weakness(dex):
    """Electric is 2x on Flying but 0x on Ground; a Ground/Flying is immune."""
    assert dex.type_chart.effectiveness("Electric", ("Ground", "Flying")) == 0.0


def test_resistances_stack(dex):
    assert dex.type_chart.effectiveness("Fire", ("Fire", "Dragon")) == 0.25


def test_neutral_is_one(dex):
    assert dex.type_chart.effectiveness("Normal", ("Dragon",)) == 1.0


def test_effectiveness_helper_uses_the_defenders_typing(dex):
    rock_slide = MoveInfo(
        move_id="rockslide", name="Rock Slide", type="Rock", category="Physical",
        base_power=75, accuracy=90, priority=0, target="allAdjacentFoes",
    )
    assert dex.effectiveness(rock_slide, dex.get_species("Charizard")) == 4.0
    assert dex.effectiveness(rock_slide, dex.get_species("Garchomp")) == 0.5


def test_unknown_types_raise(dex):
    with pytest.raises(KeyError):
        dex.type_chart.effectiveness("Fairy", ("Fire",))
    with pytest.raises(KeyError):
        dex.type_chart.effectiveness("Fire", ("Fairy",))


def test_round_trips_through_json(dex, tmp_path):
    path = tmp_path / "dex.json"
    dex.save(path)
    restored = Dex.model_validate_json(path.read_text(encoding="utf-8"))
    assert restored.get_species("Charizard").types == ("Fire", "Flying")
    assert restored.type_chart.effectiveness("Rock", ("Fire", "Flying")) == 4.0


def test_species_info_is_immutable(dex):
    with pytest.raises(Exception):
        dex.get_species("Charizard").types = ("Water",)


def test_empty_dex_is_usable_but_empty():
    empty = Dex()
    assert empty.species == {}
    with pytest.raises(KeyError):
        empty.get_move("tackle")


def test_species_info_constructed_directly():
    info = SpeciesInfo(
        species_id="x",
        name="X",
        types=("Water",),
        base_stats=dex_stats(),
    )
    assert info.types == ("Water",)


def dex_stats():
    from champions_ai.dex import BaseStats

    return BaseStats(hp=1, attack=1, defense=1, special_attack=1, special_defense=1, speed=1)


def test_type_chart_can_be_built_directly():
    chart = TypeChart(multipliers={"Fire": {"Grass": 2.0}})
    assert chart.effectiveness("Fire", ("Grass",)) == 2.0
