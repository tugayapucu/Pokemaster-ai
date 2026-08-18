"""Single-turn effects, and the Protect streak built on top of them.

`|-singleturn|` lasts exactly one turn. Accumulating it forever made a Pokemon
that used Protect once read as protected for the rest of the battle -- a silent
error, because nothing crashes and the flag looks plausible.

The streak is the useful half: consecutive Protects are increasingly likely to
fail, so "protected last turn" and "protected once, ten turns ago" have to be
distinguishable.
"""

from champions_ai.domain import REGULATION_M_B, PokemonSet, StatSpread, Team
from champions_ai.simulator import BattleTracker


def _team() -> Team:
    return Team(
        pokemon=tuple(
            PokemonSet(
                species=species,
                level=50,
                ability="someability",
                moves=("tackle", "protect"),
                stats=StatSpread(hp=32),
            )
            for species in ("Charizard", "Garchomp")
        )
    )


def _tracker() -> BattleTracker:
    return BattleTracker(REGULATION_M_B, player=0, own_team=_team())


def _feed(tracker, *lines):
    for line in lines:
        tracker.handle({"type": "sideline", "player": tracker.own_tag, "line": line})


def _opponent(tracker, species="Incineroar"):
    for mon in tracker.opponent_side().revealed:
        if mon.species == species:
            return mon
    raise AssertionError(f"{species} not revealed")


OPENING = (
    "|turn|1",
    "|switch|p2a: Incineroar|Incineroar, L50, M|100/100",
)


def test_a_single_turn_effect_is_visible_on_the_turn_it_happens():
    tracker = _tracker()
    _feed(tracker, *OPENING, "|-singleturn|p2a: Incineroar|move: Protect")
    assert "protect" in _opponent(tracker).volatile_conditions


def test_a_single_turn_effect_expires_when_the_next_turn_begins():
    """The bug this guards: it used to persist for the whole battle."""
    tracker = _tracker()
    _feed(tracker, *OPENING, "|-singleturn|p2a: Incineroar|move: Protect", "|turn|2")
    assert "protect" not in _opponent(tracker).volatile_conditions


def test_protecting_once_gives_a_streak_of_one():
    tracker = _tracker()
    _feed(tracker, *OPENING, "|-singleturn|p2a: Incineroar|move: Protect")
    assert _opponent(tracker).protect_streak == 1


def test_protecting_on_consecutive_turns_accumulates():
    tracker = _tracker()
    _feed(
        tracker,
        *OPENING,
        "|-singleturn|p2a: Incineroar|move: Protect",
        "|turn|2",
        "|-singleturn|p2a: Incineroar|move: Protect",
    )
    assert _opponent(tracker).protect_streak == 2


def test_a_gap_resets_the_streak():
    """The engine's stall counter resets the moment you do something else."""
    tracker = _tracker()
    _feed(
        tracker,
        *OPENING,
        "|-singleturn|p2a: Incineroar|move: Protect",
        "|turn|2",
        "|move|p2a: Incineroar|Flare Blitz|p1a: X",
        "|turn|3",
        "|-singleturn|p2a: Incineroar|move: Protect",
    )
    assert _opponent(tracker).protect_streak == 1


def test_the_streak_is_forgotten_once_the_turn_after_has_passed():
    tracker = _tracker()
    _feed(
        tracker,
        *OPENING,
        "|-singleturn|p2a: Incineroar|move: Protect",
        "|turn|2",
        "|turn|3",
    )
    assert tracker.protect_streak("p2", "Incineroar") == 0


def test_switching_out_resets_the_streak():
    tracker = _tracker()
    _feed(
        tracker,
        *OPENING,
        "|-singleturn|p2a: Incineroar|move: Protect",
        "|turn|2",
        "|switch|p2a: Torkoal|Torkoal, L50, F|100/100",
        "|turn|3",
        "|switch|p2a: Incineroar|Incineroar, L50, M|100/100",
        "|-singleturn|p2a: Incineroar|move: Protect",
    )
    assert _opponent(tracker).protect_streak == 1


def test_a_relative_of_protect_counts_toward_the_same_streak():
    """Detect, Spiky Shield and friends all drive the engine's one stall counter."""
    tracker = _tracker()
    _feed(
        tracker,
        *OPENING,
        "|-singleturn|p2a: Incineroar|move: Protect",
        "|turn|2",
        "|-singleturn|p2a: Incineroar|move: Spiky Shield",
    )
    assert _opponent(tracker).protect_streak == 2


def test_a_single_turn_effect_that_is_not_protect_starts_no_streak():
    tracker = _tracker()
    _feed(tracker, *OPENING, "|-singleturn|p2a: Incineroar|move: Focus Punch")
    assert _opponent(tracker).protect_streak == 0
    assert "focuspunch" in _opponent(tracker).volatile_conditions


def test_our_own_streak_is_tracked_too():
    """The request payload says nothing about the stall counter."""
    tracker = _tracker()
    _feed(
        tracker,
        "|turn|1",
        "|switch|p1a: Charizard|Charizard, L50, M|153/153",
        "|-singleturn|p1a: Charizard|move: Protect",
    )
    assert tracker.protect_streak("p1", "Charizard") == 1
    assert tracker.protect_streak("p2", "Charizard") == 0, "sides must not collide"


def test_endure_feeds_the_same_counter_as_protect():
    """Endure shares the engine's stall counter without blocking anything.

    Missing it left a following Protect looking like a first use -- expected to
    succeed, where the engine actually gives it one chance in three.
    """
    tracker = _tracker()
    _feed(
        tracker,
        *OPENING,
        "|-singleturn|p2a: Incineroar|move: Endure",
        "|turn|2",
        "|-singleturn|p2a: Incineroar|move: Protect",
    )
    assert _opponent(tracker).protect_streak == 2


def test_wide_guard_does_not_feed_the_counter():
    """Since Gen 6 it may be used every turn, so it must not discount Protect."""
    tracker = _tracker()
    _feed(
        tracker,
        *OPENING,
        "|-singleturn|p2a: Incineroar|move: Wide Guard",
        "|turn|2",
        "|-singleturn|p2a: Incineroar|move: Protect",
    )
    assert _opponent(tracker).protect_streak == 1
