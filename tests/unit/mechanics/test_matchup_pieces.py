"""The pieces `matchup` is built from.

`assumed_attacks` is the prior standing in for an opponent's unseen moveset, and
it feeds Protect's threat model as well as Team Preview. Experiment 0001 found
that treating an unrevealed opponent as harmless is what made one-turn search
inert, so "this prior is never empty" is a real invariant rather than a detail.
"""

import pytest

from champions_ai.dex import Dex
from champions_ai.domain import PokemonSet
from champions_ai.mechanics import ASSUMED_MOVE_POWER, assumed_attacks, matchup, own_stats

TYPES = ["Fire", "Water", "Normal"]
DEX = Dex.from_payload({
    "species": {
        "burny": {
            "name": "Burny", "types": ["Fire"],
            "baseStats": {"hp": 100, "atk": 120, "def": 80, "spa": 90, "spd": 80, "spe": 100},
            "abilities": [], "weightkg": 1.0, "baseSpecies": "Burny",
        },
        "dual": {
            "name": "Dual", "types": ["Fire", "Water"],
            "baseStats": {"hp": 100, "atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
            "abilities": [], "weightkg": 1.0, "baseSpecies": "Dual",
        },
    },
    "moves": {"ember": {
        "name": "Ember", "type": "Fire", "category": "Physical", "basePower": 90,
        "accuracy": 100, "priority": 0, "target": "normal", "flags": [], "secondaries": [],
    }},
    "types": TYPES, "chart": {a: dict.fromkeys(TYPES, 1.0) for a in TYPES},
})


def test_an_unseen_opponent_is_never_assumed_harmless():
    """Treating one as harmless is what made one-turn search inert (0001)."""
    assert assumed_attacks(DEX.get_species("Burny"))


def test_the_prior_covers_both_categories_of_every_type():
    """Which of the two a Pokemon actually uses is exactly what is hidden, so
    both are generated and the worst is taken."""
    moves = assumed_attacks(DEX.get_species("Dual"))
    assert {m.type for m in moves} == {"Fire", "Water"}
    assert {m.category for m in moves} == {"Physical", "Special"}
    assert all(m.base_power == ASSUMED_MOVE_POWER for m in moves)


def test_assumed_moves_are_damaging_so_they_register_as_a_threat():
    assert all(m.is_damaging for m in assumed_attacks(DEX.get_species("Burny")))


def test_own_stats_uses_the_declared_stat_points():
    """Our own side is known exactly, unlike an opponent's."""
    from champions_ai.domain import StatSpread

    invested = PokemonSet(
        species="Burny", level=50, ability="x", moves=("ember",),
        stats=StatSpread(attack=32),
    )
    plain = PokemonSet(species="Burny", level=50, ability="x", moves=("ember",))
    assert own_stats(DEX, invested)["atk"] > own_stats(DEX, plain)["atk"]


def test_a_matchup_is_signed_and_carries_its_parts():
    scored = matchup(
        DEX, PokemonSet(species="Burny", level=50, ability="x", moves=("ember",)),
        DEX.get_species("Dual"), level=50,
    )
    assert 0.0 <= scored.offence <= 1.0
    assert 0.0 <= scored.defence <= 1.0
    assert scored.net == pytest.approx(scored.offence - scored.defence + scored.speed_edge)


def test_a_matchup_with_no_usable_moves_still_scores():
    """A Pokemon whose moves we could not recover must not crash the ranking."""
    scored = matchup(
        DEX, PokemonSet(species="Burny", level=50, ability="x", moves=()),
        DEX.get_species("Dual"), level=50,
    )
    assert scored.offence == 0.0
