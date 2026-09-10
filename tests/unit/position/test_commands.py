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


# -- what you may legally pick, which is the only wrong-answer gap -------------


class _RestrictionDex(_Dex):
    """Adds a moveset with a status move in it, and move categories."""

    def __init__(self) -> None:
        super().__init__()
        self.moves.update(
            {
                "flareblitz": _Move("Flare Blitz"),
                "protect": _Move("Protect"),
                "fakeout": _Move("Fake Out"),
                "partingshot": _Move("Parting Shot"),
            }
        )
        self._category = {
            "flareblitz": "Physical",
            "fakeout": "Physical",
            "protect": "Status",
            "partingshot": "Status",
            "tackle": "Physical",
        }

    def get_move(self, move_id):
        move = self.moves[move_id]
        move.category = self._category.get(move_id, "Physical")
        return move


MOVES = ("flareblitz", "protect", "fakeout", "partingshot")


@pytest.fixture
def restricted():
    """Our lead has four moves, two of them status."""
    own = Side(
        team=(
            _mon("blaziken").model_copy(
                update={
                    "pokemon_set": _mon("blaziken").pokemon_set.model_copy(
                        update={"moves": MOVES}
                    )
                }
            ),
            _mon("torkoal"),
        ),
        active_slots=(0, 1),
    )
    base = Position(regulation=REGULATION_M_B, own=own, their_team=THEIR_SIX)
    return base.with_them_out(0, "kingambit")


@pytest.fixture
def rdex():
    return _RestrictionDex()


def test_a_choice_lock_leaves_exactly_one_move(restricted, rdex):
    """The gap this closes. Without it the shortlist offers three moves the
    engine would refuse outright -- a confident wrong answer, not a missing
    one."""
    after = _apply(restricted, rdex, "blaziken locked flare blitz")
    assert after.own.team[0].disabled_moves == frozenset(MOVES) - {"flareblitz"}


def test_encore_is_the_same_shape_as_a_choice_lock(restricted, rdex):
    """Different rules, identical consequence for what may be submitted."""
    a = _apply(restricted, rdex, "blaziken locked protect")
    b = _apply(restricted, rdex, "blaziken encore protect")
    assert a.own.team[0].disabled_moves == b.own.team[0].disabled_moves


def test_a_taunt_takes_the_status_moves_and_leaves_the_rest(restricted, rdex):
    after = _apply(restricted, rdex, "blaziken taunt")
    assert after.own.team[0].disabled_moves == frozenset({"protect", "partingshot"})


def test_disable_takes_one_move_and_stacks(restricted, rdex):
    after = _apply(restricted, rdex, "blaziken disable protect")
    assert after.own.team[0].disabled_moves == frozenset({"protect"})
    both = _apply(after, rdex, "blaziken disable fake out")
    assert both.own.team[0].disabled_moves == frozenset({"protect", "fakeout"})


def test_free_clears_everything(restricted, rdex):
    locked = _apply(restricted, rdex, "blaziken locked flare blitz")
    assert _apply(locked, rdex, "blaziken free").own.team[0].disabled_moves == frozenset()


def test_a_move_it_does_not_have_is_refused(restricted, rdex):
    """Resolving against the whole dex would accept Earthquake here, disable
    nothing, and read on screen as though it had worked."""
    with pytest.raises(ValueError, match="no move matches"):
        _apply(restricted, rdex, "blaziken locked earthquake")


def test_restrictions_are_only_tracked_for_our_side(restricted, rdex):
    """We submit nothing for the opponent, so their Taunt changes no choice we
    could make. Modelling it would be a different thing, and it must not be
    smuggled in through a legality field."""
    with pytest.raises(ValueError, match="only tracked for your side"):
        _apply(restricted, rdex, "their gambit taunt")


def test_a_restriction_ends_when_the_pokemon_leaves_the_field(restricted, rdex):
    """Choice lock, Encore, Taunt and Disable all end on a switch out. Leaving
    them on the bench is the same bug shape as stale stat stages."""
    locked = _apply(restricted, rdex, "blaziken locked flare blitz")
    switched = _apply(locked, rdex, "we torkoal")
    assert switched.own.team[0].disabled_moves == frozenset()


# -- PP, which matters more here than it does in most formats -----------------


@pytest.fixture
def counted(restricted):
    """Our lead with the engine's PP on it. Protect gets 8 in Champions."""
    mon = restricted.own.team[0].model_copy(update={"move_pp": (24, 8, 16, 32)})
    return restricted.model_copy(
        update={"own": restricted.own.with_pokemon_at(0, mon)}
    )


def test_using_a_move_spends_one(counted, rdex):
    after = _apply(counted, rdex, "blaziken used protect")
    assert after.own.team[0].move_pp == (24, 7, 16, 32)
    assert after.own.team[0].last_move == "protect"


def test_pp_can_be_set_directly(counted, rdex):
    after = _apply(counted, rdex, "blaziken pp protect 2")
    assert after.own.team[0].move_pp == (24, 2, 16, 32)


