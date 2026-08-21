"""Moves that use a stat their category does not imply must be scored on it.

Three moves in this dex do: Body Press is Physical and swings with the user's
Defense, Psyshock is Special and lands on the target's Defense, and Foul Play
swings with the target's Attack. Every scoring path read `move.category`
directly, so Body Press was priced off Attack -- which on a Body Press user is
the stat they deliberately did not build.

Psyshock is how this was found: the engine differential reported it as
consistently under-predicted, because we were defending it with Special
Defense while the engine used Defense.
"""

import pytest

from champions_ai.agents.heuristic import HeuristicAgent
from champions_ai.dex import Dex
from champions_ai.domain import (
    REGULATION_M_B,
    BattlePokemon,
    Boosts,
    MoveAction,
    Observation,
    ObservedPokemon,
    ObservedSide,
    PokemonSet,
    Side,
    TargetSlot,
)


def _move(name, category, **extra):
    return {
        "name": name, "type": "Normal", "category": category, "basePower": 80,
        "accuracy": 100, "priority": 0, "target": "normal",
        "flags": [], "secondaries": [], **extra,
    }


DEX = Dex.from_payload({
    "species": {
        # Deliberately lopsided: a wall that presses, with Defense far above
        # Attack, so reading the wrong stat cannot pass by coincidence.
        "presser": {
            "name": "Presser", "types": ["Normal"],
            "baseStats": {"hp": 100, "atk": 50, "def": 150, "spa": 50, "spd": 90, "spe": 50},
            "abilities": [], "weightkg": 1.0, "baseSpecies": "Presser",
        },
        # Physically stout, specially frail -- so a Special move that hits
        # Defense scores very differently from one that hits Special Defense.
        "target": {
            "name": "Target", "types": ["Normal"],
            "baseStats": {"hp": 150, "atk": 60, "def": 150, "spa": 60, "spd": 50, "spe": 60},
            "abilities": [], "weightkg": 1.0, "baseSpecies": "Target",
        },
        # Identical to Target apart from a huge Attack, so a Foul Play into it
        # differs only by the stat the move is meant to read.
        "bruiser": {
            "name": "Bruiser", "types": ["Normal"],
            "baseStats": {"hp": 150, "atk": 170, "def": 150, "spa": 60, "spd": 50, "spe": 60},
            "abilities": [], "weightkg": 1.0, "baseSpecies": "Bruiser",
        },
    },
    "moves": {
        "bonk": _move("Bonk", "Physical"),
        "beam": _move("Beam", "Special"),
        "bodypress": _move("Body Press", "Physical", overrideOffensiveStat="def"),
        "psyshock": _move("Psyshock", "Special", overrideDefensiveStat="def"),
        "foulplay": _move("Foul Play", "Physical", overrideOffensivePokemon="target"),
    },
    "types": ["Normal"], "chart": {"Normal": {"Normal": 1.0}},
})

# Attack and Defense are far apart on purpose.
OUR_STATS = {"atk": 90, "def": 190, "spa": 90, "spd": 130, "spe": 90}
# Two sets, because a Pokemon may hold only four moves and each override
# needs its plain counterpart alongside it as a control.
CORE_MOVES = ("bonk", "beam", "bodypress", "psyshock")
FOUL_MOVES = ("bonk", "foulplay")


def _observation(our_boosts=None, their_boosts=None, foe="Target", moves=CORE_MOVES):
    mine = BattlePokemon(
        pokemon_set=PokemonSet(species="Presser", level=50, ability="x", moves=moves),
        current_hp=195, max_hp=195,
        computed_stats=OUR_STATS,
        choosable_moves=moves,
        boosts=our_boosts or Boosts(),
    )
    return Observation(
        regulation=REGULATION_M_B, turn=2, player=0,
        own_side=Side(team=(mine,), active_slots=(0, None)),
        opponent_side=ObservedSide(
            revealed=(ObservedPokemon(
                species=foe, level=50, hp_percent=100, fainted=False,
                boosts=their_boosts or Boosts(),
            ),),
            active_slots=(0, None),
        ),
    )


@pytest.fixture
def agent():
    return HeuristicAgent(DEX, name="test")


def _score(agent, move_index, **kwargs):
    return agent.score_slot_action(
        _observation(**kwargs),
        0,
        MoveAction(move_index=move_index, target=TargetSlot(side="foe", slot=0)),
    ).score


