"""Team Preview allows that an opponent may Mega Evolve, by how often it does.

Opponent items are hidden at Team Preview, so every previewed species was
scored as its base forme. With `opponent_megas` on, a cell against a species
with a measured rate is the expectation over "it evolves" and "it does not".

The tests pin the arithmetic at its ends and its middle: a rate of 1 is the
Mega matchup, a rate of 1/2 is halfway, and a species with no rate, or the flag
off, is untouched.
"""

import pytest

from champions_ai.agents import HeuristicAgent
from champions_ai.dex import BaseStats, Dex, MoveInfo, SpeciesInfo, TypeChart
from champions_ai.domain import REGULATION_M_C, PokemonSet, RevealedPokemon, Team, TeamPreview

WEAK = BaseStats(hp=70, attack=70, defense=70, special_attack=70, special_defense=70, speed=70)
STRONG = BaseStats(
    hp=70, attack=150, defense=120, special_attack=150, special_defense=120, speed=120
)


def _species(species_id, name, stats=WEAK, base=None):
    return SpeciesInfo(
        species_id=species_id, name=name, types=("Normal",), base_stats=stats,
        abilities=("Run Away",), base_species=base or name,
    )


OURS = ["mine1", "mine2", "mine3", "mine4", "mine5", "mine6"]
FOES = ["drake", "foe2", "foe3", "foe4", "foe5", "foe6"]

DEX = Dex(
    species={
        s.species_id: s
        for s in [
            _species("drake", "Drake"),
            _species("drakemega", "Drake-Mega", STRONG, base="Drake"),
            *(_species(n, n.capitalize()) for n in OURS + FOES[1:]),
        ]
    },
    moves={
        "bash": MoveInfo(
            move_id="bash", name="Bash", type="Normal", category="Physical",
            base_power=80, accuracy=100, priority=0, target="normal",
        ),
    },
    types=("Normal",),
    type_chart=TypeChart(multipliers={"Normal": {"Normal": 1.0}}),
)


def _preview(first_foe="drake"):
    return TeamPreview(
        regulation=REGULATION_M_C,
        own_team=Team(pokemon=tuple(
            PokemonSet(species=s, level=50, ability="runaway", moves=("bash",)) for s in OURS
        )),
        opponent_team=tuple(
            RevealedPokemon(species=s, level=50) for s in [first_foe, *FOES[1:]]
        ),
    )


def _agent(rate, on=True):
    return HeuristicAgent(
        DEX, mega_priors={"drake": ("Drake-Mega", rate)}, opponent_megas=on
    )


def test_off_by_default_the_rates_change_nothing():
    plain = HeuristicAgent(DEX).matchup_table(_preview())
    assert _agent(0.9, on=False).matchup_table(_preview()) == plain


def test_a_rate_of_one_is_the_mega_matchup():
    against_mega = HeuristicAgent(DEX).matchup_table(_preview("drakemega"))
    blended = _agent(1.0).matchup_table(_preview())
    assert [row[0] for row in blended] == pytest.approx([row[0] for row in against_mega])


def test_a_rate_of_a_half_lands_halfway():
    base = HeuristicAgent(DEX).matchup_table(_preview())
    mega = HeuristicAgent(DEX).matchup_table(_preview("drakemega"))
    blended = _agent(0.5).matchup_table(_preview())
    for row_b, row_m, row_x in zip(base, mega, blended):
        assert row_x[0] == pytest.approx((row_b[0] + row_m[0]) / 2)


def test_the_mega_really_is_a_harder_matchup_here():
    """Guards the fixture: if base and Mega scored the same, the two tests
    above would pass without testing anything."""
    base = HeuristicAgent(DEX).matchup_table(_preview())
    mega = HeuristicAgent(DEX).matchup_table(_preview("drakemega"))
    assert sum(row[0] for row in mega) < sum(row[0] for row in base)


def test_a_species_without_a_rate_is_scored_as_itself():
    plain = HeuristicAgent(DEX).matchup_table(_preview())
    blended = _agent(0.9).matchup_table(_preview())
    assert [row[1:] for row in blended] == [row[1:] for row in plain]
