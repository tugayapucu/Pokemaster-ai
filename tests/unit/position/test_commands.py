"""The typed language, and the ways it must refuse.

Speed is the point -- forty seconds a turn, two tokens for the common edits --
but the tests that matter here are the refusals. A fragment matching two
Pokemon, a weather word nothing reacts to, a move that does not exist: each of
those, accepted, produces a position that looks right on screen and is wrong
underneath, which is the failure this project keeps finding in itself.

The last section is the one to keep. Every weather, terrain, side condition and
field condition this language can produce is checked against the tables the
scorer actually reads. A typo in the alias table would otherwise be stored,
echoed back to the player, and then ignored by every calculation downstream.
"""

import pytest

from champions_ai.domain import (
    REGULATION_M_B,
    BattlePokemon,
    PokemonSet,
    Side,
    StatSpread,
)
from champions_ai.mechanics.base_power import TERRAIN_BOOSTED_TYPES
from champions_ai.mechanics.damage import WEATHER_DEFENCE_BOOSTS, WEATHER_TYPE_MULTIPLIERS
from champions_ai.position import Position
from champions_ai.position.commands import (
    FIELD_CONDITIONS,
    SIDE_CONDITIONS,
    TERRAIN,
    WEATHER,
    apply,
    apply_all,
)
from champions_ai.position.names import AmbiguousName

THEIR_SIX = ("kingambit", "charizard", "aerodactyl", "farigiraf", "garchomp", "sylveon")
OUR_FOUR = ("blaziken", "torkoal", "mawile", "sneasler")


class _Move:
    def __init__(self, name: str) -> None:
        self.name = name


class _Dex:
    """Enough dex to resolve names. The real one is a 5MB dump; these tests are
    about the language, and a stub keeps them honest about what it needs."""

    def __init__(self) -> None:
        self.species = dict.fromkeys([*THEIR_SIX, *OUR_FOUR, "charmander"], None)
        self.moves = {"heatwave": _Move("Heat Wave"), "earthquake": _Move("Earthquake"),
                      "suckerpunch": _Move("Sucker Punch")}
        self.items = {"sitrusberry": _Move("Sitrus Berry"), "leftovers": _Move("Leftovers")}

    def get_move(self, move_id):
        return self.moves[move_id]

    def get_item(self, item_id):
        return self.items[item_id]


def _mon(species: str) -> BattlePokemon:
    return BattlePokemon(
        pokemon_set=PokemonSet(
            species=species, level=50, ability="blaze", moves=("tackle",),
            stats=StatSpread(hp=11),
        ),
        current_hp=150,
        max_hp=150,
    )


@pytest.fixture
def dex():
    return _Dex()


@pytest.fixture
def position():
    own = Side(team=tuple(_mon(s) for s in OUR_FOUR), active_slots=(0, 1))
    base = Position(regulation=REGULATION_M_B, own=own, their_team=THEIR_SIX)
    return base.with_them_out(0, "kingambit").with_them_out(1, "charizard")


def _apply(position, dex, line):
    return apply_all(position, dex, line).position


# -- how little has to be typed -----------------------------------------------


def test_a_fragment_reaches_the_pokemon(position, dex):
    """`char 55` mid-game, not `charizard 55`."""
    after = _apply(position, dex, "char 55")
    assert after.their_seen[1].hp_percent == 55


def test_an_exact_name_wins_over_a_longer_one_that_starts_with_it(position, dex):
    """Otherwise every exact name of a Pokemon with a longer relative would be
    ambiguous, and the full name would be unusable."""
    own = Side(team=(_mon("charizard"), _mon("charmander")), active_slots=(0, 1))
    both = Position(regulation=REGULATION_M_B, own=own, their_team=THEIR_SIX)
    assert _apply(both, dex, "charizard 40").own.team[0].current_hp == 60


def test_hp_status_and_a_knockout_are_two_tokens(position, dex):
    after = _apply(position, dex, "gambit 30")
    assert after.their_seen[0].hp_percent == 30
    assert _apply(position, dex, "gambit par").their_seen[0].status == "par"
    assert _apply(position, dex, "gambit ko").their_seen[0].fainted


def test_a_stage_reads_in_either_order(position, dex):
    assert _apply(position, dex, "gambit +2 atk").their_seen[0].boosts.attack == 2
    assert _apply(position, dex, "gambit atk +2").their_seen[0].boosts.attack == 2
    assert _apply(position, dex, "+1 spe blaziken").own.team[0].boosts.speed == 1
    assert _apply(position, dex, "gambit -1 spe").their_seen[0].boosts.speed == -1


def test_a_whole_turn_fits_on_one_line(position, dex):
    """Three or four things change a turn, and typing them separately is the
    difference between keeping up with a game and not."""
    outcome = apply_all(position, dex, "char 55; gambit ko; +1 atk blaziken")
    after = outcome.position
    assert after.their_seen[1].hp_percent == 55
    assert after.their_seen[0].fainted
    assert after.own.team[0].boosts.attack == 1
    assert "55%" in outcome.message


def test_a_refusal_partway_through_a_line_keeps_what_came_before_it(position, dex):
    """Applied in order and stopped at the first refusal, so the message says
    what actually took effect rather than what was typed."""
    with pytest.raises(ValueError):
        apply_all(position, dex, "char 55; char 900")
    # And the original is untouched, because nothing here mutates.
    assert position.their_seen[1].hp_percent == 100


