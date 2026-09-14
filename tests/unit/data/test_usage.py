"""Set distributions from sources that see whole sets, and drawing from them.

The pool's items came from what replays reveal, so silent items went missing.
These tests pin the two replacement sources -- Smogon's chaos file and open team
sheets -- and the draws: proportional, seeded, and respectful of Item Clause.
"""

import gzip
import json
import random
from collections import Counter

import pytest

from champions_ai.data.harvest import SpeciesEvidence, build_set
from champions_ai.data.replay import Replay, ReplayMetadata
from champions_ai.data.usage import (
    SetDistribution,
    carry_rates,
    combine,
    load_smogon_chaos,
    open_sheet_distributions,
    sample_item,
    sample_moves,
    sample_spread,
)
from champions_ai.dex import BaseStats, Dex, ItemInfo, SpeciesInfo, TypeChart

STATS = BaseStats(hp=80, attack=80, defense=80, special_attack=80, special_defense=80, speed=80)


def _species(species_id, name, base=None):
    return SpeciesInfo(
        species_id=species_id, name=name, types=("Normal",), base_stats=STATS,
        abilities=("Run Away",), base_species=base or name,
    )


DEX = Dex(
    species={
        s.species_id: s
        for s in (
            _species("drake", "Drake"),
            _species("drakemegax", "Drake-Mega-X", base="Drake"),
            _species("bloom", "Bloom"),
            _species("bloometernal", "Bloom-Eternal", base="Bloom"),
            _species("bloommega", "Bloom-Mega", base="Bloom"),
        )
    },
    moves={},
    types=("Normal",),
    type_chart=TypeChart(multipliers={"Normal": {"Normal": 1.0}}),
    items={
        "drakitex": ItemInfo(item_id="drakitex", name="Drakite X",
                             mega_stone="Drake", mega_forme="Drake-Mega-X"),
        "bloomite": ItemInfo(item_id="bloomite", name="Bloomite",
                             mega_stone="Bloom-Eternal", mega_forme="Bloom-Mega"),
        "lifeorb": ItemInfo(item_id="lifeorb", name="Life Orb"),
        "whiteherb": ItemInfo(item_id="whiteherb", name="White Herb"),
    },
)

CHAOS = {
    "info": {"metagame": "test", "cutoff": 1500},
    "data": {
        "Drake": {
            "Raw count": 100,
            "Items": {"lifeorb": 60, "nothing": 10},
            "Spreads": {"Adamant:32/32/0/0/2/0": 70},
            "Moves": {"tackle": 70, "ember": 35, "": 1},
        },
        "Drake-Mega-X": {
            "Raw count": 50,
            "Items": {"drakitex": 50},
            "Spreads": {"Jolly:2/32/0/0/0/32": 50},
            "Moves": {"tackle": 50, "roar": 25},
        },
        "Bloom-Mega": {
            "Raw count": 30,
            "Items": {"bloomite": 30},
            "Spreads": {"Modest:32/0/0/32/2/0": 30},
        },
    },
}


@pytest.fixture
def chaos_path(tmp_path):
    path = tmp_path / "chaos.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(CHAOS, handle)
    return path


def test_a_mega_entry_is_folded_into_the_species_that_holds_its_stone(chaos_path):
    usage = load_smogon_chaos(chaos_path, DEX)
    drake = usage["drake"]
    assert drake.samples == 150
    assert drake.items == Counter({"lifeorb": 60, "drakitex": 50, "": 10})
    assert drake.natures == Counter({"Adamant": 70, "Jolly": 50})
    assert drake.spreads[("Jolly", (2, 32, 0, 0, 0, 32))] == 50
    assert "drakemegax" not in usage


def test_the_stone_decides_the_holder_not_the_base_species(chaos_path):
    """A Mega that evolves from a forme is filed under that forme."""
    usage = load_smogon_chaos(chaos_path, DEX)
    assert "bloometernal" in usage and "bloom" not in usage


def test_a_plain_json_file_loads_too(tmp_path):
    path = tmp_path / "chaos.json"
    path.write_text(json.dumps(CHAOS), encoding="utf-8")
    assert "drake" in load_smogon_chaos(path, DEX)


def test_move_carry_rates_are_shares_of_whole_sets(chaos_path):
    """Divided by the set weight, not the raw count, and the empty-slot key
    Smogon writes as "" is not a move."""
    drake = load_smogon_chaos(chaos_path, DEX)["drake"]
    assert drake.sets == 120
    rates = carry_rates(drake)
    assert rates["tackle"] == 1.0
    assert rates["ember"] == pytest.approx(35 / 120)
    assert rates["roar"] == pytest.approx(25 / 120)
    assert "" not in rates


def _sheet_replay(n):
    line = (
        "|showteam|p1|Drake||Life Orb|Run Away|Tackle,Ember|Adamant||M|||50|"
        "]Bloom|Bloom-Eternal|White Herb|Run Away|Tackle|Timid||F|||50|"
    )
    return Replay(
        metadata=ReplayMetadata(
            replay_id=str(n), format_id="gen9championsvgc2026regmc",
            players=("a", "b"), ratings=(1200, 1200), upload_time=0, rated=True,
        ),
        log=(line,),
    )