def test_pp_never_goes_below_zero(counted, rdex):
    spent = _apply(counted, rdex, "blaziken pp protect 0")
    assert _apply(spent, rdex, "blaziken used protect").own.team[0].move_pp[1] == 0


def test_an_exhausted_move_really_stops_being_offered(counted, rdex):
    """The reason this is tracked at all, checked against the real generator
    rather than against the field it happens to write.

    Champions cuts every protection move to eight uses and a fifteen-turn
    doubles game can reach that, so Protect at zero has to leave the shortlist.
    """
    from champions_ai.domain import legal_joint_actions
    from champions_ai.domain.move_data import MoveData

    move_data = {
        "flareblitz": MoveData(move_id="flareblitz", target="normal"),
        "protect": MoveData(move_id="protect", target="self"),
        "fakeout": MoveData(move_id="fakeout", target="normal"),
        "partingshot": MoveData(move_id="partingshot", target="normal"),
        "tackle": MoveData(move_id="tackle", target="normal"),
    }

    def offers_protect(position):
        """A `MoveAction` carries a `move_index`, not a move id -- the index is
        into the acting Pokemon's own list, so it has to be resolved through
        that. Getting this wrong reads as 'never offered', which would let the
        second assertion below pass without the first one being true."""
        observation = position.observation()
        actions = legal_joint_actions(observation, move_data)
        for action in actions:
            for slot, choice in enumerate(action.slot_actions):
                index = observation.own_side.active_slots[slot]
                if index is None or choice.kind != "move":
                    continue
                if observation.own_side.team[index].selectable_moves[
                    choice.move_index
                ] == "protect":
                    return True
        return False

    assert offers_protect(counted), "the check cannot see Protect at all; it proves nothing"
    assert not offers_protect(_apply(counted, rdex, "blaziken pp protect 0"))


def test_an_opponents_pp_is_not_something_we_can_claim(counted, rdex):
    """Nothing on screen reports it, so a field for it is a place to invent
    one. Watching a move is `saw`, which records what was seen."""
    with pytest.raises(ValueError, match="saw <move>"):
        _apply(counted, rdex, "their gambit used sucker punch")


def test_a_move_it_does_not_have_cannot_be_spent(counted, rdex):
    with pytest.raises(ValueError, match="no move matches"):
        _apply(counted, rdex, "blaziken used earthquake")


# -- advancing a turn, which is really about the timers ------------------------


class _StallDex(_RestrictionDex):
    """Knows which moves drive the engine's stall counter."""

    def get_move(self, move_id):
        move = super().get_move(move_id)
        move.stalling = move_id in ("protect", "banefulbunker")
        return move


@pytest.fixture
def sdex():
    return _StallDex()


def test_next_advances_the_turn(position, dex):
    assert _apply(position, dex, "n").turn == 2


def test_next_ticks_every_timer_down(position, dex):
    """The actual point. A count that only moves when someone remembers to
    retype it is a count that will be wrong by the turn it matters."""
    set_up = _apply(position, dex, "tailwind them; reflect us; room")
    after = _apply(set_up, dex, "n")
    assert after.their_side_conditions == {"tailwind": 3}
    assert after.own.side_conditions == {"reflect": 4}
    assert after.field_conditions == {"trickroom": 4}


def test_a_timer_that_runs_out_is_removed_not_left_at_zero(position, dex):
    """Zero would read as present-but-expired everywhere downstream."""
    set_up = _apply(position, dex, "tailwind them 1")
    assert _apply(set_up, dex, "n").their_side_conditions == {}


def test_next_changes_nothing_else(position, dex):
    """What happened during the turn is what the player types; this only moves
    the clock."""
    before = _apply(position, dex, "gambit 40; gambit +2 atk")
    after = _apply(before, dex, "n")
    assert after.their_seen[0].hp_percent == 40
    assert after.their_seen[0].boosts.attack == 2
    assert after.their_active == before.their_active


def test_a_repeated_protect_builds_a_streak(counted, sdex):
    """A second Protect in a row succeeds about a third as often, so the
    streak is worth keeping."""
    once = _apply(counted, sdex, "blaziken used protect")
    twice = _apply(once, sdex, "blaziken used protect")
    assert once.own.team[0].protect_streak == 1
    assert twice.own.team[0].protect_streak == 2


def test_using_anything_else_breaks_the_streak(counted, sdex):
    once = _apply(counted, sdex, "blaziken used protect")
    assert _apply(once, sdex, "blaziken used flare blitz").own.team[0].protect_streak == 0


def test_a_watched_protect_builds_their_streak_too(position, sdex):
    """`saw` is how we learn anything about them, and the streak is the part
    that changes what Protect is worth to them next turn."""
    once = _apply(position, sdex, "gambit saw protect")
    assert once.their_seen[0].protect_streak == 1
    assert _apply(once, sdex, "gambit saw earthquake").their_seen[0].protect_streak == 0
