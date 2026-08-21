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
    DamageCollector,
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


# ------------------------------------------------------------- scoring, not parsing


def _sample(actual, **overrides):
    """A hit our model predicts at roughly 40-47 damage."""
    from champions_ai.evaluation.differential import DamageSample

    defaults = dict(
        attacker=_mon("Charizard"), defender=_mon("Garchomp"), move_id="tackle",
        actual=actual, defender_hp_before=200, weather=None, critical=False,
        spread=False, spread_targets=1, truncated=False,
    )
    return DamageSample(**{**defaults, **overrides})


def _dex():
    from champions_ai.dex import Dex

    types = ["Normal", "Dragon", "Ground", "Fire", "Flying"]
    def species(name, kinds):
        return {
            "name": name, "types": kinds,
            "baseStats": {"hp": 100, "atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
            "abilities": [], "weightkg": 1.0, "baseSpecies": name,
        }
    return Dex.from_payload({
        "species": {"charizard": species("Charizard", ["Fire", "Flying"]),
                    "garchomp": species("Garchomp", ["Dragon", "Ground"])},
        "moves": {"tackle": {
            "name": "Tackle", "type": "Normal", "category": "Physical", "basePower": 80,
            "accuracy": 100, "priority": 0, "target": "normal", "flags": [], "secondaries": [],
        }},
        "types": types, "chart": {a: dict.fromkeys(types, 1.0) for a in types},
    })


def test_a_hit_inside_the_predicted_range_counts_as_agreement():
    from champions_ai.evaluation.differential import compare

    dex = _dex()
    low, high = _sample(0).predict(dex, level=50, doubles=False)
    report = compare([_sample((low + high) // 2)], dex, doubles=False)
    assert report.samples == 1
    assert report.inside_range == 1
    assert report.accuracy == 1.0


def test_under_and_over_prediction_are_counted_separately():
    """Which direction the model is wrong in is the whole diagnostic."""
    from champions_ai.evaluation.differential import compare

    dex = _dex()
    low, high = _sample(0).predict(dex, level=50, doubles=False)
    report = compare([_sample(high + 50), _sample(max(1, low - 5))], dex, doubles=False)
    assert report.above_range == 1, "engine dealt more than predicted"
    assert report.below_range == 1
    assert report.inside_range == 0


def test_a_knockout_is_skipped_rather_than_scored():
    """Its recorded damage is what the target could absorb, not what was dealt,
    so scoring it would report every overkill as an over-prediction."""
    from champions_ai.evaluation.differential import compare

    report = compare([_sample(3, truncated=True)], _dex(), doubles=False)
    assert report.samples == 0
    assert report.skipped == 1


def test_a_critical_hit_is_skipped_by_default_but_can_be_included():
    """The model estimates the ordinary roll; counting crits as misses would
    report a known omission as an arithmetic error."""
    from champions_ai.evaluation.differential import compare

    dex = _dex()
    crit = _sample(500, critical=True)
    assert compare([crit], dex, doubles=False).skipped == 1
    assert compare([crit], dex, doubles=False, include_crits=True).samples == 1


def test_a_move_missing_from_the_dex_is_skipped_not_fatal():
    from champions_ai.evaluation.differential import compare

    report = compare([_sample(40, move_id="nosuchmove")], _dex(), doubles=False)
    assert report.skipped == 1
    assert report.samples == 0


def test_mismatches_name_the_pokemon_and_the_direction():
    from champions_ai.evaluation.differential import compare

    dex = _dex()
    _, high = _sample(0).predict(dex, level=50, doubles=False)
    report = compare([_sample(high + 40)], dex, doubles=False)
    assert report.mismatches
    assert "Charizard" in report.mismatches[0] and "under-predicted" in report.mismatches[0]


def test_stat_stages_change_the_prediction():
    """They are absent from `computed_stats`, and with Intimidate about the same
    matchup produced actuals from 16 to 63 against one fixed prediction."""
    from champions_ai.domain import Boosts

    dex = _dex()
    plain = _sample(0)
    boosted = _sample(0, attacker=_mon("Charizard").model_copy(
        update={"boosts": Boosts(attack=2)}
    ))
    assert boosted.predict(dex, level=50, doubles=False)[0] > plain.predict(
        dex, level=50, doubles=False
    )[0]


def test_a_spread_move_reaching_one_target_is_not_reduced():
    """The engine only applies the 0.75 reduction above one target."""
    dex = _dex()
    one = _sample(0, spread=True, spread_targets=1).predict(dex, level=50, doubles=True)
    two = _sample(0, spread=True, spread_targets=2).predict(dex, level=50, doubles=True)
    assert one[0] >= two[0]


def test_an_empty_run_reports_nothing_rather_than_dividing_by_zero():
    from champions_ai.evaluation.differential import compare

    report = compare([], _dex())
    assert report.samples == 0
    assert report.accuracy == 0.0
    assert "0/0" in report.summary()


# ---------------------------------------------- reading the protocol as a stream

TURN_ONE = [
    "|switch|p1a: Charizard|Charizard, L50|180/180",
    "|switch|p2a: Garchomp|Garchomp, L50|194/194",
    "|move|p1a: Charizard|Flamethrower|p2a: Garchomp",
    "|-damage|p2a: Garchomp|150/194",
    "|turn|2",
]
TURN_TWO = [
    "|move|p1a: Charizard|Flamethrower|p2a: Garchomp",
    "|-damage|p2a: Garchomp|106/194",
    "|move|p2a: Garchomp|Earthquake|p1a: Charizard",
    "|-damage|p1a: Charizard|120/180",
    "|turn|3",
]


def test_a_collector_keeps_hp_across_chunks():
    """The runner reads the protocol a turn at a time.

    Calling the one-shot function per turn starts from an empty HP table, so
    the first hit on every target every turn has no "before" to subtract from
    and is dropped. It left about one sample per battle, and the survivors
    were second hits -- spread moves and focus-fire onto weakened targets.
    """
    collector = DamageCollector()
    streamed = collector.feed(TURN_ONE, LOOKUP) + collector.feed(TURN_TWO, LOOKUP)
    at_once = collect_samples(TURN_ONE + TURN_TWO, LOOKUP)

    assert len(streamed) == len(at_once) == 3
    assert [s.actual for s in streamed] == [s.actual for s in at_once] == [44, 44, 60]
    assert collector.unknown_hp == 0


def test_a_hit_with_no_known_starting_hp_is_counted_not_silently_dropped():
    collector = DamageCollector()
    dropped = collector.feed([
        "|move|p1a: Charizard|Flamethrower|p2a: Garchomp",
        "|-damage|p2a: Garchomp|150/194",
    ], LOOKUP)
    assert dropped == []
    assert collector.unknown_hp == 1


def test_healing_moves_the_hp_the_next_hit_is_measured_from():
    """Without this, a hit after a Roost reads as far more damage than it was."""
    collector = DamageCollector()
    collector.feed(["|switch|p2a: Garchomp|Garchomp, L50|100/194"], LOOKUP)
    samples = collector.feed([
        "|-heal|p2a: Garchomp|194/194",
        "|move|p1a: Charizard|Flamethrower|p2a: Garchomp",
        "|-damage|p2a: Garchomp|150/194",
    ], LOOKUP)
    assert [s.actual for s in samples] == [44]


def test_weather_set_in_one_chunk_still_applies_in_the_next():
    collector = DamageCollector()
    collector.feed(["|-weather|SunnyDay"], LOOKUP)
    samples = collector.feed([
        "|switch|p2a: Garchomp|Garchomp, L50|194/194",
        "|move|p1a: Charizard|Flamethrower|p2a: Garchomp",
        "|-damage|p2a: Garchomp|150/194",
    ], LOOKUP)
    assert samples[0].weather == "sunnyday"


def test_residual_damage_moves_the_hp_the_next_hit_is_measured_from():
    """Recoil is not a sample, but it lowers the bar the next hit starts from.

    Taken from a real run: Leafeon at 83 took 48 recoil to 35, then a Knock Off
    took it to 12. The Knock Off dealt 23 -- inside the predicted 22-27 -- and
    was recorded as 71, because the recoil line was skipped without recording
    the HP it left behind. Every Pokemon carrying a burn or hazard damage read
    the same way, which is most of them, and it skewed the whole report toward
    under-prediction.
    """
    collector = DamageCollector()
    samples = collector.feed([
        "|switch|p2a: Garchomp|Garchomp, L50|83/194",
        "|move|p2a: Garchomp|Double-Edge|p1a: Charizard",
        "|-damage|p1a: Charizard|40/180",
        "|-damage|p2a: Garchomp|35/194|[from] Recoil",
        "|move|p1a: Charizard|Knock Off|p2a: Garchomp",
        "|-damage|p2a: Garchomp|12/194",
    ], LOOKUP)
    knock_off = [s for s in samples if s.move_id == "knockoff"]
    assert [s.actual for s in knock_off] == [23]
    assert knock_off[0].defender_hp_before == 35


def test_status_damage_between_turns_is_recorded_too():
    """A burn tick arrives with no move pending at all, so the branch has to
    run whether or not there is one."""
    collector = DamageCollector()
    collector.feed([
        "|switch|p2a: Garchomp|Garchomp, L50|194/194",
        "|-damage|p2a: Garchomp|170/194 brn|[from] brn",
        "|turn|2",
    ], LOOKUP)
    samples = collector.feed([
        "|move|p1a: Charizard|Flamethrower|p2a: Garchomp",
        "|-damage|p2a: Garchomp|126/194 brn",
    ], LOOKUP)
    assert [s.actual for s in samples] == [44]
    assert collector.unknown_hp == 0
