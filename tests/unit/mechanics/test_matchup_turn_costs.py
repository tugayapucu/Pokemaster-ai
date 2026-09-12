"""`matchup` can price moves that cost a turn, as the move scorer does.

It priced a charge move charging now and a recharge move as free, instant hits,
so Team Preview and switching overrated any Pokemon whose best move was one of
them. With `price_turn_costs` the same prices apply: a charge move charging
this turn is half its hit and cannot end a knockout race now; a recharge move is
1 / (1 + accuracy) of its hit and can.
"""

import pytest

from champions_ai.dex import BaseStats, Dex, MoveInfo, SpeciesInfo, TypeChart
from champions_ai.domain import PokemonSet
from champions_ai.mechanics import estimate_stats, matchup

STATS = BaseStats(hp=90, attack=90, defense=90, special_attack=90, special_defense=90, speed=90)


def _move(move_id, flags, accuracy=100):
    return MoveInfo(
        move_id=move_id, name=move_id, type="Normal", category="Special",
        base_power=120, accuracy=accuracy, priority=0, target="normal",
        flags=frozenset(flags),
    )


DEX = Dex(
    species={
        s: SpeciesInfo(species_id=s, name=s.capitalize(), types=("Normal",),
                       base_stats=STATS, abilities=("Run Away",))
        for s in ("ours", "theirs")
    },
    moves={
        "plain": _move("plain", {"protect"}),
        "megablast": _move("megablast", {"recharge", "protect"}, accuracy=90),
        "solarbeam": _move("solarbeam", {"charge", "protect"}),
    },
    types=("Normal",),
    type_chart=TypeChart(multipliers={"Normal": {"Normal": 1.0}}),
)
THEIRS = DEX.get_species("theirs")


def _offence(move, **kwargs):
    ours = PokemonSet(species="Ours", level=50, ability="", moves=(move,))
    return matchup(DEX, ours, THEIRS, level=50, **kwargs).offence


def test_off_by_default_a_turn_costing_move_is_priced_as_before():
    assert _offence("megablast") == _offence("megablast", price_turn_costs=False)


def test_a_recharge_move_is_worth_its_hit_over_the_turns_it_commits():
    assert _offence("megablast", price_turn_costs=True) == pytest.approx(
        _offence("megablast") / 1.9
    )


def test_a_charge_move_charging_now_is_worth_half_its_hit():
    assert _offence("solarbeam", price_turn_costs=True) == pytest.approx(
        _offence("solarbeam") * 0.5
    )


def test_a_charge_move_that_fires_at_once_in_the_sun_is_a_full_hit():
    assert _offence("solarbeam", price_turn_costs=True, weather="sunnyday") == pytest.approx(
        _offence("solarbeam", weather="sunnyday")
    )


def test_an_ordinary_move_is_untouched():
    assert _offence("plain", price_turn_costs=True) == _offence("plain")


def _race(move, **kwargs):
    """Faster than them, in a race where one hit ends it either way."""
    ours = PokemonSet(species="Ours", level=50, ability="", moves=(move,))
    faster = estimate_stats(STATS, 11)["spe"] + 20
    stats = {"hp": 200, "atk": 100, "def": 100, "spa": 200, "spd": 100, "spe": faster}
    return matchup(
        DEX, ours, THEIRS, level=50, our_stats=stats, our_hp=1, their_hp=1, **kwargs
    ).speed_edge


def test_a_charge_move_cannot_win_a_knockout_race_this_turn():
    assert _race("solarbeam") > 0
    assert _race("solarbeam", price_turn_costs=True) == 0.0


def test_a_recharge_move_still_can():
    assert _race("megablast", price_turn_costs=True) > 0
