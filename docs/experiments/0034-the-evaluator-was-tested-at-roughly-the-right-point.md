# Experiment 0034 — The evaluator was tested at roughly the right point

**Date:** 2026-09-03
**Result: sweeping the scale of the evaluator's extra terms does not rescue them, because 0030 had already sampled near the peak.** The curve rises to a maximum around scale 1 — the setting 0030 used — and turns clearly negative above scale 2. The gain there is small and not stably estimated: two cross-validation runs over the same data give **+0.2pp** and **+1.00pp**. Unlike switching, where sweeping moved the answer from "harmful" to "shipped", here it only confirms the shape.

## Why it was worth sweeping

0032 found the switching question had been answered wrongly three times because everyone tested a single point on a monotone curve. 0030 tested the evaluator's extra terms at exactly one scale, and there was a specific reason to think that scale was wrong: the weights come from logistic regression, which minimises **log-loss**, while the evaluator is graded on **sign accuracy**. Those have different optima.

So the terms were scaled by `k` and `k` swept, with `k = 0` the plain evaluator so the status quo is one of the points.

## The curve

```
  scale      gain    sd across splits   positive   verdicts moved
    0.0    +0.00pp        0.00            0/24          0.0%
   0.25    +0.28pp        0.46           18/24          4.9%
    0.5    +0.53pp        0.69           19/24          8.8%
    1.0    +1.00pp        0.95           21/24         14.2%   <- 0030 tested here
    2.0    +0.57pp        1.57           16/24         20.4%
    4.0    -0.95pp        1.83            6/24         26.1%
    8.0    -2.87pp        1.87            2/24         30.6%
```

A peak at scale 1, falling away on both sides and clearly harmful by scale 4. **0030 sampled the best point available.** Its number was low, but its conclusion was not the result of testing the wrong setting the way 0027's was.

## The statistic I nearly got wrong

The first version of this printed a standard error as `sd / sqrt(24)`, which would have made scale 1 look like +1.00 ± 0.19 — five standard errors from zero, and a confident claim.

**It is not a standard error.** Repeated cross-validation folds reuse the same 19,035 positions; they are not independent samples, and dividing by the root of the fold count understates the uncertainty by a lot. The honest measure of spread is what two runs of the same computation actually produced:

```
0030   8 splits, seeds 100+   +0.2pp
0034  24 splits, seeds 200+   +1.00pp
```

Both are estimates of the same quantity from the same data. The gap between them is the uncertainty, and it is comparable to the effect.

## What this settles

- **The extra terms are worth something small**, probably in the region of half a point to a point of winner prediction, at a scale near where 0030 tested. Calling it a flat null was slightly too strong; calling it a win would be much too strong.
- **Sweeping is not a universal rescue.** It moved switching from "harmful" to "shipped" because the curve crossed zero between untested settings. Here the curve has no such crossing, and the sweep's value was confirming that rather than finding anything.
- **Nothing ships.** `evaluate_position` has no production caller — search does not use it — so a change would alter no games today. It matters only if search is re-opened, and 0022 is a standing reminder that lookahead has disappointed here twice.

## Not established

- Whether the gain is real at all. +0.2 and +1.00 from the same data leave zero inside the plausible range.
- Whether these features would help a *search* even if they barely help winner prediction. Ranking near-identical positions one ply apart is a different task from naming the eventual winner, and nothing here measures it.
- Whether a non-linear model finds something linear terms cannot. Unchanged from 0030.
