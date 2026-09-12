"""What base power does a caller get when it asks for none?

It used to be the move's *static* power -- the number printed in the dex --
which quietly split the codebase in two. The in-battle move scorer, the
differential harness and the feature builder each called `dynamic_base_power`
and handed the result in. `matchup` passed nothing, so the same Grass move was
worth 90 when Team Preview scored it and 117 when the move scorer did, three
call sites apart, on the same terrain.

Neither side was wrong about the rule. One of them was not asking. The default
is now the computed answer, and a caller that knows better still overrides it.
"""

from champions_ai.dex import Dex
from champions_ai.mechanics.damage import estimate_damage

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

MOVE = DEX.get_move("vinelash")


def _hit(**kwargs):
    return estimate_damage(
        DEX, MOVE,
        attacker=DEX.get_species("leafy"), attack_stat=150,
        defender=DEX.get_species("plain"), defense_stat=100, defender_hp=175,
        level=50, **kwargs,
    )


def test_passing_no_base_power_now_asks_the_engine_rule():
    """The Grassy Terrain 1.3 lands without the caller working it out."""
    assert _hit(terrain="grassyterrain").average > _hit(terrain=None).average


def test_an_explicit_base_power_still_wins():
    """The three callers that compute it themselves must be unaffected, or the
    bonus would be applied twice."""
    computed = _hit(terrain="grassyterrain").average
    overridden = _hit(terrain="grassyterrain", base_power=MOVE.base_power).average
    assert overridden < computed
