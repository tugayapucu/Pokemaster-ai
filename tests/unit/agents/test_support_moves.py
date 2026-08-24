"""Moves the engine cannot describe, priced from state we do hold.

Fifty-four status moves carry their whole effect in an `onHit` callback, so
the bridge dumps nothing about them. Many are still exactly computable: a
Belly Drum is six stages against half a health bar, a Pain Split is arithmetic
on two HP totals, a Haze is the difference between the stages on each side.

Modelled regardless of how often they appear in the corpus. Rarity in 500
games is a fact about that sample, not about the game.
"""

import pytest

from champions_ai.agents.currency import (
    STAT_STAGE_VALUE,
    STAT_STAGE_WEIGHT,
    SUSTAIN_WEIGHT,
)
from champions_ai.agents.support import score_support_move
from champions_ai.dex import MoveInfo
from champions_ai.domain import BattlePokemon, Boosts, ObservedPokemon, PokemonSet

STAGE = STAT_STAGE_VALUE * STAT_STAGE_WEIGHT


def _move(move_id, target="self"):
    return MoveInfo(
        move_id=move_id, name=move_id, type="Normal", category="Status",
        base_power=0, accuracy=100, priority=0, target=target,
    )


def _mon(hp=200, max_hp=200, boosts=None, status=None):
    return BattlePokemon(
        pokemon_set=PokemonSet(species="Garchomp", level=50, ability="x", moves=("rest",)),
        current_hp=hp, max_hp=max_hp, status=status,
        computed_stats={"atk": 150, "def": 100, "spa": 150, "spd": 100, "spe": 100},
        boosts=boosts or Boosts(),
    )


def _foe(hp_percent=100, boosts=None):
    return ObservedPokemon(
        species="Charizard", level=50, hp_percent=hp_percent, fainted=False,
        boosts=boosts or Boosts(),
    )


STATS = {"hp": 200, "atk": 140, "def": 100, "spa": 120, "spd": 100, "spe": 110}


def _score(move_id, **kwargs):
    kwargs.setdefault("attacker", _mon())
    return score_support_move(_move(move_id), **kwargs)


# ------------------------------------------------------------------ healing


@pytest.mark.parametrize("move_id", ["moonlight", "morningsun", "synthesis"])
def test_the_weather_heals_depend_on_the_weather(move_id):
    """Two thirds in sun, a quarter in anything else, half on a clear field."""
    sun, _ = _score(move_id, attacker=_mon(hp=20), weather="sunnyday")
    clear, _ = _score(move_id, attacker=_mon(hp=20), weather=None)
    sand, _ = _score(move_id, attacker=_mon(hp=20), weather="sandstorm")
    assert sun > clear > sand > 0


def test_healing_is_capped_by_what_is_missing():
    hurt, _ = _score("synthesis", attacker=_mon(hp=100))
    scratched, _ = _score("synthesis", attacker=_mon(hp=190))
    full, _ = _score("synthesis", attacker=_mon(hp=200))
    assert hurt > scratched > 0
    assert full == 0.0


def test_rest_costs_two_turns_of_about_five():
    """It scores negative almost everywhere, which is the right answer for this
    format rather than a bug, but it is still ordered by how much it restores.
    """
    nearly_dead, _ = _score("rest", attacker=_mon(hp=20))
    scratched, _ = _score("rest", attacker=_mon(hp=190))
    assert nearly_dead > scratched
    assert scratched < 0


def test_pain_split_is_worth_nothing_when_we_are_the_healthy_one():
    taking, _ = _score("painsplit", attacker=_mon(hp=40),
                       observed=_foe(100), observed_stats=STATS)
    giving, _ = _score("painsplit", attacker=_mon(hp=200),
                       observed=_foe(20), observed_stats=STATS)
    assert taking > 0
    assert giving == 0.0


def test_strength_sap_heals_by_their_attack_and_drops_it():
    value, why = _score("strengthsap", attacker=_mon(hp=40),
                        observed=_foe(), observed_stats=STATS)
    assert value > 0
    assert any("Attack" in reason for reason in why)


