"""How long a Pokemon has left, and what that makes a stat boost worth.

Setting up trades this turn's attack for bigger attacks later, so what it is
worth depends on how many later turns there are. The agent priced a stage at a
flat 0.12 health bars (`STAT_STAGE_VALUE`), which makes Swords Dance worth 24
and therefore worth using only when the best attack available does under 24%
of a health bar. That rule turns on how *hard we hit*, when the real one turns
on how *long we last*.

Writing the trade out: attacking every turn deals `f * T`, while setting up
first deals `m * f * (T - 1)`, where `m` is the multiplier the stages buy.
Setting up wins when

    m * f * (T - 1)  >  f * T        <=>        T  >  m / (m - 1)

and the `f` cancels entirely. A +2 boost (m = 2) pays off from a tenure just
over two turns, a +1 boost (m = 1.5) from just over three. Measured over
self-play, tenure exceeds two on 44.6% of turns, so this is a live fraction of
the game rather than an edge case.

Pricing the boost as the extra damage it buys -- `(m - 1) * f * (T - 1)` --
makes the agent's own argmax against an attack (which scores `f`) reproduce
that condition exactly, `f` cancelling as it should. That matters beyond
tidiness: experiment 0022 made the agent nine points worse by subtracting two
terms that were in different currencies, and this stays in the one currency
everything else here uses, a fraction of a health bar.

`T` is not observable, but it is predictable. `hp_fraction / incoming_threat`
-- turns until the worst expected hit finishes us -- correlates +0.57 with
actual tenure and rises monotonically across every decile. It is badly biased
low, because `_incoming_threat` takes the worst hit either opponent could land
and assumes a STAB attack from anything unrevealed, so it reads as though
almost everything dies next turn.

A least-squares fit over 2,574 observations from 300 self-play battles put the
correction at `T = 1.96 + 1.05 * raw`, residual sd 1.48 turns. **That fit is
not used**, despite being the best one available on average, because its
intercept hands 1.96 turns to a Pokemon with none: something at 10% health
facing a hit that takes 60% reads as a fine Swords Dance candidate. That is
the largest bucket in the data (n = 1,051, actual tenure 1.61) and the one
place the error cannot be recovered from -- the boost is bought and the
Pokemon faints holding it.

The form used instead is pinned where the answer is knowable:

    T = 1 + raw / 0.5

"you always get this turn, plus the raw estimate doubled, because the
worst-case hit only lands about half the time". It is worse in the middle of
the range (raw ~ 0.5 under-predicts by about a turn) and correct at the bottom,
which is the trade worth making. Under-predicting tenure buys *less* setup,
and after experiment 0022 -- where a mis-scaled term made the agent nine
points worse -- erring toward the current behaviour is the conservative
direction.

Checked against the buckets:

    raw     0.0   0.5   1.0   1.5   2.0   2.5
    actual  1.61  3.17  3.30  3.94  4.31  4.63
    used    1.00  2.00  3.00  4.00  5.00  6.00

The residual is large either way -- this ranks far better than it measures --
so the ceiling and floor matter as much as the slope.
"""

from champions_ai.domain.boosts import MAX_STAGE, MIN_STAGE

# The turn you are having now, which nothing can take away. Pinning the
# intercept here rather than at the fitted 1.96 is the whole safety property:
# a Pokemon with no turns left is priced as having none.
TENURE_BASE = 1.0

# The worst-case hit lands about half the time, so the raw ratio understates
# tenure by roughly this factor.
THREAT_REALISATION = 0.5

# The predictor is a ratio and runs away at both ends: a Pokemon at full HP
# against something that can barely scratch it reads as immortal. Clamped to
# the range actually observed, so one wild estimate cannot buy a boost.
TENURE_FLOOR = 1.0
TENURE_CEILING = 6.0

# When nothing on the field can threaten us at all the ratio is undefined
# rather than infinite. Measured separately: those turns ran 3.75 long.
TENURE_UNTHREATENED = 3.75

# Stages this module prices. Attack and Special Attack multiply damage dealt,
# which is what the arithmetic above describes. Speed changes turn order and
# the defensive stats change damage taken -- both real, both a different
# calculation -- so they keep the flat rate for now.
OFFENSIVE_STATS = frozenset({"atk", "spa"})


def stage_factor(stage: int) -> float:
    """The engine's stat multiplier at a given boost stage."""
    stage = max(MIN_STAGE, min(MAX_STAGE, stage))
    if stage >= 0:
        return (2.0 + stage) / 2.0
    return 2.0 / (2.0 - stage)


def stage_multiplier(before: int, after: int) -> float:
    """How much moving from `before` to `after` multiplies the stat by.

    Relative rather than absolute on purpose: a Swords Dance at +4 raises
    Attack by a third, not by double, and pricing it as a double is how an
    agent talks itself into a fourth one.
    """
    return stage_factor(after) / stage_factor(before)


def expected_tenure(hp_fraction: float, incoming_fraction: float) -> float:
    """Turns this Pokemon can expect, counting the current one."""
    if incoming_fraction <= 1e-6:
        return TENURE_UNTHREATENED
    raw = max(0.0, hp_fraction) / incoming_fraction
    return max(
        TENURE_FLOOR,
        min(TENURE_CEILING, TENURE_BASE + raw / THREAT_REALISATION),
    )


def offensive_boost_value(
    multiplier: float,
    damage_fraction: float,
    tenure: float,
    target_fraction: float = 1.0,
) -> float:
    """Health bars a boost buys: larger attacks, for the turns that remain.

    Zero at a tenure of one, which is the point -- a boost on the turn you
    faint buys nothing, and the flat price said otherwise.

    Also zero when the attack already knocks the target out. Damage stops
    paying at the knockout threshold, and a boost's entire product is a bigger
    number per hit, so that ceiling is exactly where its value goes. Pricing
    the gain as `(m - 1) * f` without it made the agent turn down a guaranteed
    knockout on 14.5% of the turns one was available -- it had been offered a
    kill and preferred to make its next kill larger. Measured, and it cost 4.6
    points of win rate.

        useful gain per turn  =  min(m * f, hp)  -  min(f, hp)

    which is the full `(m - 1) * f` while the target survives the hit, and
    nothing once it does not.
    """
    damage = max(0.0, damage_fraction)
    target = max(0.0, target_fraction)
    gain = min(multiplier * damage, target) - min(damage, target)
    return gain * max(0.0, tenure - 1.0)
