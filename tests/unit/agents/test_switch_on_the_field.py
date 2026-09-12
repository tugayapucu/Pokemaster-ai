"""Switch decisions are scored on the field that is actually up.

`_matchup_against_field` had the `Observation` in hand and passed neither
`weather` nor `terrain` to `matchup()`, while this file threads
`observation.weather` into eleven other call sites and `observation.terrain`
into six. So in rain the switch scorer priced their Fire move at full and
decided whether to switch on a battle nobody was playing.

Second lap of one bug. `tracker._on_minor_fieldstart` still carries the first:
*"`terrain` was declared, read into every Observation and never once assigned,
so it was permanently None."* That fix made the field real and put it on the
Observation. This consumer never started reading it.

Unlike the ability and field priors, this is a **fact the agent already holds**
rather than a guess about the opponent, so it is on by default. The flag keeps
the bare-field behaviour constructible -- these tests are most of why it is
worth keeping.
"""

import pytest

from champions_ai.agents.heuristic import HeuristicAgent
from champions_ai.dex import Dex
from champions_ai.domain import (
    REGULATION_M_B,
    BattlePokemon,
    Observation,
    ObservedPokemon,
    ObservedSide,
    PokemonSet,
    Side,
    SwitchAction,
)

TYPES = ["Normal", "Fire", "Water", "Grass"]
CHART = {a: dict.fromkeys(TYPES, 1.0) for a in TYPES}
CHART["Water"]["Fire"] = 2.0
CHART["Fire"]["Water"] = 0.5


def _mon(name, types):
    return {
        "name": name, "types": list(types),
        "baseStats": {"hp": 100, "atk": 110, "def": 80, "spa": 110, "spd": 80, "spe": 100},
        "abilities": [], "weightkg": 1.0, "baseSpecies": name,
    }


def _move(name, move_type):
    return {
        "name": name, "type": move_type, "category": "Physical", "basePower": 90,
        "accuracy": 100, "priority": 0, "target": "normal", "flags": [], "secondaries": [],
    }


DEX = Dex.from_payload({
    "species": {
        "firemon": _mon("Firemon", ("Fire",)),
        "watermon": _mon("Watermon", ("Water",)),
        "grassmon": _mon("Grassmon", ("Grass",)),
        "plainmon": _mon("Plainmon", ("Normal",)),
    },
    "moves": {
        "ember": _move("Ember", "Fire"),
        "splash": _move("Splash", "Water"),
        "vine": _move("Vine", "Grass"),
        "bonk": _move("Bonk", "Normal"),
    },
    "types": TYPES,
    "chart": CHART,
})
MOVE_FOR = {
    "Firemon": "ember", "Watermon": "splash",
    "Grassmon": "vine", "Plainmon": "bonk",
}


def _battle_mon(species):
    return BattlePokemon(
        pokemon_set=PokemonSet(
            species=species, level=50, ability="x", moves=(MOVE_FOR[species],)
        ),
        current_hp=175, max_hp=175,
        computed_stats={"atk": 130, "def": 100, "spa": 130, "spd": 100, "spe": 120},
        choosable_moves=(MOVE_FOR[species],),
    )


def _observation(active, bench, foe, *, weather=None, terrain=None):
    team = (_battle_mon(active),) + tuple(_battle_mon(s) for s in bench)
    return Observation(
        regulation=REGULATION_M_B,
        turn=2,
        player=0,
        own_side=Side(team=team, active_slots=(0, None)),
        opponent_side=ObservedSide(
            revealed=(ObservedPokemon(species=foe, level=50, hp_percent=100, fainted=False),),
            active_slots=(0, None),
        ),
        weather=weather,
        terrain=terrain,
    )


@pytest.fixture
def aware():
    """The shipped agent: it knows what field it is standing on."""
    return HeuristicAgent(DEX, name="aware")


@pytest.fixture
def blind():
    """The old behaviour, kept constructible for 0049's comparison."""
    return HeuristicAgent(DEX, name="blind", field_aware_switching=False)


def _switch_score(agent, observation):
    return agent.score_slot_action(observation, 0, SwitchAction(team_index=1)).score


def test_bringing_a_fire_attacker_in_is_worth_less_in_the_rain(aware):
    """Rain halves our Ember and boosts their Splash. The same switch into the
    same Pokemon is a worse idea, and the scorer must be able to say so."""
    dry = _observation("Plainmon", ["Firemon"], foe="Watermon")
    wet = _observation("Plainmon", ["Firemon"], foe="Watermon", weather="raindance")
    assert _switch_score(aware, wet) < _switch_score(aware, dry)


def test_the_same_switch_is_worth_more_in_the_sun(aware):
    """The other direction, so the test is not passing on any change at all."""
    dry = _observation("Plainmon", ["Firemon"], foe="Watermon")
    sunny = _observation("Plainmon", ["Firemon"], foe="Watermon", weather="sunnyday")
    assert _switch_score(aware, sunny) > _switch_score(aware, dry)


def test_a_terrain_reaches_the_switch_decision_too(aware):
    """Grassy Terrain raises our Grass move. Terrain is the half that matters
    most in Reg M-C -- Rillaboom is on 39.2% of teams."""
    bare = _observation("Plainmon", ["Grassmon"], foe="Watermon")
    grassy = _observation(
        "Plainmon", ["Grassmon"], foe="Watermon", terrain="grassyterrain"
    )
    assert _switch_score(aware, grassy) > _switch_score(aware, bare)


def test_the_blind_arm_cannot_tell_the_difference(blind):
    """What the bug was. Kept as a test because it is the 0049 baseline, and
    because a flag that silently does nothing is the failure mode here."""
    dry = _observation("Plainmon", ["Firemon"], foe="Watermon")
    wet = _observation("Plainmon", ["Firemon"], foe="Watermon", weather="raindance")
    assert _switch_score(blind, wet) == _switch_score(blind, dry)


def test_on_bare_ground_the_two_arms_agree(aware, blind):
    """No field up is most of the early game, and there the fix must be a
    no-op -- otherwise it is changing something other than what it claims."""
    bare = _observation("Plainmon", ["Firemon"], foe="Watermon")
    assert _switch_score(aware, bare) == _switch_score(blind, bare)
