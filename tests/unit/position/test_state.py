"""A typed-in position, and the Observation it has to produce.

Two things are being checked here, and the second is the one that matters.

The first is that the model holds together: HP, stages, status, who is out.

The second is that it cannot be talked into claiming something a player does
not know. `unrevealed_count` has to count what is *brought* and not yet seen,
never what is declared and not yet seen; an opposing Pokemon that leaves the
field has to drop its stat stages, which is a bug this project has already had
once in the tracker; and a species that was never at Team Preview has to be
refused, because at a tournament the likeliest reason for one is a typo.
"""

import pytest

from champions_ai.domain import (
    REGULATION_M_B,
    BattlePokemon,
    Boosts,
    PokemonSet,
    Side,
    StatSpread,
)
from champions_ai.position import THEM, US, Position, Target

THEIR_SIX = ("kingambit", "charizard", "aerodactyl", "farigiraf", "garchomp", "sylveon")


def _mon(species: str, moves=("tackle",), hp: int = 150) -> BattlePokemon:
    return BattlePokemon(
        pokemon_set=PokemonSet(
            species=species,
            level=50,
            ability="blaze",
            moves=moves,
            stats=StatSpread(hp=11, attack=11),
        ),
        current_hp=hp,
        max_hp=hp,
    )


def _position(**changes) -> Position:
    own = Side(
        team=(_mon("blaziken"), _mon("torkoal"), _mon("mawile"), _mon("sneasler")),
        active_slots=(0, 1),
    )
    base = Position(regulation=REGULATION_M_B, own=own, their_team=THEIR_SIX)
    return base.model_copy(update=changes) if changes else base


def _ours(index: int) -> Target:
    return Target(side=US, index=index)


def _theirs(index: int) -> Target:
    return Target(side=THEM, index=index)


# -- what the opponent side is allowed to claim -------------------------------


def test_seeing_all_six_at_preview_does_not_count_as_seeing_them_in_play():
    """Team Preview shows six; four are brought and which four is hidden.

    If preview knowledge leaked into `revealed`, the agent would believe it had
    seen Pokemon that may not even be in the game, and `unrevealed_count` --
    the number it reasons about a switch against -- would read zero all game.
    """
    observation = _position().observation()
    assert observation.opponent_side.revealed == ()
    assert observation.opponent_side.unrevealed_count == 4


def test_the_unseen_count_falls_as_they_come_out():
    position = _position().with_them_out(0, "kingambit").with_them_out(1, "charizard")
    observation = position.observation()
    assert [mon.species for mon in observation.opponent_side.revealed] == [
        "kingambit",
        "charizard",
    ]
    assert observation.opponent_side.active_slots == (0, 1)
    assert observation.opponent_side.unrevealed_count == 2


def test_a_species_that_was_never_at_preview_is_refused():
    """The likeliest cause is a typo, and accepting it puts a Pokemon that is
    not in the game onto the board."""
    with pytest.raises(ValueError, match="Team Preview"):
        _position().with_them_out(0, "amoonguss")


def test_more_than_four_of_theirs_is_refused():
    position = _position()
    for slot, species in enumerate(THEIR_SIX[:4]):
        position = position.with_them_out(slot % 2, species)
    with pytest.raises(ValueError, match="only 4 are brought"):
        position.with_them_out(0, "garchomp")


def test_the_observation_is_the_one_the_rest_of_the_project_consumes():
    """It is handed straight to the recommender and the board renderer, so it
    has to satisfy `Observation` itself rather than merely resemble one."""
    observation = _position().with_them_out(0, "kingambit").observation()
    assert observation.player == 0
    assert observation.regulation == REGULATION_M_B
    assert observation.own_side.active_slots == (0, 1)


# -- edits --------------------------------------------------------------------


def test_their_hp_is_the_percentage_the_bar_shows():
    position = _position().with_them_out(0, "kingambit").with_hp(_theirs(0), 55)
    assert position.their_seen[0].hp_percent == 55


def test_our_hp_is_scaled_against_a_real_maximum():
    position = _position().with_hp(_ours(0), 50)
    assert position.own.team[0].current_hp == 75


def test_a_survivor_never_rounds_down_to_a_faint():
    """1% of 150 rounds to 2, but 1% of 60 would round to 1 and 0.4% to zero.
    A Pokemon the player can see alive must not be reported as knocked out."""
    position = _position(own=Side(team=(_mon("blaziken", hp=60),), active_slots=(0, None)))
    assert position.with_hp(_ours(0), 1).own.team[0].current_hp == 1
    assert not position.with_hp(_ours(0), 1).own.team[0].fainted


def test_zero_percent_is_a_faint_on_both_sides():
    position = _position().with_them_out(0, "kingambit")
    assert position.with_hp(_theirs(0), 0).their_seen[0].fainted
    assert position.with_hp(_ours(0), 0).own.team[0].fainted


def test_hp_outside_a_percentage_is_refused():
    with pytest.raises(ValueError, match="percentage"):
        _position().with_hp(_ours(0), 120)


def test_a_stage_is_set_to_what_the_arrows_show_not_added():
    """Typing the total twice must leave the total, because a player reads it
    off the screen rather than tracking the changes that produced it."""
    position = _position().with_boost(_ours(0), "atk", 2).with_boost(_ours(0), "atk", 2)
    assert position.own.team[0].boosts.attack == 2


def test_a_negative_stage_works_the_same_way():
    position = _position().with_them_out(0, "kingambit").with_boost(_theirs(0), "spe", -1)
    assert position.their_seen[0].boosts.speed == -1


def test_an_unknown_stat_is_refused_rather_than_ignored():
    with pytest.raises(ValueError, match="not a stat"):
        _position().with_boost(_ours(0), "hp", 1)


