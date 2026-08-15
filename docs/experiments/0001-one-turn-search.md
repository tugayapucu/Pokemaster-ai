# Experiment 0001 — Does one-turn lookahead beat a damage heuristic?

**Date:** 2026-08-15
**Git commit:** see `git log` for the `feat(agents): add SearchAgent` commit
**Result: No.** Kept as a documented negative result, not as an improvement.

## Hypothesis

The heuristic treats opponents purely as damage targets — it never asks whether
it is about to be knocked out, or whether it moves first. Adding a one-turn
lookahead that prices the opponent's reply should beat it.

## Setup

| | |
|---|---|
| Agents | `SearchAgent(pessimism=0.7)` vs `HeuristicAgent` |
| Regulation | Gen 9 Champions VGC 2026 Reg M-B |
| Teams | Generated pool of 10, 74 distinct matchups |
| Battles | 300, sides and teams both exchanged per matchup |
| Seed | 2026 |
| Primary metric | Win rate with a 95% Wilson interval |

## Result

```
search-v1 vs heuristic-v1: 148-152 over 300 battles
win rate 49.3% (95% CI 43.7%-55.0%, not significant)
ahead in 28/74 matchups
```

Sanity checks against the Random baseline, same pool:

```
search-v1    vs random: 188-12 (94.0%, CI 89.8-96.5%)
heuristic-v1 vs random: 192-8  (96.0%, CI 92.3-98.0%)
```

Search is indistinguishable from the heuristic, and if anything marginally
worse against Random.

## Why

Instrumented over 119 decisions in live battles:

- **Search chose a different action from the heuristic on 6% of turns.**

That is the whole result. Two policies that agree 94% of the time will split a
head-to-head near 50%, whatever the reasoning behind the other 6%. The
lookahead is not wrong so much as inert.

It is inert for a reason worth recording: **the opponent's moves are mostly
unknown.** Across decisions, a mean of ~3.0 opponent moves had been revealed in
total across their whole team, and 10% of decisions had none at all. Battles
last 5-6 turns, so there is little time to learn anything. A threat model built
only on revealed moves therefore has almost nothing to work with, and an
opponent whose moves are unknown looks harmless.

A second version that removed a threat when our move would guarantee-KO the
attacker *and* win the speed check did not change this (49.3% is that version).

## Conclusion

At this depth and in this format, **search depth is not the bottleneck —
opponent knowledge is.** Reasoning about a reply you cannot see does not
improve play, however carefully it is priced.

This is direct evidence for the ordering of `PROJECT_PLAN.md`'s research
questions 5 and 6: modelling hidden information is worth more than deeper
search, and should come first.

## Follow-up: is exact search even possible?

Asked while writing this up, because the answer changes what "deeper search"
would cost. Measured directly:

- Showdown supports `Battle.toJSON()` / `Battle.fromJSON()` (`sim/state.ts`).
- A battle serialises to ~27 KB in ~0.7 ms and restores in ~1.4 ms.
- A restored fork advances **in complete isolation**: the fork took damage and
  reached turn 2 while the original stayed untouched at turn 1.
- Roughly **460 forks/sec**.

So exact search is affordable for a recommendation system (one decision, a
second of budget) and far too slow for RL self-play (millions of decisions).
Reimplementing battle resolution to go faster remains ruled out by ADR 0001:
forking is exact by construction, a reimplementation diverges silently.

This resolves the open question in `PROJECT_PLAN.md` section 15.

## Next action

- Keep `SearchAgent` as a baseline and as scaffolding: its threat model gains
  real inputs the moment opponent modelling (Milestone 10) can supply a prior
  over unseen movesets.
- Do **not** present it as the strongest agent. `HeuristicAgent` remains the
  best available policy.
- Revisit after opponent modelling, re-running this exact comparison.
