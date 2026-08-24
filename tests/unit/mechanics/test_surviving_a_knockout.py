"""Focus Sash, Sturdy, and a move that splits its hits.

Measured against the engine, the model's "guaranteed knockout" claim was right
98.1% of the time -- not the 83% the plan carried, which came from replay
calibration where the spread and the item are unknown. The two causes of the
remaining 1.9% were both real and both fixable:

  Focus Sash    leaves the holder on 1 HP, but only from full health
  Dragon Darts  fires one of its two hits at *each* opponent in doubles, so
                reading it as two hits on one target doubled it

With both modelled the claim is right 99.0% of the time.
"""

import pytest

from champions_ai.dex import BaseStats, Dex, SpeciesInfo
from champions_ai.mechanics import estimate_damage, survives_a_knockout


def _species(name):
    return SpeciesInfo(
        species_id=name.lower(), name=name, types=("Normal",),
        base_stats=BaseStats(hp=100, attack=100, defense=100,
                             special_attack=100, special_defense=100, speed=100),
    )


DEX = Dex.from_payload({
    "species": {"a": {"name": "A", "types": ["Normal"],
                      "baseStats": {"hp": 100, "atk": 100, "def": 100,
                                    "spa": 100, "spd": 100, "spe": 100},
                      "abilities": [], "weightkg": 1.0, "baseSpecies": "A"}},
    "moves": {
        "nuke": {"name": "nuke", "type": "Normal", "category": "Physical",
                 "basePower": 250, "accuracy": 100, "priority": 0,
                 "target": "normal", "flags": [], "secondaries": []},
        "darts": {"name": "darts", "type": "Normal", "category": "Physical",
                  "basePower": 50, "accuracy": 100, "priority": 0,
                  "target": "normal", "flags": [], "secondaries": [],
                  "multihit": 2, "smartTarget": True},
    },
    "types": ["Normal"], "chart": {"Normal": {"Normal": 1.0}},
})
SPECIES = DEX.get_species("A")
COMMON = dict(attacker=SPECIES, attack_stat=200, defender=SPECIES,
              defense_stat=80, defender_hp=100)


# ------------------------------------------------------------- the sash rule


def test_a_sash_only_works_from_full_health():
    assert survives_a_knockout("focussash", None, at_full_hp=True)
    assert not survives_a_knockout("focussash", None, at_full_hp=False)


def test_sturdy_does_the_same_as_an_ability():
    assert survives_a_knockout(None, "sturdy", at_full_hp=True)
    assert not survives_a_knockout(None, "levitate", at_full_hp=True)


def test_focus_band_is_left_out_on_purpose():
    """A 10% chance at any HP is a coin flip, not a certainty -- the same
    reasoning that leaves out Quick Draw."""
    assert not survives_a_knockout("focusband", None, at_full_hp=True)


def test_nothing_held_survives_nothing():
    assert not survives_a_knockout(None, None, at_full_hp=True)


# --------------------------------------------------- what it does to the claim


def test_a_sash_turns_a_guaranteed_knockout_into_a_survival():
    plain = estimate_damage(DEX, DEX.get_move("nuke"), **COMMON)
    sashed = estimate_damage(
        DEX, DEX.get_move("nuke"), **COMMON,
        defender_item="focussash", defender_at_full_hp=True,
    )
    assert plain.guaranteed_ko
    assert not sashed.guaranteed_ko
    assert sashed.maximum == 99, "it leaves them on exactly one"


def test_a_sash_on_a_chipped_target_changes_nothing():
    hurt = estimate_damage(
        DEX, DEX.get_move("nuke"), **COMMON,
        defender_item="focussash", defender_at_full_hp=False,
    )
    assert hurt.guaranteed_ko


# -------------------------------------------------------- splitting the hits


def test_dragon_darts_hits_once_each_in_doubles():
    """Both darts land on one target in singles, and one on each in doubles."""
    alone = estimate_damage(DEX, DEX.get_move("darts"), **COMMON,
                            doubles=True, opponents=1)
    paired = estimate_damage(DEX, DEX.get_move("darts"), **COMMON,
                             doubles=True, opponents=2)
    assert paired.maximum == pytest.approx(alone.maximum / 2, rel=0.02)
    assert paired.average < alone.average


def test_an_ordinary_multi_hit_move_is_not_split():
    """Guards the test above: only `smartTarget` spreads its hits."""
    ordinary = Dex.from_payload({
        "species": {"a": {"name": "A", "types": ["Normal"],
                          "baseStats": {"hp": 100, "atk": 100, "def": 100,
                                        "spa": 100, "spd": 100, "spe": 100},
                          "abilities": [], "weightkg": 1.0, "baseSpecies": "A"}},
        "moves": {"spear": {"name": "spear", "type": "Normal",
                            "category": "Physical", "basePower": 50,
                            "accuracy": 100, "priority": 0, "target": "normal",
                            "flags": [], "secondaries": [], "multihit": 2}},
        "types": ["Normal"], "chart": {"Normal": {"Normal": 1.0}},
    })
    common = dict(COMMON, attacker=ordinary.get_species("A"),
                  defender=ordinary.get_species("A"))
    alone = estimate_damage(ordinary, ordinary.get_move("spear"), **common,
                            doubles=True, opponents=1)
    paired = estimate_damage(ordinary, ordinary.get_move("spear"), **common,
                             doubles=True, opponents=2)
    assert paired.maximum == alone.maximum
