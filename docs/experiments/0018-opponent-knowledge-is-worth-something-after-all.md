# Experiment 0018 — Opponent knowledge is worth something, and only one part of it

**Date:** 2026-08-25
**Result: the ceiling is +4.3 points of win rate, and essentially all of it is stat spreads.** Perfect knowledge of the opponent's item and ability is worth **nothing** measurable. Perfect knowledge of their spread is worth about **+3.6 points** — but only on teams whose spreads are actually concentrated, which the first version of this measurement could not have discovered.

This does not overturn experiment 0005; it completes it. 0005 measured *movesets* against *agreement* and found nothing. This measures *spreads, items and abilities* against *win rate*, and finds one of the three carries everything.

## The measurement that nearly lied

The first run gave a clean flat answer:

```
generator's own spreads, pooled    811/1600 = 50.7%   (95% CI 48.2%-53.1%)
```

Both seeds spanned 50%. On that alone the direction was dead.

Then the pool turned out to be the reason it could not have said anything else. Showdown's random-battle generator hands out:

```
49 of 72 Pokemon    (11, 11, 11, 11, 11, 11)   <- the agent's exact assumption
17 of 72            (11,  0, 11, 11, 11, 11)
mean max-min gap    2.8 points
```

`assumed_opponent_points = 11` spreads 66 points evenly over six stats. **The agent's assumption was already correct for the entire test population**, so the spread half of the oracle was inert and the run was silently measuring item and ability knowledge alone.

That is the fourth time in two days that an instrument could not see the thing it was pointed at, and the first where the blind spot was in the *population* rather than the harness.

## Asking again, on teams worth knowing about

Every generated spread was rewritten into a competitive shape — 32 into the stat the Pokémon actually attacks with, 32 into Speed, the remainder into HP — and revalidated through the engine, so nothing illegal entered the pool.

```
mean max-min gap    2.8  ->  32.0

concentrated spreads, pooled       869/1600 = 54.3%   (95% CI 51.9%-56.7%)
generator's spreads,  pooled       811/1600 = 50.7%   (95% CI 48.2%-53.1%)

difference between the two arms     z = 2.05,  p = 0.040
```

The concentrated arm excludes 50%. The difference between arms is itself significant.

## What that decomposes into

The two arms differ in exactly one thing: whether the oracle's *spread* knowledge is worth anything, because in the flat arm the baseline already had it right.

```
item + ability knowledge      ~0 points     (the flat arm is 50.7%)
spread knowledge             ~3.6 points    (the difference between arms)
everything together          +4.3 points
```

**So the thing to build is spread inference.** Tracking items and abilities more aggressively is not where the value is, which is the opposite of what the backlog assumed when it listed `_known_ability` and the item-gated moves as motivation.

## The honest size of it

+4.3 points is the ceiling for a *perfect* oracle. Any real inference system captures some fraction of that. For scale, on the same instrument and the same bar:

```
scoring the Mega forme (one afternoon)      60.1%   = +10.1 points
perfect opponent knowledge (a milestone)    54.3%   =  +4.3 points
```

The entire ceiling of opponent modelling is less than half of what a single afternoon's mechanical fix delivered. That is not an argument against doing it — it is an argument for knowing what it is worth before committing a milestone to it, which is the whole reason this was run first.

## Caveats worth carrying

- **The concentrated pool is synthetic.** Every Pokémon got the same
  32/32/2 shape. Real teams vary more and in more directions, so the agent's
  assumption would be wrong in more varied ways. +3.6 is the right order of
  magnitude, not a precise figure.
- **This measures a perfect oracle, not an achievable one.** Spreads have to be
  *inferred* from observed damage, and no inference will be exact.
- **The corpus cannot grade spread inference** — Stat Points are never
  published (ADR 0002). The engine differential harness knows both sides'
  true stats from the requests, so it is not merely the better instrument
  here, it is the only one.
