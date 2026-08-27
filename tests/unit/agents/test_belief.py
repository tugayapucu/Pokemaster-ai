"""Inferring the opponent's Stat Points from the damage they deal and take.

Stat Points are never published (ADR 0002), so the agent has always assumed 66
points shared evenly. Experiment 0018 measured what perfect knowledge would be
worth -- **+4.3 points of win rate, essentially all of it spreads** -- so this
infers spreads and nothing else.

The inversion is a binary search over `estimate_damage` rather than an algebraic
inverse, so there is one damage formula in the project instead of two that can
drift. These check it recovers a spread it was never told, from noiseless
damage: if it cannot do that it will certainly not manage it in a battle.
"""

import pytest

from champions_ai.agents.belief import (
    MAX_POINTS_PER_STAT,
    NEUTRAL_POINTS,
    TOTAL_POINTS,
    OpponentBelief,
    SpreadBelief,
    points_from_stat,
)
from champions_ai.dex import BaseStats, Dex, MoveInfo, SpeciesInfo, TypeChart
from champions_ai.mechanics.damage import estimate_damage
from champions_ai.mechanics.stats import hp_stat, other_stat

TYPES = ("Normal", "Fighting")

BRUISER = SpeciesInfo(
    species_id="bruiser", name="Bruiser", types=("Fighting",),
    base_stats=BaseStats(hp=90, attack=130, defense=80,
                         special_attack=65, special_defense=85, speed=55),
)
WALL = SpeciesInfo(
    species_id="wall", name="Wall", types=("Normal",),
    base_stats=BaseStats(hp=160, attack=110, defense=65,
                         special_attack=65, special_defense=110, speed=30),
)
TACKLE = MoveInfo(
    move_id="tackle", name="Tackle", type="Normal", category="Physical",
    base_power=80, accuracy=100, priority=0, target="normal",
)


@pytest.fixture
def dex() -> Dex:
    return Dex(
        species={s.species_id: s for s in (BRUISER, WALL)},
        moves={TACKLE.move_id: TACKLE},
        types=TYPES,
        type_chart=TypeChart(
            multipliers={a: dict.fromkeys(TYPES, 1.0) for a in TYPES}
        ),
    )


def _real_hit(dex, attack_points, defence_points):
    """What the hit truly does, from the same model the search inverts."""
    hp = hp_stat(WALL.base_stats.hp, NEUTRAL_POINTS)
    estimate = estimate_damage(
        dex, TACKLE,
        attacker=BRUISER,
        attack_stat=other_stat(BRUISER.base_stats.attack, attack_points),
        defender=WALL,
        defense_stat=other_stat(WALL.base_stats.defense, defence_points),
        defender_hp=hp, doubles=False,
    )
    return (estimate.minimum + estimate.maximum) / 2 / hp, hp


# --- the inversion --------------------------------------------------------


@pytest.mark.parametrize("truth", [0, 8, 16, 24, 32])
def test_a_defenders_investment_is_recovered_from_a_hit_we_landed(dex, truth):
    fraction, hp = _real_hit(dex, NEUTRAL_POINTS, truth)
    belief = OpponentBelief(dex)
    for _ in range(6):
        belief.note_hit_we_landed(
            move=TACKLE, attacker=BRUISER,
            attack_stat=other_stat(BRUISER.base_stats.attack, NEUTRAL_POINTS),
            defender=WALL, defender_max_hp=hp, fraction_lost=fraction,
            doubles=False,
        )
    assert abs(belief.of("Wall").points["def"] - truth) <= 3


@pytest.mark.parametrize("truth", [0, 8, 16, 24])
def test_an_attackers_investment_is_recovered_from_a_hit_we_took(dex, truth):
    fraction, hp = _real_hit(dex, truth, NEUTRAL_POINTS)
    belief = OpponentBelief(dex)
    for _ in range(6):
        belief.note_hit_we_took(
            move=TACKLE, attacker=BRUISER, defender=WALL,
            defence_stat=other_stat(WALL.base_stats.defense, NEUTRAL_POINTS),
            our_max_hp=hp, fraction_lost=fraction, doubles=False,
        )
    assert abs(belief.of("Bruiser").points["atk"] - truth) <= 3


def test_a_status_move_teaches_nothing(dex):
    """No damage, no equation."""
    protect = MoveInfo(
        move_id="protect", name="Protect", type="Normal", category="Status",
        base_power=0, accuracy=None, priority=4, target="self",
    )
    belief = OpponentBelief(dex)
    belief.note_hit_we_landed(
        move=protect, attacker=BRUISER, attack_stat=140,
        defender=WALL, defender_max_hp=200, fraction_lost=0.3, doubles=False,
    )
    assert belief.of("Wall").observations == {}


# --- the budget -----------------------------------------------------------


def test_the_belief_never_exceeds_the_regulation_budget():
    """66 points is the whole allowance, so raising one stat has to cost
    another. A spread that breaks the rules is not a spread."""
    belief = SpreadBelief()
    for key in ("atk", "spa", "spe"):
        belief.learn(key, MAX_POINTS_PER_STAT)
    assert sum(belief.points.values()) <= TOTAL_POINTS
    assert all(0 <= v <= MAX_POINTS_PER_STAT for v in belief.points.values())


def test_the_cost_falls_on_stats_nothing_has_told_us_about():
    """What we have seen is better evidence than the prior, so the rebalance
    spends the prior's points rather than the measured ones."""
    belief = SpreadBelief()
    belief.learn("atk", 32)
    belief.learn("spe", 32)
    assert belief.points["atk"] >= 30
    assert belief.points["spe"] >= 30


def test_the_estimate_is_the_mean_of_what_the_hits_implied():
    """Not a walk away from the prior. With one or two readings per stat an
    exponential average never travels far enough to beat the guess it started
    from -- measured at 16.0 -> 15.4 points of error before this changed, and
    16.0 -> 14.7 after."""
    belief = SpreadBelief()
    belief.learn("atk", 30)
    assert belief.points["atk"] == 30      # not 11 + 45% of the way
    belief.learn("atk", 20)
    assert belief.points["atk"] == 25      # the mean of 30 and 20


def test_points_invert_the_stat_formula():
    assert points_from_stat(110, other_stat(110, 32)) == 32
    assert points_from_stat(110, other_stat(110, 0)) == 0
    # Nothing illegal comes back out, whatever goes in.
    assert points_from_stat(110, 9999) == MAX_POINTS_PER_STAT
    assert points_from_stat(110, 0) == 0
