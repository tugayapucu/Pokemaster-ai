"""Team Preview scores each four in the field its own setters create.

It scored every four on bare ground, so a team built around its own weather was
ranked as though it never set any. Our abilities are known and they set the
field the moment their holder arrives -- or, for a Mega forme, the moment it
evolves -- so the field a four brings is a fact about that four.

The fixture is a rain team: a setter, a Water attacker who gains from rain, a
holder whose Mega forme sets rain, and fillers.
"""

import pytest

from champions_ai.agents import HeuristicAgent
from champions_ai.dex import BaseStats, Dex, ItemInfo, MoveInfo, SpeciesInfo, TypeChart
from champions_ai.domain import REGULATION_M_C, PokemonSet, RevealedPokemon, Team, TeamPreview
from champions_ai.mechanics import matchup

STATS = BaseStats(hp=80, attack=80, defense=80, special_attack=100, special_defense=80, speed=80)
TYPES = ("Normal", "Water")


def _species(species_id, name, ability="Run Away", types=("Normal",), base=None):
    return SpeciesInfo(
        species_id=species_id, name=name, types=types, base_stats=STATS,
        abilities=(ability,), base_species=base or name,
    )


SETTER, SWIMMER, CLOUDY = 0, 1, 2
OURS = ["Setter", "Swimmer", "Cloudy", "Fill1", "Fill2", "Fill3"]
FOES = ["Foe1", "Foe2", "Foe3", "Foe4", "Foe5", "Foe6"]

DEX = Dex(
    species={
        s.species_id: s
        for s in [
            _species("setter", "Setter", ability="Drizzle"),
            _species("swimmer", "Swimmer", types=("Water",)),
            _species("cloudy", "Cloudy"),
            _species("cloudymega", "Cloudy-Mega", ability="Drizzle", base="Cloudy"),
            *(_species(n.lower(), n) for n in OURS[3:] + FOES),
        ]
    },
    moves={
        "tackle": MoveInfo(
            move_id="tackle", name="Tackle", type="Normal", category="Physical",
            base_power=80, accuracy=100, priority=0, target="normal",
        ),
        "surf": MoveInfo(
            move_id="surf", name="Surf", type="Water", category="Special",
            base_power=90, accuracy=100, priority=0, target="normal",
        ),
    },
    types=TYPES,
    type_chart=TypeChart(multipliers={a: dict.fromkeys(TYPES, 1.0) for a in TYPES}),
    items={
        "cloudite": ItemInfo(item_id="cloudite", name="Cloudite",
                             mega_stone="Cloudy", mega_forme="Cloudy-Mega"),
    },
)


def _set(species):
    ability = "Drizzle" if species == "Setter" else "Run Away"
    move = "surf" if species == "Swimmer" else "tackle"
    item = "Cloudite" if species == "Cloudy" else None
    return PokemonSet(species=species, level=50, ability=ability, moves=(move,), item=item)


def _preview():
    return TeamPreview(
        regulation=REGULATION_M_C,
        own_team=Team(pokemon=tuple(_set(s) for s in OURS)),
        opponent_team=tuple(RevealedPokemon(species=s, level=50) for s in FOES),
    )


def test_a_four_with_the_setter_brings_its_weather():
    agent = HeuristicAgent(DEX)
    assert agent._own_field(_preview(), (SETTER, SWIMMER, 3, 4), None) == ("raindance", None)


def test_a_four_without_one_is_on_bare_ground():
    agent = HeuristicAgent(DEX)
    assert agent._own_field(_preview(), (SWIMMER, 3, 4, 5), None) == (None, None)


def test_a_mega_forme_sets_its_weather_only_when_it_is_the_one_evolving():
    agent = HeuristicAgent(DEX)
    preview = _preview()
    assert agent._own_field(preview, (SWIMMER, CLOUDY, 3, 4), CLOUDY) == ("raindance", None)
    assert agent._own_field(preview, (SWIMMER, CLOUDY, 3, 4), None) == (None, None)


def test_the_water_attacker_scores_higher_in_its_own_rain():
    agent = HeuristicAgent(DEX)
    bare, _ = agent._team_preview_rows(_preview())
    wet, _ = agent._team_preview_rows(_preview(), own_field=("raindance", None))
    assert sum(wet[SWIMMER]) > sum(bare[SWIMMER])
    assert wet[3] == bare[3]


def test_our_own_weather_overrides_their_predicted_weather():
    """An opponent's predicted sun is not blended in once our rain is fixed --
    two weathers cannot both be up, and we chose to bring ours."""
    agent = HeuristicAgent(DEX)
    shared = dict(level=50, doubles=True, assumed_points=agent.assumed_opponent_points)
    foe = DEX.get_species("Foe1")
    swimmer = _set("Swimmer")
    got = agent._preview_net(
        swimmer, foe, [("sunnyday", "weather", 0.9)], shared, own_field=("raindance", None)
    )
    expected = matchup(
        DEX, swimmer, foe, weather="raindance", **shared, **agent._set_for_matchup(swimmer)
    ).net
    assert got == pytest.approx(expected)


def test_off_keeps_every_four_on_bare_ground():
    agent = HeuristicAgent(DEX, own_field=False)
    assert agent._best_team_preview(_preview(), 4)[1] == (None, None)
