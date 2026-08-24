"""Abilities that need no reveal.

`revealed_ability` answers "have we watched it fire", and that is the wrong
question for a species with only one ability to have. All 77 Mega formes are
like this -- Metagross-Mega is Tough Claws and there is nothing else it could
be -- so the forme change *is* the reveal, and waiting for an announcement
throws away information every player at the table already has.

The rule is not special to Mega. 42 base formes also have a single ability, so
it is stated as what it is: one candidate means no doubt. Anything with a
choice stays unknown until it shows itself.
"""

import pytest

from champions_ai.agents import HeuristicAgent
from champions_ai.dex import BaseStats, Dex, SpeciesInfo, TypeChart
from champions_ai.domain import ObservedPokemon

TYPES = ("Steel", "Psychic")


def _agent_for(abilities: tuple[str, ...]):
    species = SpeciesInfo(
        species_id="metagrossmega",
        name="Metagross-Mega",
        types=TYPES,
        base_stats=BaseStats(
            hp=80, attack=145, defense=150,
            special_attack=105, special_defense=110, speed=110,
        ),
        abilities=abilities,
    )
    dex = Dex(
        species={species.species_id: species},
        moves={},
        types=TYPES,
        type_chart=TypeChart(
            multipliers={a: dict.fromkeys(TYPES, 1.0) for a in TYPES}
        ),
    )
    observed = ObservedPokemon(
        species="Metagross-Mega", level=50, hp_percent=100, fainted=False
    )
    return HeuristicAgent(dex), observed


@pytest.fixture
def single():
    return _agent_for(("Tough Claws",))


@pytest.fixture
def either():
    return _agent_for(("Tough Claws", "Clear Body"))


def test_one_possible_ability_is_known_on_sight(single):
    agent, observed = single
    assert observed.revealed_ability is None
    assert agent._known_ability(observed) == "toughclaws"


def test_a_species_with_a_choice_stays_unknown(either):
    agent, observed = either
    assert agent._known_ability(observed) is None


def test_a_revealed_ability_still_wins(either):
    """Seeing it fire settles it even where the species has options."""
    agent, observed = either
    seen = observed.model_copy(update={"revealed_ability": "clearbody"})
    assert agent._known_ability(seen) == "clearbody"


def test_an_unknown_species_is_not_guessed_at(single):
    agent, _ = single
    stranger = ObservedPokemon(
        species="Not-In-The-Dex", level=50, hp_percent=100, fainted=False
    )
    assert agent._known_ability(stranger) is None


def test_nothing_there_is_not_an_ability(single):
    agent, _ = single
    assert agent._known_ability(None) is None
