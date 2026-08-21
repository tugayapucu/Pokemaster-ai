"""Crediting investment to the stat a move actually uses.

Fitted against 5,054 real attacks rather than chosen. A uniform spread
under-predicts damage by 10%; sweeping the attacker's investment removes the
bias, crossing 1.00x at about 28 points and peaking on within-ten-points
accuracy at 24.

The justification is evidential: a Pokemon *using* a physical move is far more
likely to have invested in Attack than one drawn at random.
"""


from champions_ai.dex import BaseStats
from champions_ai.domain import REGULATION_M_B
from champions_ai.mechanics import ASSUMED_ATTACKING_POINTS, assumed_stats, estimate_stats

BASE = BaseStats(
    hp=100, attack=120, defense=80, special_attack=60, special_defense=80, speed=100
)


def test_no_attacking_stat_is_the_plain_uniform_estimate():
    assert assumed_stats(BASE, 11) == estimate_stats(BASE, 11)
    assert assumed_stats(BASE, 11, attacking=None) == estimate_stats(BASE, 11)


def test_the_attacking_stat_is_credited_with_more_investment():
    uniform = estimate_stats(BASE, 11)
    physical = assumed_stats(BASE, 11, attacking="atk")
    assert physical["atk"] > uniform["atk"]


def test_only_the_named_stat_moves():
    """Using a physical move says nothing about Special Attack or bulk."""
    uniform = estimate_stats(BASE, 11)
    physical = assumed_stats(BASE, 11, attacking="atk")
    for key in ("hp", "def", "spa", "spd", "spe"):
        assert physical[key] == uniform[key]


def test_a_special_move_credits_special_attack_instead():
    special = assumed_stats(BASE, 11, attacking="spa")
    uniform = estimate_stats(BASE, 11)
    assert special["spa"] > uniform["spa"]
    assert special["atk"] == uniform["atk"]


def test_the_investment_is_within_the_per_stat_cap():
    """Whatever it is fitted to, it must stay a legal allocation for one stat."""
    assert ASSUMED_ATTACKING_POINTS <= REGULATION_M_B.max_stat_points_per_stat


def test_the_model_is_deliberately_asymmetric_and_not_a_legal_spread():
    """Pinned so nobody 'fixes' it into consistency without reading why.

    The attacking stat gets the credit and the defensive stats stay uniform,
    which exceeds the 66-point budget if read as one Pokemon's spread. It is
    not one: it is a predictor over two populations, since whoever is attacking
    is likely built to attack while whoever is being attacked is a mixed bag.
    A legal concentrated spread on both sides was tried and fitted worse.
    """
    credited = assumed_stats(BASE, 11, attacking="atk")
    implied = ASSUMED_ATTACKING_POINTS + 11 * 5
    assert implied > REGULATION_M_B.max_total_stat_points
    assert credited["def"] == estimate_stats(BASE, 11)["def"]


def test_an_unknown_stat_key_is_ignored_rather_than_crashing():
    """HP uses a different formula and no move attacks with it."""
    assert assumed_stats(BASE, 11, attacking="hp") == estimate_stats(BASE, 11)
    assert assumed_stats(BASE, 11, attacking="nonsense") == estimate_stats(BASE, 11)


def test_defense_can_be_credited_for_a_move_that_attacks_with_it():
    """Body Press swings with Defense, so that is the stat the user built.

    The constant was fitted against Attack and Special Attack, but the
    argument behind it -- carrying the move is evidence about the spread --
    does not care which stat the move happens to draw on.
    """
    credited = assumed_stats(BASE, 11, attacking="def")
    assert credited["def"] > estimate_stats(BASE, 11)["def"]
    assert credited["atk"] == estimate_stats(BASE, 11)["atk"]


def test_more_investment_means_a_higher_stat():
    low = assumed_stats(BASE, 11, attacking="atk", attacking_points=0)
    high = assumed_stats(BASE, 11, attacking="atk", attacking_points=32)
    assert high["atk"] > low["atk"]
