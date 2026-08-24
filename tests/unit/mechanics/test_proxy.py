"""Moves that borrow another move, and moves that rewrite what a Pokemon is.

Nine moves across the two groups, and all nine were unpriced. Every rule here
is read off the engine -- `moves.ts` and the flags already in our own dump --
rather than off the corpus, because the corpus cannot settle any of it: humans
picked one of the four borrowing moves seven times in 500 battles, and none of
the five retyping ones at all.

Rarity in 500 games is a fact about that sample, not about the game.
"""

from champions_ai.dex import MoveInfo
from champions_ai.mechanics import (
    copycat_borrows,
    gains_from_repeating,
    instruct_repeats,
    retyped_by,
    sleep_talk_candidates,
    spite_removes,
)


def _move(move_id: str, **kwargs) -> MoveInfo:
    fields = dict(
        move_id=move_id,
        name=move_id.title(),
        type="Normal",
        category="Physical",
        base_power=80,
        accuracy=100,
        priority=0,
        target="normal",
    )
    fields.update(kwargs)
    return MoveInfo(**fields)


EARTHQUAKE = _move("earthquake", type="Ground", base_power=100)
PROTECT = _move("protect", category="Status", base_power=0, accuracy=None,
                target="self", flags=frozenset({"failcopycat", "noassist"}))
SWORDS_DANCE = _move("swordsdance", category="Status", base_power=0, accuracy=None,
                     target="self", self_boosts={"atk": 2})
TRICK_ROOM = _move("trickroom", category="Status", base_power=0, accuracy=None,
                   target="all", pseudo_weather="trickroom")
SOLAR_BEAM = _move("solarbeam", category="Special", base_power=120,
                   flags=frozenset({"charge", "failinstruct"}))
HYPER_BEAM = _move("hyperbeam", base_power=150, flags=frozenset({"recharge"}))
SLEEP_TALK = _move("sleeptalk", category="Status", base_power=0, accuracy=None,
                   target="self",
                   flags=frozenset({"nosleeptalk", "failinstruct", "failcopycat"}))


# --- Copycat ------------------------------------------------------------


def test_copycat_becomes_whatever_went_last():
    assert copycat_borrows(EARTHQUAKE) is EARTHQUAKE


def test_copycat_fails_before_anybody_has_moved():
    assert copycat_borrows(None) is None


def test_copycat_refuses_the_moves_the_engine_flags():
    """Protect carries `failcopycat`, and the flag has been in the dump since
    the dump existed with nothing reading it."""
    assert copycat_borrows(PROTECT) is None


# --- Sleep Talk ---------------------------------------------------------


def test_sleep_talk_does_nothing_while_awake():
    """A legality fact, not a valuation: the engine refuses the move, so an
    agent that does not know this throws away a turn."""
    assert sleep_talk_candidates([EARTHQUAKE, PROTECT], asleep=False) == ()


def test_sleep_talk_picks_from_the_moveset_while_asleep():
    picked = sleep_talk_candidates([EARTHQUAKE, PROTECT], asleep=True)
    assert picked == (EARTHQUAKE, PROTECT)


def test_sleep_talk_cannot_pick_itself():
    picked = sleep_talk_candidates([EARTHQUAKE, SLEEP_TALK], asleep=True)
    assert picked == (EARTHQUAKE,)


# --- Instruct -----------------------------------------------------------


def test_instruct_repeats_an_ordinary_move():
    assert instruct_repeats(EARTHQUAKE) is EARTHQUAKE


def test_instruct_fails_with_nothing_to_repeat():
    assert instruct_repeats(None) is None


def test_instruct_refuses_a_move_that_is_still_in_progress():
    """The engine checks `charge` and `recharge` explicitly: a move half-way
    through has no clean point to restart from."""
    assert instruct_repeats(SOLAR_BEAM) is None
    assert instruct_repeats(HYPER_BEAM) is None


# --- Spite --------------------------------------------------------------


def test_spite_needs_a_move_to_bite_into():
    assert spite_removes(None) is None
    assert spite_removes(EARTHQUAKE) is EARTHQUAKE


# --- what is worth doing twice in one turn -------------------------------


def test_damage_and_stat_stages_are_worth_repeating():
    assert gains_from_repeating(EARTHQUAKE)
    assert gains_from_repeating(SWORDS_DANCE)


def test_protect_is_not_worth_repeating():
    """Instruct fires the repeat in the *same* turn, so a second Protect is
    simply refused. Without this rule the best-scoring repeat for one ally in
    the corpus came out as its Protect, at 310 points for nothing at all."""
    assert not gains_from_repeating(PROTECT)


def test_a_field_effect_is_not_worth_repeating():
    """A second Trick Room in one turn undoes the first."""
    assert not gains_from_repeating(TRICK_ROOM)


# --- moves that rewrite what a Pokemon is --------------------------------


def test_soak_makes_the_target_pure_water():
    assert retyped_by("soak", ("Steel", "Ghost")) == ("Water",)


def test_soak_fails_on_something_already_pure_water():
    """The engine returns false, so the turn is wasted -- which is a different
    statement from the move being weak, and an agent needs to know which."""
    assert retyped_by("soak", ("Water",)) is None


def test_soak_still_works_on_a_part_water_type():
    assert retyped_by("soak", ("Water", "Bug")) == ("Water",)


def test_trick_or_treat_adds_a_third_type():
    assert retyped_by("trickortreat", ("Flying", "Steel")) == ("Flying", "Steel", "Ghost")


def test_trick_or_treat_fails_on_something_already_part_ghost():
    assert retyped_by("trickortreat", ("Ghost", "Poison")) is None


def test_forests_curse_adds_grass():
    assert retyped_by("forestscurse", ("Fire",)) == ("Fire", "Grass")


def test_magic_powder_makes_the_target_pure_psychic():
    assert retyped_by("magicpowder", ("Dark", "Steel")) == ("Psychic",)


def test_reflect_type_copies_the_target():
    assert retyped_by("reflecttype", ("Fire",), copied=("Water", "Bug")) == ("Water", "Bug")


def test_reflect_type_fails_when_we_already_match():
    assert retyped_by("reflecttype", ("Water", "Bug"), copied=("Water", "Bug")) is None