def test_heal_pulse_needs_an_ally_to_heal():
    with_ally, _ = _score("healpulse", ally=_mon(hp=60))
    healthy_ally, _ = _score("healpulse", ally=_mon(hp=200))
    alone, _ = _score("healpulse", ally=None)
    assert with_ally > 0
    assert healthy_ally == 0.0
    assert alone == 0.0


# --------------------------------------------------------------- stat stages


def test_belly_drum_is_six_stages_against_half_a_health_bar():
    value, _ = _score("bellydrum", attacker=_mon(hp=200))
    assert value == pytest.approx(6 * STAGE - 0.5 * SUSTAIN_WEIGHT)


def test_belly_drum_fails_below_half_health():
    value, why = _score("bellydrum", attacker=_mon(hp=80))
    assert value == 0.0
    assert "fail" in why[0]


def test_belly_drum_fails_at_maximum_attack():
    value, _ = _score("bellydrum", attacker=_mon(boosts=Boosts(attack=6)))
    assert value == 0.0


def test_haze_is_worth_the_difference_between_the_two_sides():
    theirs, _ = _score("haze", observed=_foe(boosts=Boosts(attack=2, speed=2)))
    assert theirs == pytest.approx(4 * STAGE)


def test_haze_is_a_mistake_when_we_are_the_boosted_one():
    ours, _ = _score("haze", attacker=_mon(boosts=Boosts(attack=2)), observed=_foe())
    assert ours == pytest.approx(-2 * STAGE)


def test_haze_with_nothing_to_clear_is_worth_nothing():
    value, why = _score("haze", observed=_foe())
    assert value == 0.0
    assert "no stat changes" in why[0]


def test_psych_up_only_copies_what_is_better_than_ours():
    better, _ = _score("psychup", observed=_foe(boosts=Boosts(attack=4)))
    worse, _ = _score("psychup", attacker=_mon(boosts=Boosts(attack=4)),
                      observed=_foe())
    assert better == pytest.approx(4 * STAGE)
    assert worse == 0.0


def test_topsy_turvy_is_worth_double_their_boosts():
    """Turning +3 into -3 is a six-stage swing."""
    value, _ = _score("topsyturvy", observed=_foe(boosts=Boosts(attack=3)))
    assert value == pytest.approx(6 * STAGE)


def test_topsy_turvy_would_help_a_debuffed_target():
    value, _ = _score("topsyturvy", observed=_foe(boosts=Boosts(attack=-3)))
    assert value == 0.0


def test_parting_shot_drops_both_offences():
    fresh, _ = _score("partingshot", observed=_foe())
    floored, _ = _score(
        "partingshot", observed=_foe(boosts=Boosts(attack=-6, special_attack=-6))
    )
    assert fresh == pytest.approx(2 * STAGE)
    assert floored == 0.0


def test_parting_shot_is_a_pivot_as_well_as_a_debuff():
    """Pricing only the debuff made it worth less than an unknown support move
    and cost six labels of agreement. Getting something weakened out of danger
    is worth what it is worth anywhere else."""
    healthy, _ = _score("partingshot", attacker=_mon(hp=200), observed=_foe())
    weakened, _ = _score("partingshot", attacker=_mon(hp=40), observed=_foe())
    assert weakened > healthy


def test_perish_song_is_not_priced_at_all():
    """It cuts both ways and its worth depends on trapping and on who is
    ahead, neither of which is modelled. A flat guess scored below the
    unknown-support fallback and lost agreement, so this says so instead."""
    assert _score("perishsong", observed=_foe()) is None


def test_a_stage_swap_only_pays_when_theirs_are_better():
    good, _ = _score("powerswap", observed=_foe(boosts=Boosts(attack=3)))
    bad, _ = _score("powerswap", attacker=_mon(boosts=Boosts(attack=3)),
                    observed=_foe())
    assert good == pytest.approx(3 * STAGE)
    assert bad == 0.0


