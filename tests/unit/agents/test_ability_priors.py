"""A corpus-derived guess at an opponent's ability, and what overrides it.

`_known_ability` already answered for a species with exactly one legal ability
-- a Mega forme, or one of 42 base formes -- and returned nothing for anything
with a choice. Rillaboom is in 39% of Reg M-C teams and was unknown until its
Grassy Surge fired, though the corpus holds 2,292 activations of it and no
Overgrow at all.

The prior fills **that gap and no other**. Everything here is about the edges
where it must not apply: a revealed ability beats it, an ability the species
cannot legally have is refused, and a species that was never in doubt does not
consult it.
"""

import pytest

from champions_ai.agents.heuristic import HeuristicAgent
from champions_ai.dex import Dex
from champions_ai.domain import ObservedPokemon

DEX = Dex.from_payload({
    "species": {
        # Two legal abilities, one of which the corpus says is universal.
        "rillaboom": {
            "name": "Rillaboom", "types": ["Grass"],
            "baseStats": {"hp": 100, "atk": 125, "def": 90, "spa": 60, "spd": 70, "spe": 85},
            "abilities": ["Overgrow", "Grassy Surge"],
            "weightkg": 78.2, "baseSpecies": "Rillaboom",
        },
        # One legal ability: never in doubt, so never a question for the prior.
        "torkoal": {
            "name": "Torkoal", "types": ["Fire"],
            "baseStats": {"hp": 70, "atk": 85, "def": 140, "spa": 85, "spd": 70, "spe": 20},
            "abilities": ["Drought"],
            "weightkg": 80.4, "baseSpecies": "Torkoal",
        },
    },
    "moves": {},
    "items": {},
    "types": ["Grass", "Fire"],
    "chart": {},
})


def _agent(priors=None):
    return HeuristicAgent(DEX, name="test", ability_priors=priors)


def _seen(species, revealed=None):
    return ObservedPokemon(
        species=species, level=50, hp_percent=100, fainted=False,
        revealed_ability=revealed,
    )


def test_without_a_prior_a_two_ability_species_stays_unknown():
    """The behaviour being replaced, pinned so the change is visible."""
    assert _agent()._known_ability(_seen("Rillaboom")) is None


def test_a_prior_fills_that_gap():
    agent = _agent({"rillaboom": "grassysurge"})
    assert agent._known_ability(_seen("Rillaboom")) == "grassysurge"


def test_a_revealed_ability_always_wins():
    """Predict, and move back the moment something contradicts it. One
    observation ends the guess."""
    agent = _agent({"rillaboom": "grassysurge"})
    assert agent._known_ability(_seen("Rillaboom", "overgrow")) == "overgrow"


def test_a_prior_this_species_cannot_have_is_refused():
    """A prior derived under one regulation must not name an ability this forme
    does not legally have. Rosters and abilities both move between them, and a
    stale file should degrade to silence rather than to a wrong answer."""
    agent = _agent({"rillaboom": "hugepower"})
    assert agent._known_ability(_seen("Rillaboom")) is None


def test_a_single_ability_species_does_not_need_the_prior():
    """One candidate means no doubt; that answer does not come from a corpus
    and must not be overridable by one."""
    agent = _agent({"torkoal": "shellarmor"})
    assert agent._known_ability(_seen("Torkoal")) == "drought"


def test_an_empty_prior_changes_nothing():
    """Opt-in: an agent given no file behaves exactly as it did before there
    was one."""
    assert _agent({})._known_ability(_seen("Rillaboom")) is None


@pytest.mark.parametrize("missing", [None, {}])
def test_the_default_is_off(missing):
    assert HeuristicAgent(DEX, ability_priors=missing).ability_priors == {}
