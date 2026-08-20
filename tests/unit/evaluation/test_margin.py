"""How decisively a battle ended.

Win/loss carries one bit per battle, which has proved too coarse to measure
anything this project does -- every change since the original heuristic came
out "not significant" against it. These tests pin the properties that make the
margin a more sensitive instrument on the same battles.
"""

import pytest

from champions_ai.domain import BattlePokemon, PokemonSet, Side
from champions_ai.evaluation.margin import (
    BattleMargin,
    margin_from_sides,
    measure_side,
    relative_power,
    summarise,
)


def _mon(species, current, maximum=100):
    return BattlePokemon(
        pokemon_set=PokemonSet(species=species, level=50, ability="x", moves=("tackle",)),
        current_hp=current, max_hp=maximum,
    )


def _side(*hps):
    return Side(
        team=tuple(_mon(f"mon{i}", hp) for i, hp in enumerate(hps)),
        active_slots=(0, None),
    )


def test_a_side_reports_survivors_and_their_remaining_hp():
    alive, hp = measure_side(_side(100, 50, 0, 0))
    assert alive == 2
    assert hp == pytest.approx(1.5)


def test_a_sweep_and_a_narrow_win_are_different_evidence():
    """The whole point. Both are one win; they are not the same result."""
    sweep = margin_from_sides(_side(100, 100, 100, 100), _side(0, 0, 0, 0))
    narrow = margin_from_sides(_side(100, 0, 0, 0), _side(0, 0, 0, 1))
    assert sweep.pokemon_margin == 4
    assert narrow.pokemon_margin == 0
    assert sweep.hp_margin > narrow.hp_margin


def test_the_margin_is_signed_from_the_first_side(): 
    losing = margin_from_sides(_side(0, 0, 0, 0), _side(100, 100, 0, 0))
    assert losing.pokemon_margin == -2
    assert losing.hp_margin < 0


def test_chip_damage_shows_in_hp_but_not_in_pokemon_count():
    """Two measures on purpose: one robust and coarse, one fine and noisier."""
    healthy = margin_from_sides(_side(100, 100), _side(100, 100))
    chipped = margin_from_sides(_side(100, 100), _side(100, 20))
    assert healthy.pokemon_margin == chipped.pokemon_margin == 0
    assert chipped.hp_margin > healthy.hp_margin


def test_an_even_result_is_not_significant():
    summary = summarise("even", [1, -1, 1, -1, 1, -1] * 20)
    assert summary.mean == pytest.approx(0.0)
    assert not summary.is_significant


def test_a_consistent_edge_is_significant():
    summary = summarise("ahead", [1, 2, 1, 1, 2, 1] * 20)
    assert summary.mean > 0
    assert summary.is_significant
    low, _ = summary.interval
    assert low > 0


def test_a_single_battle_supports_no_claim():
    """One result has no spread, so it must not read as certainty."""
    summary = summarise("one", [4.0])
    assert summary.standard_error == 0.0
    assert not summary.is_significant


def test_no_battles_reports_nothing_rather_than_dividing_by_zero():
    summary = summarise("none", [])
    assert summary.mean == 0.0
    assert not summary.is_significant


def test_the_margin_needs_fewer_battles_than_win_loss():
    """The claim the module exists to make, stated as a test.

    A run split near evenly on wins but consistently decisive when won carries
    far more evidence per battle in the margin than in the bit.
    """
    margins = ([3, 3, 3, -1, -1] * 20)
    wins = [1 if m > 0 else 0 for m in margins]
    assert relative_power(margins, wins) > 1.0


def test_relative_power_compares_signal_to_noise_not_raw_error():
    """A margin runs -4..+4 and a win 0..1, so their standard errors are in
    different units; comparing them directly would be meaningless."""
    margins = [1, -1] * 50           # no signal at all
    wins = [1, 0] * 50               # also no signal
    assert relative_power(margins, wins) == pytest.approx(1.0, abs=0.5)


def test_a_perfectly_consistent_margin_is_infinitely_cheaper():
    """Zero variance means no sample size of coin flips would match it."""
    assert relative_power([2.0] * 50, [1, 0] * 25) == float("inf")


def test_margin_defaults_are_harmless_when_a_battle_had_no_final_state():
    empty = BattleMargin(survivors_a=0, survivors_b=0, hp_a=0.0, hp_b=0.0, team_size=4)
    assert empty.pokemon_margin == 0
    assert empty.hp_margin == 0.0


def test_relative_power_can_report_the_margin_being_worse():
    """It is, on this project's real comparisons -- 0.4x to 0.6x.

    The module was built expecting the opposite. Keeping a test for the
    unfavourable direction stops the docstring drifting back to the claim the
    measurement refuted.
    """
    # Wide spread, small mean: exactly the shape a Pokemon margin takes.
    margins = [4, -4, 3, -3, 4, -3, 3, -4] * 20
    wins = [1, 0, 1, 0, 1, 0, 1, 1] * 20      # a clear 62.5% edge
    assert relative_power(margins, wins) < 1.0
