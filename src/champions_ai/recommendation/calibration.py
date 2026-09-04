"""What a gap in the agent's score is actually worth, in games.

The recommender has always shown a confidence: a share of a softmax over
scores, with a temperature of 12.0 that nobody ever swept. `PROJECT_PLAN.md`
was explicit that it is not a win probability and that a calibrated number
"comes from Milestone 7" -- and Milestone 7 was then measured and closed (0035,
0037), so on the plan's own terms the honest number was never going to arrive.

It arrived from somewhere else. 0041 rolled out 1,633 candidate actions at 582
real decision points and found that the *magnitude* of a score gap predicts the
real difference in win rate, not merely its sign:

```
  score gap from the top choice     held-out mean regret
    under 60                                -0.7%
    60 to 250                               -4.7%
    250 and above                          -10.2%
```

Held out by battle over eight random splits, the three bands came out
**correctly ordered on all eight**, with non-overlapping ranges between the
first and last. That is coarse, and it is deliberately reported as coarse: the
deciles between those bands are noise at this sample size, so this offers three
bands rather than a curve it cannot support.

**Two limits, both stated on screen rather than buried.**

The measurement is self-play. Both sides are this agent, so the number is what
a choice costs *against an opponent like us*, and 0026's caution applies to any
mechanic we systematically under-use.

And 0041 varied exactly one slot at a time, while the recommender ranks whole
turns. That matters less than it sounds: measured over 1,313 shortlist entries,
**94.2% differ from the top choice in a single slot**. The remaining 5.8% are
an extrapolation, and `cost_of_gap` says so by refusing to answer for them.
"""

from dataclasses import dataclass

# (upper bound on the score gap, label, win-rate points behind the top choice)
#
# The points are the held-out means from 0041, rounded to the precision the
# measurement supports. Reporting -4.7 would claim a tenth of a point from a
# number whose spread across splits was -6.6 to -2.8.
BANDS: tuple[tuple[float, str, int], ...] = (
    (60.0, "close", 1),
    (250.0, "behind", 5),
    (float("inf"), "well behind", 10),
)


@dataclass(frozen=True)
class Cost:
    """What choosing this instead of the top recommendation looks like to cost."""

    band: str
    points: int

    def __str__(self) -> str:
        if self.points <= 1:
            return "about level with the top choice"
        return f"about {self.points} points behind"


def cost_of_gap(gap: float, *, slots_differing: int = 1) -> Cost | None:
    """What a score gap is worth, or None when it is outside what was measured.

    `slots_differing` is how many slots this action changes relative to the top
    choice. 0041 measured one at a time, so a two-slot difference is a sum of
    two effects nobody has checked adds up, and this returns None rather than
    guessing. It is 5.8% of shortlist entries in practice.

    A negative gap means the caller has passed something the agent ranked
    *above* its own pick, which the joint scorer can produce -- a slot action
    can score higher on its own while the pair scores worse. Also unmeasured,
    also None.
    """
    if slots_differing != 1 or gap < 0:
        return None
    for upper, label, points in BANDS:
        if gap < upper:
            return Cost(band=label, points=points)
    return None  # unreachable: the last band is unbounded
