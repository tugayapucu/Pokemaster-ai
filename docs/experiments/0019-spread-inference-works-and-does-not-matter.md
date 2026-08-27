# Experiment 0019 — Spread inference works, and does not matter

**Date:** 2026-08-25
**Result: the inference is real and the effect is not.** Inferring opponent Stat Points from observed damage cuts the error against their true spread from **16.0 to 14.7 points**, and wins **50.8%** head-to-head against the agent that does not bother (95% CI 48.4–53.3%, p = 0.516). The mechanism is correct; it closes about 8% of the distance to the truth, and 8% of a +3.6-point ceiling is nothing you can measure.

Backlog item, built after experiment 0018 measured the ceiling and said spreads were where the whole of it lived. Predicted flat before running, and flat is what it is.

## What was built

Every hit is an equation with one unknown:

```
a hit we take     tells us about their attacking stat
a hit we land     tells us about their defending stat
```

Everything else in the damage formula is either ours — exact, from our own request — or public. The unknown is recovered by **binary search over `estimate_damage`** rather than by algebra: damage is monotonic in both stats, and reusing the model already measured at 93.9% against the engine keeps one damage formula in this project instead of two that can drift apart.

**Only unambiguous turns teach anything.** In doubles two of ours attack and two of theirs can lose health, and attributing the wrong damage to the wrong Pokémon is *worse* than not learning — a wrong belief is acted on with exactly the confidence of a right one. Each direction refuses unless the pairing is forced.

The agent sees only `Observation`s, never protocol, so damage is recovered by diffing consecutive observations against the action it chose.

## It does infer something

Graded against the truth, which only the engine can supply — Stat Points are never published (ADR 0002), so the corpus cannot referee this at all:

```
200 battles, 111 stats the agent formed a view on

flat prior (11 everywhere)   mean error 16.0 points
exponential walk             mean error 15.4
mean of what the hits imply  mean error 14.7
```

The middle line is worth keeping. The first estimator walked 45% toward each observation, and with one or two readings per stat **it never travelled far enough from its starting guess to beat it**. Taking the mean of the implied values instead roughly doubled the improvement. An estimator can be too timid to be worth having.

## And it changes nothing

```
concentrated-spread pool, teams exchanged, 800 battles x 2 seeds

  seed 1   398/800  = 49.8%   (95% CI 46.3%-53.2%)
  seed 7   415/800  = 51.9%   (95% CI 48.4%-55.3%)
  pooled   813/1600 = 50.8%   (95% CI 48.4%-53.3%)   z = 0.65, p = 0.516
```

Predicted before the run at roughly +0.3 points, from 8% of a +3.6 ceiling. Measured at +0.8, comfortably inside the noise.

## Why the chain does not pay

0018 established the ceiling by handing the agent *perfect* spreads. Getting a useful fraction of +3.6 needs a belief close to perfect, and 14.7 points of average error is not close — the whole legal range is 0 to 32.

Three reasons it cannot easily get closer, all structural:

- **The observations are scarce.** 111 stats across 200 battles. The attribution rules are strict on purpose, and relaxing them trades precision for volume in the direction that makes a wrong belief confident.
- **Each observation is noisy.** The damage roll alone is ±7.5%, before an unknown item or ability shifts the reading further.
- **The corpus cannot help.** Nothing outside the engine can grade a spread, so there is no larger dataset to fit against.

## What this leaves

The code stays, opt-in and off by default (`infer_spreads=False`), with tests. That is a deliberate choice rather than sentiment: 0018's +3.6 ceiling is real, and a materially better inference — joint estimation across a whole team under the 66-point budget, or priors from usage statistics — could still claim some of it. What is dead is *this* inference, and the assumption that damage observations alone are enough.

Kept off rather than deleted, and named as unused, so it does not become the thirteenth instance of this project's most common bug: something that exists, is never read, and is quietly believed to be working.
