"""Scoring Team Preview on the field their six is likely to establish.

`matchup_table` scored on a bare field and said so: *"No weather at Team
Preview: the battle has not started, so none is set yet."* True, and beside the
point. No field is set **yet**. A team with Pelipper is going to be in rain, and
a grid scored on bare ground is scoring a battle that will not happen.

The design rests on the prior being a **weight** rather than a switch, which is
what these tests are mostly about. Asserting rain on sight of Pelipper is wrong
in three games out of ten, and the corpus puts Charizard's sun at 45% -- it does
not set sun, Charizard-Mega-Y does, so 45% is how often it Megas that way. A
switch would have to discard that. A weight can use it.
"""

from champions_ai.agents.heuristic import HeuristicAgent
from champions_ai.dex import Dex
from champions_ai.domain import PokemonSet, RevealedPokemon, Team, TeamPreview
from champions_ai.domain.regulation import REGULATION_M_C

TYPES = ["Water", "Fire", "Grass", "Normal"]
CHART = {
    "Water": {"Water": 1.0, "Fire": 2.0, "Grass": 0.5, "Normal": 1.0},
    "Fire": {"Water": 0.5, "Fire": 1.0, "Grass": 2.0, "Normal": 1.0},
    "Grass": {"Water": 2.0, "Fire": 0.5, "Grass": 1.0, "Normal": 1.0},
    "Normal": dict.fromkeys(TYPES, 1.0),
}
DEX = Dex.from_payload({
    "species": {
        "pelipper": {
            "name": "Pelipper", "types": ["Water"],
            "baseStats": {"hp": 60, "atk": 50, "def": 100, "spa": 95, "spd": 70, "spe": 65},
            "abilities": ["Drizzle"], "weightkg": 28.0, "baseSpecies": "Pelipper",
        },
        "rillaboom": {
            "name": "Rillaboom", "types": ["Grass"],
            "baseStats": {"hp": 100, "atk": 125, "def": 90, "spa": 60, "spd": 70, "spe": 85},
            "abilities": ["Grassy Surge"], "weightkg": 78.2, "baseSpecies": "Rillaboom",
        },
        # Species Clause forbids a repeated species, so the filler slots on
        # both sides have to be six distinct nobodies rather than one copied.
        **{
            f"plain{n}": {
                "name": f"Plain{n}", "types": ["Normal"],
                "baseStats": {"hp": 90, "atk": 90, "def": 90, "spa": 90, "spd": 90, "spe": 90},
                "abilities": [], "weightkg": 50.0, "baseSpecies": f"Plain{n}",
            }
            for n in range(6)
        },
        **{
            f"burny{n}": {
                "name": f"Burny{n}", "types": ["Fire"],
                "baseStats": {"hp": 80, "atk": 110, "def": 70, "spa": 110, "spd": 70, "spe": 100},
                "abilities": [], "weightkg": 50.0, "baseSpecies": f"Burny{n}",
            }
            for n in range(6)
        },
    },
    "moves": {"flame": {
        "name": "Flame", "type": "Fire", "category": "Special", "basePower": 90,
        "accuracy": 100, "priority": 0, "target": "normal", "flags": [], "secondaries": [],
    }},
    "items": {},
    "types": TYPES,
    "chart": CHART,
})

RAIN = {"pelipper": ("raindance", "weather", 0.68)}
GRASS = {"rillaboom": ("grassyterrain", "terrain", 0.59)}


def _set(species):
    return PokemonSet(species=species, level=50, ability="x", moves=("flame",))


def _preview(opponents):
    # Our six are Fire attackers, so rain on their side is what the grid feels.
    six = tuple(_set(f"burny{n}") for n in range(6))
    return TeamPreview(
        regulation=REGULATION_M_C,
        own_team=Team(pokemon=six),
        opponent_team=tuple(
            RevealedPokemon(species=name, level=50) for name in opponents
        ),
    )


def _agent(priors=None):
    return HeuristicAgent(DEX, field_priors=priors)


def test_a_fire_attacker_is_worth_less_into_a_team_that_brings_rain():
    """The whole point, in one assertion: our Fire move is halved on a field
    their Pelipper has not set yet and probably will."""
    preview = _preview(["pelipper"] + [f"plain{n}" for n in range(5)])
    bare = _agent().matchup_table(preview)[0][0]
    predicted = _agent(RAIN).matchup_table(preview)[0][0]
    assert predicted < bare


def test_the_prior_is_a_weight_not_a_switch():
    """At 68% the cell must land between bare ground and certain rain, or the
    probability is being read as a boolean."""
    preview = _preview(["pelipper"] + [f"plain{n}" for n in range(5)])
    bare = _agent().matchup_table(preview)[0][0]
    likely = _agent(RAIN).matchup_table(preview)[0][0]
    certain = _agent({"pelipper": ("raindance", "weather", 1.0)}).matchup_table(preview)[0][0]
    assert certain < likely < bare


def test_no_prior_is_the_old_behaviour_exactly():
    preview = _preview(["pelipper"] + [f"plain{n}" for n in range(5)])
    assert _agent().matchup_table(preview) == _agent({}).matchup_table(preview)


def test_a_species_that_predicts_nothing_leaves_the_grid_alone():
    preview = _preview([f"plain{n}" for n in range(6)])
    assert _agent(RAIN).matchup_table(preview) == _agent().matchup_table(preview)


def test_only_one_weather_and_one_terrain_can_be_predicted():
    """Two weathers cannot both be up. The likelier one wins rather than both
    being applied, which would score a field that cannot exist."""
    agent = _agent({
        "pelipper": ("raindance", "weather", 0.68),
        "plain0": ("sunnyday", "weather", 0.40),
        "rillaboom": ("grassyterrain", "terrain", 0.59),
    })
    predicted = agent._predicted_field(
        tuple(RevealedPokemon(species=s, level=50)
        for s in ["pelipper", "plain0", "rillaboom"])
    )
    assert sorted(kind for _, kind, _ in predicted) == ["terrain", "weather"]
    assert ("raindance", "weather", 0.68) in predicted


def test_a_terrain_reaches_the_grid_as_well_as_a_weather():
    """Guards the bug 0048 found: `matchup()` had no terrain parameter at all,
    so the two commonest field effects in the format were inexpressible."""
    preview = _preview(["rillaboom"] + [f"plain{n}" for n in range(5)])
    bare = _agent().matchup_table(preview)[0][0]
    assert _agent(GRASS).matchup_table(preview)[0][0] != bare
