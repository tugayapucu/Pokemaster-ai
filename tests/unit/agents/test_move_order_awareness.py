"""What the agent believes about acting first.

The rule is verified against the engine elsewhere. What is tested here is the
agent reading the right things off an `Observation` and being honest about the
one thing it cannot know -- the opponent's move.

Before this, `_moves_first` consulted priority for our move and never theirs,
treated every negative priority as zero, and read raw Speed with no stage,
Tailwind, paralysis or Trick Room applied to either side.
"""

import pytest

from champions_ai.agents.heuristic import HeuristicAgent
from champions_ai.dex import Dex
from champions_ai.domain import (
    REGULATION_M_B,
    BattlePokemon,
    Boosts,
    Observation,
    ObservedPokemon,
    ObservedSide,
    PokemonSet,
    Side,
)


def _move(move_id, priority=0):
    return {
        "name": move_id, "type": "Normal", "category": "Physical", "basePower": 80,
        "accuracy": 100, "priority": priority, "target": "normal",
        "flags": [], "secondaries": [],
    }


def _stats(speed):
    return {"hp": 100, "atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": speed}


DEX = Dex.from_payload({
    "species": {
        # Base 100 Speed against base 50: ours is clearly the faster on paper.
        "swift": {"name": "Swift", "types": ["Normal"], "baseStats": _stats(100),
                  "abilities": [], "weightkg": 1.0, "baseSpecies": "Swift"},
        "slow": {"name": "Slow", "types": ["Normal"], "baseStats": _stats(50),
                 "abilities": [], "weightkg": 1.0, "baseSpecies": "Slow"},
    },
    "moves": {
        "bonk": _move("bonk"),
        "quickbonk": _move("quickbonk", priority=1),
        "slowbonk": _move("slowbonk", priority=-3),
        "hex": dict(_move("hex"), category="Status", basePower=0),
    },
    "types": ["Normal"], "chart": {"Normal": {"Normal": 1.0}},
})

OUR_SPEED = 150
THEIR_SPECIES = "Slow"  # estimated well below ours


def _observation(
    *,
    our_boosts=None,
    their_boosts=None,
    our_status=None,
    their_status=None,
    our_side_conditions=None,
    their_side_conditions=None,
    field_conditions=None,
    their_revealed=(),
    their_ability=None,
    our_ability=None,
    foe=THEIR_SPECIES,
    our_speed=OUR_SPEED,
):
    mine = BattlePokemon(
        pokemon_set=PokemonSet(species="Swift", level=50,
                               ability=our_ability or "x",
                               moves=("bonk", "quickbonk", "slowbonk", "hex")),
        current_hp=200, max_hp=200, status=our_status,
        computed_stats={"atk": 150, "def": 100, "spa": 150, "spd": 100, "spe": our_speed},
        current_ability=our_ability,
        choosable_moves=("bonk", "quickbonk", "slowbonk", "hex"),
        boosts=our_boosts or Boosts(),
    )
    return Observation(
        regulation=REGULATION_M_B, turn=2, player=0,
        own_side=Side(
            team=(mine,), active_slots=(0, None),
            side_conditions=dict(our_side_conditions or {}),
        ),
        opponent_side=ObservedSide(
            revealed=(ObservedPokemon(
                species=foe, level=50, hp_percent=100, fainted=False,
                status=their_status, boosts=their_boosts or Boosts(),
                revealed_moves=frozenset(their_revealed),
                revealed_ability=their_ability,
            ),),
            active_slots=(0, None),
            side_conditions=dict(their_side_conditions or {}),
        ),
        field_conditions=dict(field_conditions or {}),
    )


@pytest.fixture
def agent():
    return HeuristicAgent(DEX, name="test")


def _first(agent, move_id, **kwargs):
    return agent._moves_first(DEX.get_move(move_id), _observation(**kwargs), 0)


# ------------------------------------------------------------------- priority


def test_outspeeding_means_moving_first(agent):
    assert _first(agent, "bonk") == 1.0


def test_being_outsped_means_moving_second(agent):
    assert _first(agent, "bonk", our_speed=10) == 0.0


def test_our_priority_beats_a_faster_opponent(agent):
    assert _first(agent, "quickbonk", our_speed=10) == 1.0


