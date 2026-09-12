"""`matchup` can be scored on a terrain, and the terrain actually reaches it.

`estimate_damage` has taken a `terrain` since terrain was modelled at all --
it is what applies the 1.3 to a Grass move in Grassy Terrain -- but `matchup`
had no such parameter, so every score this project computed was computed on
bare ground. Nothing failed. The number was simply a little wrong, everywhere,
and silently.

These tests are deliberately about the *plumbing* rather than the multiplier:
`test_base_power` already proves the 1.3 is right. What was missing is a test
that the argument survives the two layers between the caller and it, which is
exactly the gap that let the omission last.
"""

from champions_ai.dex import Dex
from champions_ai.domain import PokemonSet
from champions_ai.mechanics import matchup

TYPES = ["Grass", "Normal"]
DEX = Dex.from_payload({
    "species": {
        "leafy": {
            "name": "Leafy", "types": ["Grass"],
            "baseStats": {"hp": 100, "atk": 120, "def": 80, "spa": 80, "spd": 80, "spe": 100},
            "abilities": [], "weightkg": 1.0, "baseSpecies": "Leafy",
        },
        "plain": {
            "name": "Plain", "types": ["Normal"],
            "baseStats": {"hp": 100, "atk": 80, "def": 80, "spa": 80, "spd": 80, "spe": 80},
            "abilities": [], "weightkg": 1.0, "baseSpecies": "Plain",
        },
    },
    "moves": {"vinelash": {
        "name": "Vine Lash", "type": "Grass", "category": "Physical", "basePower": 90,
        "accuracy": 100, "priority": 0, "target": "normal", "flags": [], "secondaries": [],
    }},
    "types": TYPES, "chart": {a: dict.fromkeys(TYPES, 1.0) for a in TYPES},
})

GRASS_ATTACKER = PokemonSet(species="leafy", level=50, ability="x", moves=("vinelash",))


def _net(terrain):
    return matchup(
        DEX, GRASS_ATTACKER, DEX.get_species("plain"), level=50, terrain=terrain
    )


def test_a_grass_move_hits_harder_on_grassy_terrain():
    """The bonus is the attacker's footing, so our offence is what moves."""
    assert _net("grassyterrain").offence > _net(None).offence


def test_bare_ground_is_the_old_behaviour_exactly():
    """A caller that passes nothing must get the number it got before."""
    before = matchup(DEX, GRASS_ATTACKER, DEX.get_species("plain"), level=50)
    assert before.net == _net(None).net


def test_an_unrelated_terrain_changes_nothing_for_this_pair():
    """Guards against a terrain that is 'applied' by being truthy rather than
    by being the right one -- which is how a plumbing bug usually passes."""
    assert _net("psychicterrain").offence == _net(None).offence
