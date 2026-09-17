"""Typing an opponent's open team sheet into a position.

A tournament played with open team sheets hands a player every opponent's item,
ability and four moves before the first turn -- for all six, including the two
that are never brought. The ladder this project's corpus comes from shows
species alone, so nothing here could use that information: the scorer guessed
from priors while the answer sat on paper.

`sheet` is typed once, before the clock starts, and each sheet applies the
moment its Pokemon appears. The refusals matter as much as the storing: a
species that is not one of the six, or a move that does not exist, is a typo
under time pressure and would otherwise read as fact.
"""

import pytest

from champions_ai.domain import REGULATION_M_B, BattlePokemon, PokemonSet, Side, StatSpread
from champions_ai.position import Position
from champions_ai.position.commands import apply_all

THEIR_SIX = ("kingambit", "rillaboom", "pelipper", "golisopod", "basculegion", "sinistcha")


class _Named:
    def __init__(self, name: str) -> None:
        self.name = name


class _Dex:
    """Enough dex to resolve names, as in `test_commands`."""

    def __init__(self) -> None:
        self.species = dict.fromkeys([*THEIR_SIX, "torkoal"], None)
        self.moves = {"suckerpunch": _Named("Sucker Punch"), "ironhead": _Named("Iron Head"),
                      "heatwave": _Named("Heat Wave")}
        self.items = {"sitrusberry": _Named("Sitrus Berry"), "leftovers": _Named("Leftovers")}

    def get_move(self, move_id):
        return self.moves[move_id]

    def get_item(self, item_id):
        return self.items[item_id]


@pytest.fixture
def dex():
    return _Dex()


@pytest.fixture
def position():
    own = Side(
        team=(
            BattlePokemon(
                pokemon_set=PokemonSet(species="torkoal", level=50, ability="drought",
                                       moves=("heatwave",), stats=StatSpread(hp=11)),
                current_hp=150, max_hp=150,
            ),
        ),
        active_slots=(0, None),
    )
    return Position(regulation=REGULATION_M_B, own=own, their_team=THEIR_SIX)


def _apply(position, dex, line):
    return apply_all(position, dex, line).position


def test_a_sheet_typed_before_the_game_applies_when_the_pokemon_appears(position, dex):
    after = _apply(position, dex, "sheet kingambit, sitrus, defiant, sucker punch, iron head")
    assert not after.their_seen, "nothing has been sent out yet"

    out = _apply(after, dex, "they kingambit")
    mon = out.their_seen[0]
    assert mon.revealed_item == "sitrusberry"
    assert mon.revealed_ability == "defiant"
    assert mon.revealed_moves == frozenset({"suckerpunch", "ironhead"})


def test_a_sheet_for_a_pokemon_already_out_applies_at_once(position, dex):
    out = _apply(position, dex, "they kingambit")
    after = _apply(out, dex, "sheet kingambit, leftovers, defiant, sucker punch")
    assert after.their_seen[0].revealed_item == "leftovers"
    assert after.their_seen[0].revealed_moves == frozenset({"suckerpunch"})


def test_the_moves_reach_the_observation_the_scorer_reads(position, dex):
    """The point of the command: known moves, not priors."""
    after = _apply(position, dex, "sheet kingambit, sitrus, defiant, sucker punch, iron head")
    observed = _apply(after, dex, "they kingambit").observation().opponent_side.revealed[0]
    assert observed.revealed_moves == frozenset({"suckerpunch", "ironhead"})


def test_none_records_that_the_sheet_shows_no_item(position, dex):
    """Different from an unknown item, which in this format means "probably one"."""
    after = _apply(position, dex, "sheet kingambit, none, defiant, sucker punch")
    mon = _apply(after, dex, "they kingambit").their_seen[0]
    assert mon.revealed_item is None
    assert not mon.may_hold_item


def test_a_sheet_does_not_bring_back_an_item_already_used(position, dex):
    out = _apply(position, dex, "they kingambit; kingambit item gone")
    after = _apply(out, dex, "sheet kingambit, sitrus, defiant, sucker punch")
    assert after.their_seen[0].revealed_item is None
    assert after.their_seen[0].revealed_moves == frozenset({"suckerpunch"})


def test_a_species_they_did_not_show_is_refused(position, dex):
    with pytest.raises(ValueError):
        _apply(position, dex, "sheet torkoal, sitrus, drought, heat wave")


def test_a_move_that_does_not_exist_is_refused_and_changes_nothing(position, dex):
    with pytest.raises(ValueError):
        _apply(position, dex, "sheet kingambit, sitrus, defiant, quantum leap")
    assert position.their_sheets == {}


def test_a_sheet_needs_at_least_a_species_and_an_item(position, dex):
    with pytest.raises(ValueError, match="which sheet"):
        _apply(position, dex, "sheet kingambit")