def test_an_unknown_status_is_refused_rather_than_stored():
    """A status the scorer has never heard of reads as no status everywhere
    downstream, which is silent rather than wrong-looking."""
    with pytest.raises(ValueError, match="not a status"):
        _position().with_status(_ours(0), "confused")
    assert _position().with_status(_ours(0), "par").own.team[0].status == "par"


def test_a_watched_move_is_recorded_as_revealed_and_as_the_last_one():
    seen = _position().with_them_out(0, "kingambit")
    position = seen.with_revealed_move(_theirs(0), "suckerpunch")
    assert position.their_seen[0].revealed_moves == frozenset({"suckerpunch"})
    assert position.their_seen[0].last_move == "suckerpunch"


def test_our_own_moves_are_not_something_we_watch():
    with pytest.raises(ValueError, match="team sheet"):
        _position().with_revealed_move(_ours(0), "flareblitz")


def test_an_item_seen_to_leave_is_stronger_than_one_never_seen():
    """`item_consumed` is what says they are now holding nothing. Without it,
    an opponent that just ate its Sitrus Berry still reads as a threat to be
    holding one."""
    position = _position().with_them_out(0, "kingambit")
    assert position.their_seen[0].may_hold_item
    assert not position.with_their_item(_theirs(0), None).their_seen[0].may_hold_item
    assert position.with_their_item(_theirs(0), "sitrusberry").their_seen[0].revealed_item == (
        "sitrusberry"
    )


# -- switching, which is where stale state hides ------------------------------


def test_a_pokemon_that_leaves_the_field_drops_its_stat_stages():
    """The tracker had exactly this bug: benched Pokemon kept the stages they
    left with, and nothing displayed the bench so nothing caught it."""
    position = (
        _position()
        .with_them_out(0, "kingambit")
        .with_boost(_theirs(0), "atk", 2)
        .with_them_out(0, "charizard")
    )
    assert position.their_seen[0].boosts == Boosts()
    assert position.their_active == (1, None)


def test_ours_drops_its_stages_on_the_way_out_too():
    position = _position().with_boost(_ours(0), "atk", 2).with_us_out(0, 2)
    assert position.own.team[0].boosts == Boosts()
    assert position.own.active_slots == (2, 1)


def test_a_pokemon_moving_across_slots_is_not_in_two_places():
    position = _position().with_them_out(0, "kingambit").with_them_out(1, "kingambit")
    assert position.their_active == (None, 0)
    # And its stages survive, because it never left the field.
    assert len(position.their_seen) == 1


def test_a_fainted_pokemon_cannot_come_back_out():
    position = _position().with_them_out(0, "kingambit").with_fainted(_theirs(0))
    with pytest.raises(ValueError, match="fainted"):
        position.with_them_out(0, "kingambit")


def test_fainting_takes_it_off_the_field():
    position = _position().with_them_out(0, "kingambit").with_fainted(_theirs(0))
    assert position.their_active == (None, None)
    assert _position().with_fainted(_ours(0)).own.active_slots == (None, 1)


def test_switching_in_one_of_ours_that_is_already_out_just_moves_it():
    position = _position().with_us_out(1, 0)
    assert position.own.active_slots == (None, 0)


# -- the field ----------------------------------------------------------------


def test_weather_and_terrain_are_separate():
    """Sun and Grassy Terrain are up together often enough that setting one
    must not silently clear the other."""
    position = _position().with_field(weather="sunnyday").with_field(terrain="grassyterrain")
    assert position.observation().weather == "sunnyday"
    assert position.observation().terrain == "grassyterrain"
    assert position.with_field(weather=None).observation().terrain == "grassyterrain"


def test_a_side_condition_belongs_to_one_side():
    position = _position().with_side_condition(THEM, "tailwind", 4)
    observation = position.observation()
    assert observation.opponent_side.side_conditions == {"tailwind": 4}
    assert observation.own_side.side_conditions == {}
    assert position.with_side_condition(THEM, "tailwind", 0).their_side_conditions == {}


def test_our_own_side_condition_reaches_the_observation():
    observation = _position().with_side_condition(US, "reflect", 5).observation()
    assert observation.own_side.side_conditions == {"reflect": 5}


# -- Mega, the largest measured win in the project ----------------------------


def test_spending_our_mega_stops_it_being_offered_again():
    """`available_specials` is what the legal-action generator reads. Leaving
    it populated after the fact recommends a second Mega Evolution, which the
    engine would refuse outright."""
    own = Side(
        team=(_mon("blaziken").model_copy(update={"available_specials": frozenset({"mega"})}),),
        active_slots=(0, None),
    )
    position = _position(own=own).with_mega_used(US)
    assert position.own.mega_used
    assert position.own.team[0].available_specials == frozenset()


def test_their_mega_is_recorded_on_their_side():
    assert _position().with_mega_used(THEM).observation().opponent_side.mega_used


# -- structural refusals ------------------------------------------------------


def test_an_opponent_slot_pointing_at_nobody_is_refused():
    with pytest.raises(ValueError, match="has been seen"):
        Position(
            regulation=REGULATION_M_B,
            own=_position().own,
            their_team=THEIR_SIX,
            their_active=(3, None),
        )


def test_a_position_broken_after_construction_is_still_caught_on_the_way_out():
    """Pydantic does not re-run validators on `model_copy`, and every edit here
    is a `model_copy`. Without the check in `observation()` the constructor
    would guard the first position built and nothing after it."""
    position = _position().with_them_out(0, "kingambit")
    with pytest.raises(ValueError, match="two opposing slots"):
        position.model_copy(update={"their_active": (0, 0)}).observation()


def test_a_turn_before_the_first_is_refused():
    with pytest.raises(ValueError, match="turns start at 1"):
        _position().with_turn(0)
