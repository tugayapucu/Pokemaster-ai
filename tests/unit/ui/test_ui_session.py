"""One game, held by the browser client's session.

The session owns the position and the history and nothing else: no engine, no
rules. Our own side is built by the caller, because exact stats come from the
simulator, which is also what lets these tests run without starting one.

The refusal behaviour is the part worth pinning. A button pressed by mistake
under a clock must leave the position exactly as it was, and say so, rather
than half-applying a line.
"""

import pytest

from champions_ai.domain import REGULATION_M_B, BattlePokemon, PokemonSet, Side, StatSpread
from champions_ai.ui.server import Session

THEIR_SIX = ("kingambit", "rillaboom", "pelipper", "golisopod", "basculegion", "sinistcha")


class _Named:
    def __init__(self, name, type_="Normal", power=0):
        self.name = name
        self.type = type_
        self.base_power = power


class _Dex:
    def __init__(self):
        self.species = dict.fromkeys([*THEIR_SIX, "torkoal", "gardevoir"], None)
        self.moves = {"heatwave": _Named("Heat Wave", "Fire", 95)}
        self.items = {"sitrusberry": _Named("Sitrus Berry")}

    def get_species(self, species):
        return _Named(species.title())

    def get_move(self, move_id):
        return self.moves[move_id]

    def get_item(self, item_id):
        return self.items[item_id]


def _mon(species):
    return BattlePokemon(
        pokemon_set=PokemonSet(species=species, level=50, ability="drought",
                               moves=("heatwave",), stats=StatSpread(hp=11)),
        current_hp=150, max_hp=150,
    )


@pytest.fixture
def session():
    return Session(dex=_Dex(), regulation=REGULATION_M_B, own_species=("torkoal", "gardevoir"),
                   move_data={}, recommender=None)


def _start(session):
    side = Side(team=(_mon("torkoal"), _mon("gardevoir")), active_slots=(0, 1))
    session.start(their_team=THEIR_SIX, picks=(0, 1), leads=("kingambit", "rillaboom"),
                  own_side=side)


def test_before_the_game_starts_it_offers_the_team_to_pick_from(session):
    snapshot = session.snapshot()
    assert snapshot["ready"] is False
    assert [mon["species"] for mon in snapshot["team"]] == ["torkoal", "gardevoir"]
    assert snapshot["picked_team_size"] == REGULATION_M_B.picked_team_size


def test_starting_puts_their_leads_on_the_field(session):
    _start(session)
    snapshot = session.snapshot()
    assert snapshot["ready"] is True
    assert [mon["species"] for mon in snapshot["board"]["theirs"]["seen"]] == [
        "Kingambit", "Rillaboom"
    ]
    assert snapshot["board"]["theirs"]["active"] == [0, 1]


def test_naming_the_wrong_number_of_theirs_is_refused(session):
    side = Side(team=(_mon("torkoal"),), active_slots=(0, None))
    with pytest.raises(ValueError, match="all 6"):
        session.start(their_team=("kingambit",), picks=(0,), leads=("kingambit",),
                      own_side=side)


def test_a_line_changes_the_position_and_can_be_undone(session):
    _start(session)
    session.apply("their kingambit 55")
    assert session.snapshot()["board"]["theirs"]["seen"][0]["hp_percent"] == 55
    assert session.snapshot()["can_undo"] is True

    session.undo()
    assert session.snapshot()["board"]["theirs"]["seen"][0]["hp_percent"] == 100
    assert session.snapshot()["message"] == "Undone."


def test_a_refused_line_leaves_the_position_alone(session):
    """The case that happens under a clock: a mis-typed name, half a line in."""
    _start(session)
    before = session.position
    with pytest.raises(ValueError):
        session.apply("their nosuchmon 55")
    assert session.position is before
    assert session.snapshot()["can_undo"] is False


def test_undo_with_nothing_to_undo_says_so_rather_than_failing(session):
    _start(session)
    session.undo()
    assert session.snapshot()["message"] == "Nothing to undo."


def test_a_line_before_the_game_starts_is_refused(session):
    with pytest.raises(ValueError, match="not started"):
        session.apply("their kingambit 55")
