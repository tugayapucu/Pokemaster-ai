"""Reading the engine's real move order out of the protocol.

The order the engine resolved moves in *is* the order the `|move|` lines
appear in, so unlike damage there is nothing to infer -- which makes the
parsing the only place this can go wrong, and it did: the field state has to
be read as it stood at the *start* of the turn, because the engine sorts every
action once before any of them runs.
"""

from champions_ai.domain import BattlePokemon, Boosts, PokemonSet
from champions_ai.evaluation.differential import active_by_ident
from champions_ai.evaluation.turn_order import OrderCollector


def _mon(species, speed, *, boosts=None, status=None):
    return BattlePokemon(
        pokemon_set=PokemonSet(species=species, level=50, ability="x", moves=("tackle",)),
        current_hp=200, max_hp=200, status=status,
        computed_stats={"atk": 150, "def": 100, "spa": 150, "spd": 100, "spe": speed},
        boosts=boosts or Boosts(),
    )


# Charizard is the faster of the two on paper.
LOOKUP = active_by_ident({
    "p1": [_mon("Charizard", 150)],
    "p2": [_mon("Garchomp", 100)],
})


def test_the_order_of_the_move_lines_is_the_order():
    collector = OrderCollector()
    samples = collector.feed([
        "|move|p1a: Charizard|Flamethrower|p2a: Garchomp",
        "|-damage|p2a: Garchomp|150/194",
        "|move|p2a: Garchomp|Earthquake|p1a: Charizard",
        "|-damage|p1a: Charizard|120/180",
        "|turn|2",
    ], LOOKUP)
    assert len(samples) == 1
    assert samples[0].first_move == "flamethrower"
    assert samples[0].second_move == "earthquake"


def test_a_called_move_is_not_the_action_its_user_chose():
    """Metronome and Sleep Talk print a second `|move|` line for the move they
    called. Ordering is decided by the chosen action, not the called one."""
    collector = OrderCollector()
    samples = collector.feed([
        "|move|p1a: Charizard|Metronome|p1a: Charizard",
        "|move|p1a: Charizard|Fissure|p2a: Garchomp|[from]Metronome",
        "|move|p2a: Garchomp|Earthquake|p1a: Charizard",
        "|turn|2",
    ], LOOKUP)
    assert [s.first_move for s in samples] == ["metronome"]


def test_a_pokemon_acting_twice_is_not_a_race_against_itself():
    collector = OrderCollector()
    samples = collector.feed([
        "|move|p1a: Charizard|Fake Out|p2a: Garchomp",
        "|move|p1a: Charizard|Flamethrower|p2a: Garchomp",
        "|turn|2",
    ], LOOKUP)
    assert samples == []


def test_trick_room_applies_to_the_turn_it_is_up_for():
    collector = OrderCollector()
    collector.feed(["|-fieldstart|move: Trick Room|[of] p2a: Garchomp", "|turn|2"], LOOKUP)
    samples = collector.feed([
        "|move|p2a: Garchomp|Earthquake|p1a: Charizard",
        "|move|p1a: Charizard|Flamethrower|p2a: Garchomp",
        "|turn|3",
    ], LOOKUP)
    assert samples[0].trick_room


def test_trick_room_expiring_still_counts_for_that_turn():
    """It runs out in the residual phase, *after* every move has resolved.

    Reading the flag when the `|turn|` line arrives got the last turn of every
    Trick Room backwards -- the moves were ordered under it and the flag was
    already gone.
    """
    collector = OrderCollector()
    collector.feed(["|-fieldstart|move: Trick Room", "|turn|2"], LOOKUP)
    samples = collector.feed([
        "|move|p2a: Garchomp|Earthquake|p1a: Charizard",
        "|move|p1a: Charizard|Flamethrower|p2a: Garchomp",
        "|-fieldend|move: Trick Room",
        "|turn|3",
    ], LOOKUP)
    assert samples[0].trick_room, "the turn was ordered under Trick Room"


def test_trick_room_going_up_does_not_reorder_the_turn_it_went_up_on():
    """The engine sorts once at the start of the turn, so a Trick Room set
    this turn changes nothing until the next one."""
    collector = OrderCollector()
    samples = collector.feed([
        "|move|p2a: Garchomp|Trick Room|p2a: Garchomp",
        "|-fieldstart|move: Trick Room",
        "|move|p1a: Charizard|Flamethrower|p2a: Garchomp",
        "|turn|2",
    ], LOOKUP)
    assert not samples[0].trick_room


def test_tailwind_is_recorded_per_side():
    collector = OrderCollector()
    collector.feed(["|-sidestart|p1: Player 1|move: Tailwind", "|turn|2"], LOOKUP)
    samples = collector.feed([
        "|move|p1a: Charizard|Flamethrower|p2a: Garchomp",
        "|move|p2a: Garchomp|Earthquake|p1a: Charizard",
        "|turn|3",
    ], LOOKUP)
    assert samples[0].first_tailwind
    assert not samples[0].second_tailwind