def test_acupressure_fails_only_when_everything_is_maxed():
    maxed = Boosts(attack=6, defense=6, special_attack=6, special_defense=6,
                   speed=6, accuracy=6, evasion=6)
    value, _ = _score("acupressure", attacker=_mon(boosts=maxed))
    assert value == 0.0
    assert _score("acupressure")[0] == pytest.approx(2 * STAGE)


# --------------------------------------------------------- clearing the field


def test_heal_bell_is_worth_the_statuses_it_cures():
    value, _ = _score("healbell", team_statuses=("brn", "par", None))
    assert value > 0
    assert _score("healbell", team_statuses=(None, None))[0] == 0.0


def test_defog_is_worth_what_it_clears():
    value, _ = _score("defog", own_side_conditions=("stealthrock", "spikes"))
    assert value == pytest.approx(2 * STAGE)
    assert _score("defog")[0] == 0.0


def test_phazing_undoes_what_they_set_up():
    sweeper, _ = _score("whirlwind", observed=_foe(boosts=Boosts(attack=2, speed=2)))
    fresh, _ = _score("whirlwind", observed=_foe())
    assert sweeper == pytest.approx(4 * STAGE)
    assert fresh == 0.0


# --------------------------------------------------------------- held items


def _item(item_id, is_berry=False, mega_stone=None):
    from champions_ai.dex import ItemInfo
    return ItemInfo(item_id=item_id, name=item_id, is_berry=is_berry,
                    mega_stone=mega_stone)


def test_stuff_cheeks_needs_a_berry():
    """The engine refuses the move outright without one, so this is a
    legality fact rather than a valuation."""
    with_berry, _ = _score("stuffcheeks", attacker_item=_item("sitrusberry", is_berry=True))
    with_orb, _ = _score("stuffcheeks", attacker_item=_item("lifeorb"))
    empty, _ = _score("stuffcheeks", attacker_item=None)
    assert with_berry == pytest.approx(2 * STAGE)
    assert with_orb == 0.0
    assert empty == 0.0


def test_stuff_cheeks_is_worth_less_at_a_high_defence():
    boosted, _ = _score("stuffcheeks", attacker=_mon(boosts=Boosts(defense=5)),
                        attacker_item=_item("sitrusberry", is_berry=True))
    assert boosted == pytest.approx(1 * STAGE)


def test_corrosive_gas_is_worth_nothing_once_the_item_is_gone():
    live, _ = _score("corrosivegas", observed=_foe(), observed_may_hold_item=True)
    spent, _ = _score("corrosivegas", observed=_foe(), observed_may_hold_item=False)
    assert live > 0
    assert spent == 0.0


def test_a_swap_needs_to_know_what_they_are_holding():
    """The whole point of Trick is that theirs is better than ours, and their
    item is hidden until it fires -- so this is a case where guessing would be
    guessing about the more important half."""
    assert _score("trick", observed=_foe(), defender_item=None) is None
    known, _ = _score("trick", observed=_foe(), defender_item=_item("lifeorb"))
    assert known > 0


def test_recycle_knows_whether_there_is_anything_to_recover():
    """Not "cannot say": we watched the item go, so this is a definite
    statement either way."""
    something, _ = _score("recycle", consumed_item=_item("sitrusberry", is_berry=True))
    nothing, _ = _score("recycle", consumed_item=None)
    assert something > 0
    assert nothing == 0.0


# ----------------------------------------------------------- honestly unknown


@pytest.mark.parametrize("move_id", [
    "batonpass", "copycat", "sleeptalk", "transform", "instruct", "trick",
    "skillswap", "soak", "afteryou", "quash", "block", "spite",
])
def test_a_move_we_cannot_price_returns_none_rather_than_zero(move_id):
    """None means the effect depends on state nothing tracks, so the caller
    falls back to its unknown-support value. Being unable to price a move is
    not the same as the move being worthless.
    """
    assert _score(move_id, observed=_foe()) is None