def test_open_sheets_give_items_natures_and_moves_but_no_spreads():
    usage = open_sheet_distributions([_sheet_replay(n) for n in range(25)], DEX)
    assert usage["drake"].items == Counter({"lifeorb": 25})
    assert usage["drake"].natures == Counter({"Adamant": 25})
    assert usage["drake"].moves == Counter({"tackle": 25, "ember": 25})
    assert carry_rates(usage["drake"]) == {"tackle": 1.0, "ember": 1.0}
    assert not usage["drake"].spreads
    assert usage["bloometernal"].items == Counter({"whiteherb": 25})


def test_a_species_on_too_few_sheets_is_dropped():
    assert open_sheet_distributions([_sheet_replay(n) for n in range(5)], DEX) == {}


def test_the_first_source_wins_and_later_ones_fill_gaps():
    first = {"drake": SetDistribution("drake", "smogon")}
    second = {"drake": SetDistribution("drake", "open-sheets"),
              "bloom": SetDistribution("bloom", "open-sheets")}
    combined = combine(first, second)
    assert combined["drake"].source == "smogon"
    assert combined["bloom"].source == "open-sheets"


def _dist(**items):
    return SetDistribution("x", "test", items=Counter(items))


def test_items_are_drawn_in_proportion_to_use():
    dist = _dist(lifeorb=3, whiteherb=1)
    rng = random.Random(0)
    draws = Counter(sample_item(dist, rng) for _ in range(4000))
    assert 0.70 < draws["lifeorb"] / 4000 < 0.80


def test_an_item_already_on_the_team_is_never_drawn():
    dist = _dist(lifeorb=99, whiteherb=1)
    assert {sample_item(dist, random.Random(s), taken={"lifeorb"}) for s in range(50)} == {
        "whiteherb"
    }


def test_an_item_the_regulation_lacks_is_never_drawn():
    dist = _dist(lifeorb=1, oldamber=99)
    assert {sample_item(dist, random.Random(s), legal={"lifeorb"}) for s in range(50)} == {
        "lifeorb"
    }


def test_holding_nothing_is_drawn_as_none():
    assert sample_item(_dist(**{"": 1}), random.Random(0)) is None


def test_a_draw_is_reproducible_from_its_seed():
    dist = _dist(lifeorb=1, whiteherb=1, sitrusberry=1)
    first = [sample_item(dist, random.Random(7)) for _ in range(5)]
    assert first == [sample_item(dist, random.Random(7)) for _ in range(5)]


def test_a_distribution_with_natures_only_leaves_the_points_to_the_caller():
    dist = SetDistribution("x", "open-sheets", natures=Counter({"Timid": 1}))
    assert sample_spread(dist, random.Random(0)) == ("Timid", None)


def _moves(sets=4, **moves):
    return SetDistribution("x", "test", moves=Counter(moves), sets=sets)


def test_moves_are_drawn_in_proportion_to_their_carry_rate():
    dist = _moves(sets=4, a=3, b=1)
    draws = Counter(
        sample_moves(dist, random.Random(s), chosen=(), slots=1)[0] for s in range(4000)
    )
    assert 0.70 < draws["a"] / 4000 < 0.80


def test_a_move_already_chosen_is_never_drawn_and_none_repeats():
    dist = _moves(sets=4, a=4, b=2, c=2, d=2)
    for seed in range(50):
        picked = sample_moves(dist, random.Random(seed), chosen=("a",), slots=3)
        assert "a" not in picked and len(set(picked)) == len(picked) == 3


def test_a_draw_stops_when_the_distribution_runs_out():
    assert sample_moves(_moves(sets=4, a=4, b=1), random.Random(0), chosen=("a",), slots=3) == ["b"]


def test_the_corrected_weight_removes_what_the_reveal_already_covers():
    """A move revealed as often as it is carried is always in the partial set
    when carried, so it is never the answer for a slot the replay left empty."""
    dist = _moves(sets=10, protect=5, tackle=5)
    picked = {
        sample_moves(dist, random.Random(s), chosen=(), slots=1,
                     reveal_rates={"protect": 0.5})[0]
        for s in range(50)
    }
    assert picked == {"tackle"}


def test_the_corrected_weight_is_carried_given_not_revealed():
    dist = _moves(sets=10, protect=8, tackle=5)
    # protect: (0.8 - 0.6) / (1 - 0.6) = 0.5, the same as tackle's 0.5
    draws = Counter(
        sample_moves(dist, random.Random(s), chosen=(), slots=1,
                     reveal_rates={"protect": 0.6})[0]
        for s in range(4000)
    )
    assert 0.45 < draws["protect"] / 4000 < 0.55


