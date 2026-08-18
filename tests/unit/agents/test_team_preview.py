"""Picking four of six, the first decision of every battle.

Until now the strongest agent inherited the base default -- take the declared
order and ignore the opponent entirely. These tests exist mostly to prove the
choice is actually driven by the matchup, because an inert implementation
returns a perfectly plausible-looking answer (the first four).
"""

import pytest

from champions_ai.agents.heuristic import HeuristicAgent
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_B, PokemonSet, Team, TeamPreview
from champions_ai.domain.revealed_pokemon import RevealedPokemon

TYPES = ["Normal", "Fire", "Water", "Grass"]


def _species(name, types, atk=100, spe=100):
    return {
        "name": name,
        "types": list(types),
        "baseStats": {"hp": 100, "atk": atk, "def": 80, "spa": atk, "spd": 80, "spe": spe},
        "abilities": [],
        "weightkg": 1.0,
        "baseSpecies": name,
    }


def _move(name, move_type):
    return {
        "name": name, "type": move_type, "category": "Physical", "basePower": 90,
        "accuracy": 100, "priority": 0, "target": "normal", "flags": [],
    }


# Fire > Grass > Water > Fire. Normal is neutral with everything.
CHART = {a: dict.fromkeys(TYPES, 1.0) for a in TYPES}
CHART["Fire"]["Grass"] = 2.0
CHART["Grass"]["Water"] = 2.0
CHART["Water"]["Fire"] = 2.0

DEX = Dex.from_payload(
    {
        "species": {
            "firemon": _species("Firemon", ("Fire",)),
            "watermon": _species("Watermon", ("Water",)),
            "grassmon": _species("Grassmon", ("Grass",)),
            "normalmon": _species("Normalmon", ("Normal",)),
            "slowmon": _species("Slowmon", ("Normal",), atk=40, spe=10),
            "fastmon": _species("Fastmon", ("Normal",), atk=120, spe=150),
            # Outspeeds our whole roster, so a test using it as the
            # opponent isolates type advantage from the speed term.
            "fastgrass": _species("Fastgrass", ("Grass",), spe=300),
        },
        "moves": {
            "ember": _move("Ember", "Fire"),
            "bubble": _move("Bubble", "Water"),
            "vine": _move("Vine", "Grass"),
            "tackle": _move("Tackle", "Normal"),
        },
        "types": TYPES,
        "chart": CHART,
    }
)

MOVE_FOR = {
    "Firemon": "ember", "Watermon": "bubble", "Grassmon": "vine",
    "Normalmon": "tackle", "Slowmon": "tackle", "Fastmon": "tackle",
}


def _set(species):
    return PokemonSet(
        species=species, level=50, ability="x", moves=(MOVE_FOR[species],)
    )


def _preview(own, opponent):
    return TeamPreview(
        regulation=REGULATION_M_B,
        own_team=Team(pokemon=tuple(_set(s) for s in own)),
        opponent_team=tuple(RevealedPokemon(species=s, level=50) for s in opponent),
    )


@pytest.fixture
def agent():
    return HeuristicAgent(DEX, name="test")


def _picked(agent, preview, size=4):
    action = agent.select_team_preview(preview, size)
    return [preview.own_team.pokemon[i].species for i in action.picks]


ROSTER = ["Firemon", "Watermon", "Grassmon", "Normalmon", "Slowmon", "Fastmon"]


def test_the_pick_depends_on_who_the_opponent_brought(agent):
    """The whole point. An implementation that ignores the opponent returns the
    declared order every time, which looks entirely reasonable."""
    against_grass = _picked(agent, _preview(ROSTER, ["Grassmon"] * 6))
    against_water = _picked(agent, _preview(ROSTER, ["Watermon"] * 6))
    assert against_grass != against_water


def test_it_brings_the_answer_to_what_they_brought(agent):
    """Fire beats Grass, so a roster of Grass should pull Firemon in."""
    assert "Firemon" in _picked(agent, _preview(ROSTER, ["Grassmon"] * 6))


def test_it_leaves_behind_a_pokemon_that_loses_to_everything(agent):
    """Slowmon is slow and weak; something should always displace it."""
    assert "Slowmon" not in _picked(agent, _preview(ROSTER, ["Normalmon"] * 6))


def test_it_prefers_coverage_over_four_copies_of_one_answer(agent):
    """A team is a set of answers, not a pile of individually good Pokemon.

    Against a mixed roster the pick should span types rather than stacking the
    single best matchup.
    """
    picks = _picked(
        agent, _preview(ROSTER, ["Grassmon", "Grassmon", "Watermon", "Watermon",
                                 "Firemon", "Firemon"])
    )
    assert "Firemon" in picks and "Watermon" in picks


def test_the_right_number_is_picked_without_repeats(agent):
    action = agent.select_team_preview(_preview(ROSTER, ROSTER), 4)
    assert len(action.picks) == 4
    assert len(set(action.picks)) == 4
    assert all(0 <= index < 6 for index in action.picks)


def test_the_leads_come_first_and_are_the_best_average_matchup(agent):
    """Which of their six leads is unknown, so lead on the broadest answer.

    The opponent outspeeds every one of ours here, deliberately: it makes the
    speed term identical across candidates so the assertion is about type
    advantage alone. Against a *slower* roster this is a genuinely close call
    -- Firemon's 2x damage and Fastmon's speed edge nearly cancel -- and a test
    that pinned it down would be asserting a tuning preference, not behaviour.
    """
    preview = _preview(ROSTER, ["Fastgrass"] * 6)
    action = agent.select_team_preview(preview, 4)
    assert preview.own_team.pokemon[action.picks[0]].species == "Firemon"


def test_speed_advantage_and_type_advantage_genuinely_compete(agent):
    """Recorded rather than asserted away: against a slower Grass roster, a
    faster neutral attacker edges out a super-effective slower one."""
    from champions_ai.mechanics import matchup

    grass = DEX.get_species("Grassmon")
    fire = matchup(DEX, _set("Firemon"), grass, level=50, assumed_points=12)
    fast = matchup(DEX, _set("Fastmon"), grass, level=50, assumed_points=12)
    assert fire.offence > fast.offence, "the type advantage is real"
    assert fast.speed_edge > fire.speed_edge, "so is the speed advantage"
    assert abs(fire.net - fast.net) < 0.1, "and they very nearly cancel"


def test_a_speed_tie_is_not_scored_as_a_loss(agent):
    """A tie is a coin flip. Scoring it as being outsped cost a
    super-effective attacker the lead to a merely-faster one."""
    from champions_ai.mechanics import matchup

    same = DEX.get_species("Normalmon")
    # Our stats use 0 Stat Points, the opponent's an assumed spread, so match
    # them by handing the opponent nothing either.
    scored = matchup(DEX, _set("Normalmon"), same, level=50, assumed_points=0)
    assert scored.speed_edge == 0.0
    assert not scored.outspeeds


def test_missing_dex_data_scores_neutrally_rather_than_crashing(agent):
    """A species we have no data for must not read as a great or awful pick."""
    preview = _preview(ROSTER, ["Grassmon", "Mystery", "Grassmon", "Grassmon",
                                "Grassmon", "Grassmon"])
    assert len(agent.select_team_preview(preview, 4).picks) == 4


def test_explanations_name_the_best_and_worst_matchup(agent):
    reasons = agent.explain_team_preview(_preview(ROSTER, ["Fastgrass"] * 6), 4)
    assert len(reasons) == 4
    text, score = reasons[0]
    assert "Firemon" in text and "Fastgrass" in text
    assert isinstance(score, float)