# -- the refusals -------------------------------------------------------------


def test_a_fragment_matching_both_sides_is_refused_not_guessed(dex):
    """Mirror matchups happen. Editing the wrong Charizard is not something a
    player can see afterwards by looking at the board."""
    own = Side(team=(_mon("charizard"), _mon("torkoal")), active_slots=(0, 1))
    mirror = Position(regulation=REGULATION_M_B, own=own, their_team=THEIR_SIX)
    mirror = mirror.with_them_out(0, "charizard")
    with pytest.raises(ValueError, match="both sides"):
        apply(mirror, dex, "char 55")
    assert apply(mirror, dex, "their char 55").position.their_seen[0].hp_percent == 55
    assert apply(mirror, dex, "my char 50").position.own.team[0].current_hp == 75


def test_an_ambiguity_on_one_side_is_not_routed_around_to_the_other(dex):
    """The dangerous shape: two of ours match, so it quietly edits theirs."""
    own = Side(team=(_mon("charizard"), _mon("charmander")), active_slots=(0, 1))
    both = Position(regulation=REGULATION_M_B, own=own, their_team=THEIR_SIX)
    both = both.with_them_out(0, "kingambit")
    with pytest.raises(AmbiguousName, match="char"):
        apply(both, dex, "char 55")


def test_a_pokemon_that_has_not_been_seen_is_refused_with_the_way_out(position, dex):
    with pytest.raises(ValueError, match="not been out yet"):
        apply(position, dex, "garchomp 50")


def test_an_unknown_weather_is_refused_rather_than_stored(position, dex):
    with pytest.raises(ValueError, match="no weather called"):
        apply(position, dex, "weather fog")


def test_a_move_that_does_not_exist_is_refused(position, dex):
    with pytest.raises(ValueError, match="no move matches"):
        apply(position, dex, "gambit saw hyperbeam")


def test_an_unreadable_line_says_so_rather_than_doing_nothing(position, dex):
    with pytest.raises(ValueError, match="did not understand"):
        apply(position, dex, "gambit wobble")


# -- the field ----------------------------------------------------------------


def test_weather_and_terrain_are_set_by_the_word_a_player_would_use(position, dex):
    assert _apply(position, dex, "weather sun").weather == "sunnyday"
    assert _apply(position, dex, "terrain grassy").terrain == "grassyterrain"
    assert _apply(position, dex, "weather sun; weather none").weather is None


def test_who_is_out_is_named_in_slot_order(position, dex):
    after = _apply(position, dex, "they aero garchomp")
    assert [after.their_seen[i].species for i in after.their_active] == [
        "aerodactyl",
        "garchomp",
    ]
    assert _apply(position, dex, "we mawile sneasler").own.active_slots == (2, 3)


def test_a_side_condition_defaults_to_its_real_duration(position, dex):
    assert _apply(position, dex, "tailwind them").their_side_conditions == {"tailwind": 4}
    assert _apply(position, dex, "reflect us").own.side_conditions == {"reflect": 5}
    assert _apply(position, dex, "tailwind them 2").their_side_conditions == {"tailwind": 2}


def test_trick_room_is_a_field_condition_not_a_side_one(position, dex):
    assert _apply(position, dex, "room").field_conditions == {"trickroom": 5}
    assert _apply(position, dex, "room; room none").field_conditions == {}


def test_a_spent_mega_is_recorded(position, dex):
    assert _apply(position, dex, "mega them").their_mega_used
    assert _apply(position, dex, "mega us").own.mega_used


# -- the control words --------------------------------------------------------


def test_an_empty_line_asks_for_the_recommendation(position, dex):
    """The most common keystroke in the whole loop is enter."""
    assert apply_all(position, dex, "").control == "show"
    assert apply_all(position, dex, "   ").control == "show"


def test_the_control_words_are_reported_not_applied(position, dex):
    assert apply(position, dex, "q").control == "quit"
    assert apply(position, dex, "?").control == "help"
    assert apply(position, dex, "u").control == "undo"


# -- every id this language can produce, against what reads it ----------------


def test_every_weather_it_can_set_is_one_the_scorer_reacts_to():
    """A weather id nothing recognises would be stored, echoed back, and then
    ignored by every damage calculation -- visible on the board and absent from
    the numbers."""
    known = set(WEATHER_TYPE_MULTIPLIERS) | set(WEATHER_DEFENCE_BOOSTS)
    assert set(WEATHER.values()) <= known


def test_every_terrain_it_can_set_is_one_the_scorer_reacts_to():
    # Misty Terrain has no damage boost of its own -- it blocks status -- so it
    # is named here rather than looked for in the base-power table.
    assert set(TERRAIN.values()) <= set(TERRAIN_BOOSTED_TYPES) | {"mistyterrain"}


def test_every_side_and_field_condition_is_one_the_agent_reads():
    from champions_ai.agents.heuristic import PSEUDO_WEATHER_VALUE, SCREEN_CONDITIONS

    assert SCREEN_CONDITIONS <= set(SIDE_CONDITIONS)
    assert set(FIELD_CONDITIONS.values()) <= set(PSEUDO_WEATHER_VALUE)
