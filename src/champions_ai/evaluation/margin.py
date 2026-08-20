"""How decisively a battle ended, not merely who won.

Built on the hypothesis that win/loss carries **one bit per battle** and is
therefore too coarse to measure anything this project does -- every change since
the original heuristic has come out "not significant" against it.

**That hypothesis was measured and is wrong.** On real comparisons the margin is
*less* statistically powerful than the win rate, not more:

    boost-aware vs boost-blind, 800 battles
      win rate 53.0% (not significant) | margin +0.046 (not significant)
      relative_power 0.4x -- the margin needs 2.5x the battles

    heuristic vs random, 300 battles
      win rate 97.7% (significant) | margin +2.183 (significant)
      relative_power 0.6x

Its variance grows faster than its signal. A battle ending 4-0, 4-3 or 0-4
spreads the margin across a wide range, while a win is bounded and its variance
caps at 0.25. The extra information does not pay for the extra noise.

So this is kept for two narrower reasons, and **not** as a more sensitive test:

- **Effect size.** "The heuristic beats Random by 2.18 Pokemon on average" says
  something "97.7%" does not, and a saturated win rate hides how large the gap
  actually is.
- **Independent confirmation.** Two measures agreeing that a change did nothing
  is stronger evidence than one measure failing to see it. That is what settled
  the stat-stage change as a genuine wash rather than an undetected gain.

`relative_power` exists so the choice is checked per comparison rather than
assumed. Use the win rate to decide significance unless it says otherwise.

Two measures, deliberately kept apart:

- **`pokemon_margin`** -- survivors on our side minus theirs, -4 to +4. Coarse
  but robust, and it is what a player would actually call the score.
- **`hp_margin`** -- total remaining HP as a fraction of a full team, so chip
  damage counts. Finer, and correspondingly noisier around the edges where a
  Pokemon is alive at 1 HP.

Both are read from **both players' own sides**, never from either player's
observation of the other: an `ObservedSide` shows only what was revealed, so
counting an opponent's survivors from it would silently miss anything they
never sent out.
"""

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

from champions_ai.domain import Side

# 95% two-sided normal quantile, matching the Wilson interval used for rates.
Z_95 = 1.959963985


@dataclass(frozen=True)
class BattleMargin:
    """How one battle ended, from the first agent's point of view."""

    survivors_a: int
    survivors_b: int
    hp_a: float
    hp_b: float
    team_size: int

    @property
    def pokemon_margin(self) -> int:
        return self.survivors_a - self.survivors_b

    @property
    def hp_margin(self) -> float:
        """Difference in surviving HP, as a fraction of one full team."""
        return (self.hp_a - self.hp_b) / max(1, self.team_size)


def measure_side(side: Side) -> tuple[int, float]:
    """(survivors, total remaining HP as a fraction of the team) for one side."""
    alive = sum(1 for mon in side.team if not mon.fainted)
    hp = sum(mon.hp_fraction for mon in side.team if not mon.fainted)
    return alive, hp


def margin_from_sides(own: Side, theirs: Side) -> BattleMargin:
    """Both sides must be a player's *own* side, not an observation of them."""
    survivors_a, hp_a = measure_side(own)
    survivors_b, hp_b = measure_side(theirs)
    return BattleMargin(
        survivors_a=survivors_a,
        survivors_b=survivors_b,
        hp_a=hp_a,
        hp_b=hp_b,
        team_size=max(len(own.team), len(theirs.team)),
    )


@dataclass(frozen=True)
class MarginSummary:
    """Mean margin with a confidence interval, for a set of battles."""

    label: str
    values: tuple[float, ...]

    @property
    def mean(self) -> float:
        return statistics.fmean(self.values) if self.values else 0.0

    @property
    def standard_error(self) -> float:
        if len(self.values) < 2:
            return 0.0
        return statistics.stdev(self.values) / math.sqrt(len(self.values))

    @property
    def interval(self) -> tuple[float, float]:
        spread = Z_95 * self.standard_error
        return (self.mean - spread, self.mean + spread)

    @property
    def is_significant(self) -> bool:
        """Whether the interval excludes zero -- an even result.

        Requires at least two battles. A single result has zero spread, and
        reading that as a zero-width interval would report one lucky 4-0 as
        certainty rather than as no information.

        Conservative in the same way the win-rate test is: an interval
        containing zero means the run supports no claim either way, not that
        the two agents are equal.
        """
        if len(self.values) < 2:
            return False
        low, high = self.interval
        return low > 0.0 or high < 0.0

    def summary(self) -> str:
        low, high = self.interval
        verdict = "significant" if self.is_significant else "not significant"
        return (
            f"{self.label}: {self.mean:+.3f} "
            f"(95% CI {low:+.3f} to {high:+.3f}, {verdict}) over {len(self.values)} battles"
        )


def summarise(label: str, values: Sequence[float]) -> MarginSummary:
    return MarginSummary(label=label, values=tuple(values))


def relative_power(
    values: Sequence[float], wins: Sequence[float], *, baseline: float = 0.5
) -> float:
    """How many win/loss battles it takes to match one margin battle's evidence.

    The claim the module exists to make, as a number. Compares
    **signal-to-noise**, not raw standard error: a margin runs from -4 to +4 and
    a win from 0 to 1, so their standard errors are in different units and
    comparing them directly would be meaningless. Each measure's t-statistic is
    taken against its own null -- zero for the margin, a coin flip for the win
    rate -- and since required sample size scales with 1/t squared, the ratio of
    squared t-statistics is the ratio of battles needed.

    Returns 4.0 to mean "the margin extracts in one battle what win/loss needs
    four for". Infinite when the margin is perfectly consistent, since no number
    of coin flips reaches certainty.
    """
    margin = summarise("", values)
    binary = summarise("", [float(w) for w in wins])
    if not margin.values or not binary.values:
        return 1.0

    if margin.standard_error <= 0.0:
        return 1.0 if abs(margin.mean) <= 0.0 else float("inf")
    if binary.standard_error <= 0.0:
        # An unbroken run of wins is already maximally certain by this measure.
        return 1.0

    t_margin = abs(margin.mean) / margin.standard_error
    t_binary = abs(binary.mean - baseline) / binary.standard_error
    if t_binary <= 0.0:
        return float("inf") if t_margin > 0 else 1.0
    return (t_margin / t_binary) ** 2