BONK, BEAM, BODY_PRESS, PSYSHOCK = range(len(CORE_MOVES))
FOUL_BONK, FOUL_PLAY = range(len(FOUL_MOVES))


# ------------------------------------------------- the user's attacking stat


def test_body_press_swings_with_defense_not_attack(agent):
    mine = _observation().own_side.team[0]
    press = DEX.get_move("bodypress")
    assert agent._attack_stat(mine, press) == OUR_STATS["def"]
    assert agent._attack_stat(mine, press) != OUR_STATS["atk"]


def test_an_ordinary_physical_move_still_swings_with_attack(agent):
    """Guards the test above against Defense being read for everything."""
    mine = _observation().own_side.team[0]
    assert agent._attack_stat(mine, DEX.get_move("bonk")) == OUR_STATS["atk"]
    assert agent._attack_stat(mine, DEX.get_move("beam")) == OUR_STATS["spa"]


def test_a_defense_boost_makes_body_press_score_higher(agent):
    """Iron Defense before Body Press is a real line, and it read as nothing."""
    plain = _score(agent, BODY_PRESS)
    fortified = _score(agent, BODY_PRESS, our_boosts=Boosts(defense=2))
    assert fortified > plain


def test_an_attack_boost_does_not_touch_body_press(agent):
    plain = _score(agent, BODY_PRESS)
    swords_dance = _score(agent, BODY_PRESS, our_boosts=Boosts(attack=2))
    assert swords_dance == pytest.approx(plain)


def test_an_attack_boost_still_raises_an_ordinary_physical_move(agent):
    assert _score(agent, BONK, our_boosts=Boosts(attack=2)) > _score(agent, BONK)


# --------------------------------------------- the target's defending stat


def test_psyshock_lands_on_defense_not_special_defense(agent):
    """The target is physically stout and specially frail, so hitting the
    wrong side of it is worth a large difference in score."""
    assert _score(agent, PSYSHOCK) < _score(agent, BEAM)


def test_a_defense_boost_on_the_target_blunts_psyshock(agent):
    plain = _score(agent, PSYSHOCK)
    fortified = _score(agent, PSYSHOCK, their_boosts=Boosts(defense=2))
    assert fortified < plain


def test_a_special_defense_boost_on_the_target_does_not(agent):
    plain = _score(agent, PSYSHOCK)
    wrong_stat = _score(agent, PSYSHOCK, their_boosts=Boosts(special_defense=2))
    assert wrong_stat == pytest.approx(plain)
    # ...but it does blunt an ordinary Special move, or the test above would
    # pass for a version that ignored target boosts entirely.
    assert _score(agent, BEAM, their_boosts=Boosts(special_defense=2)) < _score(agent, BEAM)


# ------------------------------------------------ whose attacking stat it is


def test_foul_play_swings_with_the_targets_attack(agent):
    """The same move into two targets that differ only in Attack."""
    into_bruiser = _score(agent, FOUL_PLAY, foe="Bruiser", moves=FOUL_MOVES)
    into_target = _score(agent, FOUL_PLAY, foe="Target", moves=FOUL_MOVES)
    assert into_bruiser > into_target


def test_an_ordinary_physical_move_does_not_care_who_it_hits(agent):
    """Guards the test above: Bruiser and Target share every other stat, so a
    move that reads its own Attack must score the same into either."""
    assert _score(agent, FOUL_BONK, foe="Bruiser", moves=FOUL_MOVES) == pytest.approx(
        _score(agent, FOUL_BONK, foe="Target", moves=FOUL_MOVES)
    )


def test_foul_play_ignores_our_own_attack_boost(agent):
    plain = _score(agent, FOUL_PLAY, moves=FOUL_MOVES)
    swords_dance = _score(
        agent, FOUL_PLAY, our_boosts=Boosts(attack=2), moves=FOUL_MOVES
    )
    assert swords_dance == pytest.approx(plain)


def test_foul_play_reads_the_targets_attack_boost(agent):
    """The engine reads `attacker.boosts` off whichever Pokemon it picked, so
    a Foul Play into a Swords Dance user swings at +2."""
    plain = _score(agent, FOUL_PLAY, moves=FOUL_MOVES)
    boosted = _score(
        agent, FOUL_PLAY, their_boosts=Boosts(attack=2), moves=FOUL_MOVES
    )
    assert boosted > plain
