"""Pairing engine protocol lines with the moves that caused them.

Every bug found while building this was in the *parsing*, not the model, and
each one made our damage model look wrong when it was not:

- a hit that knocked the target out records the HP it could absorb, not the
  damage dealt, so an overkill read as a wild over-prediction;
- stat stages are absent from `computed_stats`, and with Intimidate about, the
  same matchup produced actuals from 16 to 63 against one fixed prediction;
- the spread reduction only applies when a move reaches more than one target.
"""

from champions_ai.domain import BattlePokemon, PokemonSet
from champions_ai.evaluation.differential import (
    active_by_ident,
    collect_samples,
)


def _mon(species, hp=200):
    return BattlePokemon(
        pokemon_set=PokemonSet(species=species, level=50, ability="x", moves=("tackle",)),
        current_hp=hp, max_hp=hp,
        computed_stats={"atk": 150, "def": 100, "spa": 150, "spd": 100, "spe": 100},
    )


LOOKUP = active_by_ident({"p1": [_mon("Charizard")], "p2": [_mon("Garchomp")]})


def _log(*lines):
    return list(lines)


def test_a_move_and_its_damage_are_paired():
    samples = collect_samples(_log(
        "|switch|p2a: Garchomp|Garchomp, L50, F|194/194",
        "|move|p1a: Charizard|Flamethrower|p2a: Garchomp",
        "|-damage|p2a: Garchomp|150/194",
    ), LOOKUP)
    assert len(samples) == 1
    assert samples[0].move_id == "flamethrower"
    assert samples[0].actual == 44
    assert not samples[0].truncated


def test_a_knockout_is_flagged_because_the_damage_is_truncated():
    """The protocol records HP lost, which for an overkill is what the target
    had rather than what the move dealt."""
    samples = collect_samples(_log(
        "|switch|p2a: Garchomp|Garchomp, L50, F|194/194",
        "|-damage|p2a: Garchomp|15/194",
        "|move|p1a: Charizard|Flamethrower|p2a: Garchomp",
        "|-damage|p2a: Garchomp|0 fnt",
    ), LOOKUP)
    assert samples[-1].truncated


def test_residual_damage_is_not_attributed_to_the_move():
    """`[from]` marks recoil, status, hazards and weather."""
    samples = collect_samples(_log(
        "|switch|p2a: Garchomp|Garchomp, L50, F|194/194",
        "|move|p1a: Charizard|Flamethrower|p2a: Garchomp",
        "|-damage|p2a: Garchomp|150/194|[from] Stealth Rock",
    ), LOOKUP)
    assert samples == []


def test_recoil_on_the_attacker_is_not_a_sample():
    samples = collect_samples(_log(
        "|switch|p1a: Charizard|Charizard, L50, M|180/180",
        "|move|p1a: Charizard|Flare Blitz|p2a: Garchomp",
        "|-damage|p1a: Charizard|140/180",
    ), LOOKUP)
    assert samples == []


def test_a_move_called_by_another_effect_is_skipped():
    samples = collect_samples(_log(
        "|switch|p2a: Garchomp|Garchomp, L50, F|194/194",
        "|move|p1a: Charizard|Flamethrower|p2a: Garchomp|[from]Sleep Talk",
        "|-damage|p2a: Garchomp|150/194",
    ), LOOKUP)
    assert samples == []


def test_a_critical_hit_is_flagged():
    samples = collect_samples(_log(
        "|switch|p2a: Garchomp|Garchomp, L50, F|194/194",
        "|move|p1a: Charizard|Flamethrower|p2a: Garchomp",
        "|-crit|p2a: Garchomp",
        "|-damage|p2a: Garchomp|100/194",
    ), LOOKUP)
    assert samples[0].critical


def test_a_spread_move_records_how_many_targets_it_reached():
    """The engine only applies the 0.75 reduction above one target."""
    two = collect_samples(_log(
        "|switch|p2a: Garchomp|Garchomp, L50, F|194/194",
        "|move|p1a: Charizard|Heat Wave|p2a: Garchomp|[spread] p2a,p2b",
        "|-damage|p2a: Garchomp|150/194",
    ), LOOKUP)
    assert two[0].spread and two[0].spread_targets == 2

    one = collect_samples(_log(
        "|switch|p2a: Garchomp|Garchomp, L50, F|194/194",
        "|move|p1a: Charizard|Heat Wave|p2a: Garchomp|[spread] p2a",
        "|-damage|p2a: Garchomp|150/194",
    ), LOOKUP)
    assert one[0].spread_targets == 1


def test_a_multi_hit_move_is_not_sampled():
    """One prediction cannot be compared against one of several hits."""
    samples = collect_samples(_log(
        "|switch|p2a: Garchomp|Garchomp, L50, F|194/194",
        "|move|p1a: Charizard|Dual Wingbeat|p2a: Garchomp",
        "|-hitcount|p2a: Garchomp|2",
        "|-damage|p2a: Garchomp|150/194",
    ), LOOKUP)
    assert samples == []


def test_weather_carries_into_the_sample():
    samples = collect_samples(_log(
        "|switch|p2a: Garchomp|Garchomp, L50, F|194/194",
        "|-weather|SunnyDay",
        "|move|p1a: Charizard|Flamethrower|p2a: Garchomp",
        "|-damage|p2a: Garchomp|150/194",
    ), LOOKUP)
    assert samples[0].weather == "sunnyday"


def test_an_unknown_pokemon_yields_no_sample():
    samples = collect_samples(_log(
        "|switch|p2a: Mystery|Mystery, L50, F|194/194",
        "|move|p1a: Charizard|Flamethrower|p2a: Mystery",
        "|-damage|p2a: Mystery|150/194",
    ), LOOKUP)
    assert samples == []
