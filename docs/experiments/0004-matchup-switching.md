# Experiment 0004 — Switching on the matchup

**Date:** 2026-08-20 (first run), **revised 2026-08-20** after 10× more data
**Git commit:** see `git log` for `feat(agents): switch on the matchup` and its revert
**Result: NEGATIVE. Reverted.** The first version of this document concluded the opposite, on evidence that did not survive being re-run properly. The correction is the most useful part of it.

## Hypothesis

Experiment 0002 found the largest behavioural gap in the agent: rated humans
switch on **11.5%** of decisions and `heuristic-v1` on **1.8%**, agreeing on 113
of 1,281 switch labels. Switching scored a flat −25 with a bonus when weakened,
so it was almost never worth a turn.

Pricing a switch by **the matchup it buys**, minus the turn and the free hit it
costs, should close that gap.

## Change (since reverted)

```
value = (incoming_matchup − current_matchup) × SWITCH_HORIZON
        − forgone_attack
        + bonus if staying in would be knocked out
```

`SWITCH_HORIZON` was calibrated to the **human switch rate** rather than to the
agreement score: at 1.0 the agent switched on 11.0% of decisions against a human
10.7%.

## What it did to the switch decision itself

It worked, on the narrow question:

```
switch labels agreed:  113/1281 (8.8%)  ->  297/1281 (23.2%)
agent switch rate:     2.1%             ->  14.0%   (human 11.5%)
```

Nearly triple the switch agreement. Had that been the only measurement, this
would read as a clear success.

## Result 1 — overall agreement fell, decisively

```
flat-switch     4793/11133 = 43.1%
matchup-switch  4418/11133 = 39.7%

only OLD agreed 593    only NEW agreed 218
McNemar chi2 = 172.47 — overwhelmingly significant, against the change
```

Every gain on switch turns was outweighed several times over by losses on move
turns. A parameter sweep confirmed this is not a tuning artefact: at every
setting tried, overall agreement sat below the flat baseline.

On the first 50-game corpus this same comparison gave chi2 = 13.69. At 500
games it is 172. **More data did not soften the verdict, it hardened it.**

## Result 2 — the strength result did not replicate

This is where the first version of this document went wrong. It concluded from
a single 600-battle run:

```
FIRST RUN   (600 battles, 8-team pool)      354-246 = 59.0%  significant
```

and kept the change on that basis. Re-run at higher power on a larger pool:

```
seed 31     (800 battles, 12-team pool)     410-390 = 51.2%  NOT significant
seed 4242   (800 battles, 12-team pool)     437-363 = 54.6%  significant
pooled      (1,600 battles)                 847-753 = 52.9%

vs Random:  matchup-switch 290-10 = 96.7%
            flat-switch    297-3  = 99.0%
```

The 59% was overfit to one pool and one seed. Pooled, the edge is ~3 points and
one of the two seeds shows nothing at all — and against Random the change is
**worse**, losing 10 games where the flat version loses 3.

## The error, stated plainly

Experiment 0003 recorded this exact failure mode and warned about it:

> The 200-battle run suggested 55.5%; at 800 it regressed to 51.6%. **The first
> number was noise**, and is recorded here because stopping at 200 would have
> produced a false claim.

Then this experiment stopped at 600 battles and produced a false claim. Writing
down the lesson did not prevent repeating it; only re-running did.

The methodology note that came out of the first version — *"head-to-head is the
arbiter when the two metrics conflict"* — was reasoning from a number that was
not real. **The metrics were never actually in conflict.** Agreement said no,
strength said nothing much either way, and only an underpowered run made it look
like a disagreement.

## Decision

**Reverted.** Three independent signals and none support the change:

| Measure | Verdict |
|---|---|
| Human agreement, 11,133 labels | **Worse**, chi2 = 172 |
| Head-to-head, 1,600 battles | ~52.9%, marginal, one seed null |
| Against Random, 300 battles | **Worse** — 96.7% against 99.0% |

The matchup machinery in `mechanics/matchup.py` stays: Team Preview uses it, and
the speed-edge fix it carries was justified independently.

## What this leaves

**Switching is still the largest known behavioural gap, and it is now an
honestly open one.** The agent switches on 2.1% of decisions where humans switch
on 11.5%. We know the gap, we know one formulation that does not close it, and
`tests/unit/agents/test_switch_scoring.py` pins the crudeness deliberately so
the next attempt starts from a truthful baseline rather than a flattering one.

## Next actions

- **Do not conclude a head-to-head from under ~1,500 battles**, and always run
  at least two seeds on a pool of ten or more teams. Twice now the first number
  has been wrong in the same direction.
- Any future switching attempt must beat flat switching on **agreement and
  against Random**, not only in a head-to-head against the thing it replaces.
- The likelier cause of the gap is not how switching is *scored* but what the
  agent cannot see — an opposing switch, a Pokémon worth preserving for a later
  matchup. That is opponent modelling (Milestone 10), not a scoring term.