def test_their_revealed_priority_is_no_longer_ignored(agent):
    """A Quick Attack we have seen them use beats our ordinary move even
    though we are faster. Reading only our own priority made this 1.0."""
    assert _first(agent, "bonk", their_revealed=("quickbonk",)) == 0.0


def test_matching_priority_falls_back_to_speed(agent):
    """Fake Out into a Fake Out is decided on Speed, not guaranteed."""
    assert _first(agent, "quickbonk", their_revealed=("quickbonk",)) == 1.0
    assert _first(
        agent, "quickbonk", their_revealed=("quickbonk",), our_speed=10
    ) == 0.0


def test_an_unrevealed_moveset_is_assumed_ordinary(agent):
    """Optimistic on purpose: assuming a priority move nobody has shown would
    make our own priority moves useless against every Pokemon on the turn it
    arrives."""
    assert _first(agent, "bonk", their_revealed=()) == 1.0


def test_our_negative_priority_moves_last(agent):
    """Focus Punch and Dragon Tail go last however fast their user is. Every
    negative priority used to read as an ordinary move."""
    assert _first(agent, "slowbonk") == 0.0


# ---------------------------------------------------------------- speed itself


def test_our_speed_boost_is_applied(agent):
    """Their estimated Speed is 81, so 30 loses and 30 at +6 (x4) wins."""
    assert _first(agent, "bonk", our_speed=30) == 0.0
    assert _first(agent, "bonk", our_speed=30, our_boosts=Boosts(speed=6)) == 1.0


def test_their_speed_boost_is_applied(agent):
    assert _first(agent, "bonk") == 1.0
    assert _first(agent, "bonk", their_boosts=Boosts(speed=6)) == 0.0


def test_paralysis_on_us_slows_us_down(agent):
    assert _first(agent, "bonk", our_speed=100) == 1.0
    assert _first(agent, "bonk", our_speed=100, our_status="par") == 0.0


def test_paralysis_on_them_speeds_us_up_by_comparison(agent):
    """Their 81 halves to 40, which our 50 then beats."""
    assert _first(agent, "bonk", our_speed=50) == 0.0
    assert _first(agent, "bonk", our_speed=50, their_status="par") == 1.0


def test_our_tailwind_is_applied(agent):
    assert _first(agent, "bonk", our_speed=50) == 0.0
    assert _first(
        agent, "bonk", our_speed=50, our_side_conditions={"tailwind": 0}
    ) == 1.0


def test_their_tailwind_is_applied(agent):
    assert _first(agent, "bonk") == 1.0
    assert _first(agent, "bonk", their_side_conditions={"tailwind": 0}) == 0.0


# ----------------------------------------------------------------- trick room


def test_trick_room_reverses_the_speed_comparison(agent):
    assert _first(agent, "bonk") == 1.0
    assert _first(agent, "bonk", field_conditions={"trickroom": 0}) == 0.0


def test_trick_room_does_not_reverse_priority(agent):
    """It orders on `10000 - speed`, which never touches the priority half."""
    assert _first(
        agent, "quickbonk", our_speed=10, field_conditions={"trickroom": 0}
    ) == 1.0


# ------------------------------------------------------ abilities and priority


def test_their_revealed_prankster_puts_their_status_moves_above_ours(agent):
    """`revealed_ability` was tracked by the tracker and read by nothing.

    A Grimmsnarl whose Prankster has shown itself moves before us with any
    status move, however far ahead our Speed is.
    """
    assert _first(agent, "bonk", their_revealed=("hex",)) == 1.0
    assert _first(
        agent, "bonk", their_revealed=("hex",), their_ability="prankster"
    ) == 0.0


def test_prankster_does_not_lift_their_damaging_moves(agent):
    assert _first(
        agent, "bonk", their_revealed=("bonk",), their_ability="prankster"
    ) == 1.0


def test_an_unrevealed_prankster_is_not_assumed(agent):
    """We only get to use what they have actually shown us."""
    assert _first(agent, "bonk", their_revealed=("hex",), their_ability=None) == 1.0


def test_our_own_prankster_lifts_our_status_move(agent):
    """Ours is never hidden from us -- it is in our own request payload."""
    assert _first(agent, "hex", our_speed=10) == 0.0
    assert _first(agent, "hex", our_speed=10, our_ability="prankster") == 1.0