def _evidence():
    return {
        "drake": SpeciesEvidence(
            moves=Counter({"tackle": 3}),
            abilities=Counter({"runaway": 3}),
            items=Counter({"sitrusberry": 3}),
            observed_sets=[("tackle",)],
        )
    }


def test_build_set_without_usage_is_unchanged():
    text = build_set("drake", _evidence(), random.Random(0))
    assert "@ sitrusberry" in text
    assert "EVs: 11 HP / 11 Atk / 11 Def / 11 SpA / 11 SpD / 11 Spe" in text
    assert "Serious Nature" in text


def test_build_set_with_usage_draws_the_item_nature_and_spread():
    usage = {
        "drake": SetDistribution(
            "drake", "smogon",
            items=Counter({"lifeorb": 1}),
            natures=Counter({"Jolly": 1}),
            spreads=Counter({("Jolly", (2, 32, 0, 0, 0, 32)): 1}),
        )
    }
    text = build_set("drake", _evidence(), random.Random(0), usage=usage)
    assert "@ lifeorb" in text
    assert "EVs: 2 HP / 32 Atk / 0 Def / 0 SpA / 0 SpD / 32 Spe" in text
    assert "Jolly Nature" in text


def test_build_set_with_a_nature_only_distribution_keeps_the_even_points():
    usage = {"drake": SetDistribution("drake", "open-sheets",
                                      items=Counter({"lifeorb": 1}),
                                      natures=Counter({"Adamant": 1}))}
    text = build_set("drake", _evidence(), random.Random(0), usage=usage)
    assert "Adamant Nature" in text
    assert "EVs: 11 HP / 11 Atk / 11 Def / 11 SpA / 11 SpD / 11 Spe" in text


def test_a_species_without_usage_falls_back_to_the_old_behaviour():
    text = build_set("drake", _evidence(), random.Random(0), usage={"other": _dist(lifeorb=1)})
    assert "@ sitrusberry" in text and "Serious Nature" in text


def _set_moves(text):
    return {line[2:] for line in text.splitlines() if line.startswith("- ")}


def _move_evidence(observed_sets, moves):
    return {
        "drake": SpeciesEvidence(
            moves=Counter(moves), abilities=Counter({"runaway": 1}),
            observed_sets=list(observed_sets),
        )
    }


MOVE_USAGE = {
    "drake": SetDistribution(
        "drake", "smogon", sets=2,
        moves=Counter({"tackle": 2, "ember": 1, "roar": 1, "leer": 1, "bite": 1}),
    )
}


def test_without_a_move_fill_usage_leaves_the_moves_alone():
    """0057's pool must rebuild byte for byte: the default draws nothing extra."""
    evidence = _move_evidence([("tackle",)], {"tackle": 3, "growl": 2})
    plain = build_set("drake", evidence, random.Random(0))
    with_usage = build_set("drake", evidence, random.Random(0), usage=MOVE_USAGE)
    assert _set_moves(plain) == _set_moves(with_usage) == {"tackle", "growl"}


def test_a_plain_fill_draws_the_empty_slots_from_usage():
    evidence = _move_evidence([("tackle",)], {"tackle": 3, "growl": 2})
    text = build_set("drake", evidence, random.Random(0), usage=MOVE_USAGE, move_fill="plain")
    moves = _set_moves(text)
    assert "tackle" in moves and "growl" not in moves and len(moves) == 4


def test_the_corrected_fill_lands_on_the_carry_rate_where_plain_overshoots():
    """Ember is carried by half of real sets and revealed in half of replays.

    Plain fill adds it again to sets that did not reveal it and ends up on
    about 88% of sets; corrected fill ends up on about 50%, the truth.
    """
    evidence = _move_evidence([("tackle", "ember"), ("tackle",)], {"tackle": 2, "ember": 1})
    usage = {
        "drake": SetDistribution(
            "drake", "smogon", sets=2,
            moves=Counter({"tackle": 2, "ember": 1, "roar": 1, "leer": 1, "bite": 1}),
        )
    }

    def ember_share(fill):
        sets = [
            build_set("drake", evidence, random.Random(s), usage=usage, move_fill=fill)
            for s in range(400)
        ]
        return sum("ember" in _set_moves(t) for t in sets) / len(sets)

    assert ember_share("plain") > 0.80
    assert 0.40 < ember_share("corrected") < 0.60


def test_what_the_draw_cannot_fill_falls_back_to_common_moves():
    evidence = _move_evidence([("tackle",)], {"tackle": 3, "growl": 2})
    usage = {"drake": SetDistribution("drake", "smogon", sets=1,
                                      moves=Counter({"tackle": 1, "ember": 1}))}
    text = build_set("drake", evidence, random.Random(0), usage=usage, move_fill="plain")
    assert _set_moves(text) == {"tackle", "ember", "growl"}


def test_an_unknown_move_fill_is_refused():
    with pytest.raises(ValueError):
        build_set("drake", _evidence(), random.Random(0), move_fill="mode")
