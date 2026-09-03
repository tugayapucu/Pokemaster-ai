# Experiment 0037 — Richer features do not move the ceiling either

**Date:** 2026-09-03
**Result: adding matchup features to the aggregates buys +1.0pp and moves the Bayes-error ceiling by +0.4pp.** 0035 measured the aggregate view at ~63% and explicitly left one door open: those features discard species, movesets, items and matchup. This opens that door. Aggregates alone score 63.5%, aggregates plus twelve matchup features 64.5%, and the bucket-oracle ceiling rises from 62.7% to 63.1%. **The hand-written `evaluate_position`, with four terms and no fitting, scores 64.2% — inside the range of the best model tried.**

## The door 0035 left open

The aggregates are health difference, living count, boost stages, side conditions. Two boards with identical health can be a favourable matchup or a hopeless one, and nothing in that set can tell them apart. So the obvious objection to 0035's ceiling was that it measured the wrong representation.

`mechanics.matchup` is the missing view, and it already existed because Team Preview uses it. Per live pairing, from the real movesets and stats on the field:

```
offence     fraction of their HP our best move removes
defence     fraction of ours their best expected attack removes
speed_edge  signed turn order, scaled by offence * defence
```

Twelve features: mean, best and worst net across active pairings, the offence, defence and speed components, and the same six for the best matchup sitting on the **bench** — because "behind, but holding the answer in reserve" is another thing a health difference cannot say.

## The ladder

```
  shipped evaluate_position    64.2%    63.6% - 65.1%
  aggregates only              63.5%    62.2% - 64.4%
  matchup only                 56.0%    54.9% - 57.0%
  aggregates + matchup         64.5%    63.6% - 65.2%
```

Three things stand out.

**Matchup adds +1.0pp** over aggregates. Real, and small.

**Matchup alone is 56.0%**, far below aggregates alone. Knowing exactly who is on the field and what they can do to each other tells you much less about who wins than knowing how much health each side has left. That is worth sitting with: the aggregate view is not a lossy summary of the matchup view, it is the more informative one.

**A four-term function written by hand scores 64.2%**, inside the range of a fitted twenty-four-feature model. Across two experiments and two feature sets it has never trailed the best fitted model by more than 0.6pp -- less than the split-to-split spread of either.

## The ceiling probe

The ladder shows a model class running out of room. The probe asks whether the *information* has. Bucketing now includes matchup net, so positions that looked identical under health alone are separated.

```
  coarse, no matchup    88 buckets   100% covered   61.7%
  coarse + matchup     210 buckets    98% covered   62.4%
  medium + matchup     469 buckets    94% covered   62.8%
  fine + matchup       882 buckets    82% covered   63.1%
```

Against 0035's converged 62.7% without matchup: **+0.4pp**, and the finest resolution is down to 82% coverage, so part of that last step is memorising rather than separating.

## What this closes

- **The value-model line is finished.** Aggregates were measured at ~63% (0035); the most obvious richer representation, already implemented and computed by the engine's own damage calculator, adds a point. A learned model has nowhere to go that has not now been checked twice with different feature sets.
- **`evaluate_position` is not the weak link.** It trails the best fitted alternative by 0.6pp in 0035 and 0.3pp in 0037, both well inside the split-to-split range. Nothing fitted has pulled away from it. The limit is the task, not the function.
- **This bounds search, not just the evaluator.** 0022 found the lookahead inert and nine points worse when woken; 0035 found turns 1-2 predictable at 54.8%. A search compares positions a ply or two apart, and no representation tried moves that.

## Not established

- Whether a *learned* representation beats a hand-crafted one. These are engineered features; embeddings over species and moves, trained end to end, are a different proposition. What this shows is that the obvious hand-crafted enrichment does not pay, which is what Milestone 7 actually proposed.
- Whether the ceiling is a property of the game or of the corpus. 1500-1850 Elo games between evenly matched players may simply be less predictable than decisive ones.
- Whether ranking two positions one ply apart is easier than naming the eventual winner. Still a different task, still unmeasured, and still the only route by which search could pay.
