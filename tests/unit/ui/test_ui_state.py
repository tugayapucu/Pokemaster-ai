"""The board and the advice, as the browser client reads them.

The client draws buttons from this and sends back lines of the typed language,
so what matters here is that every fact a player would press is present -- and
that the four ways a position can fail to be scored are reported as problems
rather than as an empty shortlist, which a player would read as "nothing worth
doing".
"""

import pytest

from champions_ai.domain import REGULATION_M_B, BattlePokemon, Boosts, PokemonSet, Side, StatSpread
from champions_ai.position import Position
from champions_ai.ui.state import advice, board

THEIR_SIX = ("kingambit", "rillaboom", "pelipper", "golisopod", "basculegion", "sinistcha")


class _Named:
    def __init__(self, name, type_="Normal", power=0):
        self.name = name
        self.type = type_
        self.base_power = power


class _Dex:
    def __init__(self):
        self._species = {name: _Named(name.title()) for name in (*THEIR_SIX, "torkoal")}
        self._moves = {"heatwave": _Named("Heat Wave", "Fire", 95),
                       "protect": _Named("Protect", "Normal", 0)}

    def get_species(self, species):
        return self._species[species]

    def get_move(self, move_id):
        return self._moves[move_id]


def _mon(species, moves=("heatwave", "protect"), **overrides):
    defaults = dict(
        pokemon_set=PokemonSet(species=species, level=50, ability="drought", moves=moves,
                               stats=StatSpread(hp=11)),
        current_hp=150, max_hp=150, current_ability="drought", current_item="charcoal",
        move_pp=(16, 8),
    )
    return BattlePokemon(**{**defaults, **overrides})


@pytest.fixture
def dex():
    return _Dex()


@pytest.fixture
def position():
    own = Side(team=(_mon("torkoal"), _mon("torkoal", current_hp=75)), active_slots=(0, 1))
    base = Position(regulation=REGULATION_M_B, own=own, their_team=THEIR_SIX)
    return base.with_them_out(0, "kingambit")


def test_the_board_carries_what_a_player_would_press(position, dex):
    drawn = board(position, dex)
    ours = drawn["ours"]["team"][0]
    assert ours["species"] == "Torkoal"
    assert ours["hp_percent"] == 100
    assert ours["slot"] == 0
    assert [move["name"] for move in ours["moves"]] == ["Heat Wave", "Protect"]
    assert [move["pp"] for move in ours["moves"]] == [16, 8]


def test_their_unseen_pokemon_are_listed_without_pretending_to_know_more(position, dex):
    drawn = board(position, dex)
    assert [mon["species"] for mon in drawn["theirs"]["seen"]] == ["Kingambit"]
    assert {mon["species"] for mon in drawn["theirs"]["unseen"]} == {
        "Rillaboom", "Pelipper", "Golisopod", "Basculegion", "Sinistcha"
    }


def test_only_stages_that_are_set_are_reported(position, dex):
    quiet = board(position, dex)["ours"]["team"][0]
    assert quiet["stages"] == {}
    boosted = position._with_own(0, boosts=Boosts(attack=2, speed=-1))
    assert board(boosted, dex)["ours"]["team"][0]["stages"] == {"atk": 2, "spe": -1}


def test_a_fainted_pokemon_says_so(position, dex):
    gone = position._with_own(1, current_hp=0)
    assert board(gone, dex)["ours"]["team"][1]["fainted"] is True
    assert board(gone, dex)["ours"]["team"][1]["hp_percent"] == 0


def test_the_field_and_the_turn_are_there(position, dex):
    later = position.with_field(weather="sunnyday").with_turn(4)
    drawn = board(later, dex)
    assert (drawn["weather"], drawn["terrain"], drawn["turn"]) == ("sunnyday", None, 4)


def test_nobody_on_the_field_is_a_problem_not_an_empty_shortlist(position, dex):
    empty = position.model_copy(update={"own": position.own.model_copy(
        update={"active_slots": (None, None)})})
    assert "Nobody of yours" in advice(empty, dex, {}, None)["problem"]


def test_a_move_without_data_is_reported_rather_than_scored(position, dex):
    """Scoring the rest would rank a shortlist missing its best entry, silently."""
    result = advice(position, dex, {}, None)
    assert "No move data" in result["problem"]


def test_the_shortlist_reports_the_measured_cost_not_the_confidence(position, dex):
    """0042: the confidence was a softmax share at an unswept temperature."""
    from types import SimpleNamespace

    from champions_ai.domain import MoveData

    move_data = {"heatwave": MoveData(move_id="heatwave", target="normal"),
                 "protect": MoveData(move_id="protect", target="self")}
    ranked = SimpleNamespace(
        considered=7,
        is_clear=True,
        recommendations=(
            SimpleNamespace(rank=1, description="Heat Wave", cost=None,
                            reasons=("hits both", "sun", "extra", "ignored")),
            SimpleNamespace(rank=2, description="Protect", cost="about 4 points",
                            reasons=()),
        ),
    )
    result = advice(position, dex, move_data, SimpleNamespace(recommend=lambda *_: ranked))
    assert result["considered"] == 7 and result["clear"] is True
    assert [entry["note"] for entry in result["recommendations"]] == [
        "top choice", "about 4 points"
    ]
    assert result["recommendations"][0]["reasons"] == ["hits both", "sun", "extra"]
