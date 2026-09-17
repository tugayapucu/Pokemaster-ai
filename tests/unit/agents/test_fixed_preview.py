"""Scouting a team with the four *you* would bring.

Without this the agent picks at Team Preview, so a scout measures the team and
the picker together: on one candidate the two differed by 42 battles of 240 on
the same opponents and seeds. `scout --bring` pins our side and leaves theirs
alone, and the counters here are what proves the second half.
"""

import pytest

from champions_ai.agents import FixedPreviewAgent
from champions_ai.dex import BaseStats, Dex, SpeciesInfo, TypeChart
from champions_ai.domain import (
    REGULATION_M_B,
    PokemonSet,
    StatSpread,
    Team,
    TeamPreview,
)

SIX = ("Torkoal", "Kingambit", "Pelipper", "Rillaboom", "Golisopod", "Sinistcha")
OTHERS = ("Basculegion", "Sneasler", "Salamence", "Milotic", "Excadrill", "Gholdengo")
STATS = BaseStats(hp=80, attack=80, defense=80, special_attack=80, special_defense=80, speed=80)


def _dex() -> Dex:
    species = {
        name.lower(): SpeciesInfo(
            species_id=name.lower(), name=name, types=("Normal",), base_stats=STATS,
            abilities=("Run Away",),
        )
        for name in (*SIX, *OTHERS)
    }
    return Dex(species=species, moves={}, types=("Normal",),
               type_chart=TypeChart(multipliers={"Normal": {"Normal": 1.0}}), items={})


def _team(names) -> Team:
    return Team(pokemon=tuple(
        PokemonSet(species=name, level=50, ability="runaway", moves=("tackle",),
                   stats=StatSpread(hp=11))
        for name in names
    ))


def _preview(own, opponent) -> TeamPreview:
    return TeamPreview.from_teams(REGULATION_M_B, _team(own), _team(opponent))


def _agent(picks=(0, 1, 2, 3), own=SIX) -> FixedPreviewAgent:
    return FixedPreviewAgent(_dex(), own_species=own, picks=picks)


def test_our_own_preview_is_the_four_we_chose_in_lead_order():
    agent = _agent(picks=(3, 0, 5, 1))
    action = agent.select_team_preview(_preview(SIX, OTHERS), 4)
    assert action.picks == (3, 0, 5, 1)
    assert agent.forced == 1


def test_an_opposing_preview_is_left_to_the_agent():
    """The far side must keep picking for itself, or the comparison is not a
    team against the field -- it is a team against a field playing our four."""
    agent = _agent()
    agent.select_team_preview(_preview(OTHERS, SIX), 4)
    assert agent.forced == 0
    assert agent.left_to_the_agent == 1


def test_a_mirror_of_our_six_is_counted_rather_than_assumed_away():
    """`scout_team` uses one agent for both sides, so an opposing team with our
    exact six is forced too. Rare, and reported instead of hidden."""
    agent = _agent()
    agent.select_team_preview(_preview(SIX, SIX), 4)
    assert (agent.forced, agent.forced_on_a_mirror) == (1, 1)


def test_the_wrong_number_for_the_regulation_is_refused():
    agent = _agent(picks=(0, 1, 2))
    with pytest.raises(ValueError, match="brings 4"):
        agent.select_team_preview(_preview(SIX, OTHERS), 4)


def test_the_same_pokemon_twice_is_refused_at_construction():
    with pytest.raises(ValueError, match="twice"):
        _agent(picks=(0, 1, 1, 2))


def test_a_pick_outside_the_team_is_refused_at_construction():
    with pytest.raises(ValueError, match="not one of our"):
        _agent(picks=(0, 1, 2, 9))
