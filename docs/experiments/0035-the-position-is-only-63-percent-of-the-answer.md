# Experiment 0035 — A position is only about 63% of the answer

**Date:** 2026-09-03
**Result: winner prediction from a position saturates at roughly 63%, and the hand-written evaluator is already there.** A capacity ladder from base features to every feature plus interactions moves accuracy 61.8% → 63.8% and stops. An oracle that memorises the outcome distribution of near-identical positions tops out at **62.7%**. `evaluate_position` scores 63.2%. **Backlog item 3 — a learned value model — has about a point of headroom over a function written by hand, and that is measured rather than argued.**

## Why measure the ceiling before building the model

Every re-measurement of the evaluator on a better instrument has *lowered* it:

```
0021   79.7%   generated pool, later found unrepresentative
0028   74.6%   frozen pool of harvested teams
0030   63.9%   reconstructed human positions
```

A learned model faces whatever limit produced that sequence. If evenly matched play is simply not very predictable from a board state, more capacity buys nothing, and the honest thing is to find that out for the cost of an afternoon rather than a milestone.

## The capacity ladder

Held out by replay, six splits, spread reported as a range rather than a standard error — repeated folds reuse the same 19,035 positions and are not independent samples.

```
  shipped evaluate_position     63.2%    61.7% - 64.9%
  linear, base only             61.8%    60.8% - 63.2%
  linear, all features          63.7%    62.2% - 64.6%
  linear + interactions         63.8%    62.3% - 64.7%
```

Two points matter here. Adding every extra feature and then products, squares and turn interactions on top buys **+2.0pp over base and then stops moving**. And a function somebody wrote by hand, with four terms and no fitting at all, sits inside the range of the best model tried.

## The Bayes-error probe

The ladder shows a model class running out of room; it does not show whether the *information* has run out. So: group positions that look nearly identical and ask how consistent their outcomes are. Where the same board wins half the time, nothing can do better than half.

Resolution is swept on purpose. Coarse buckets merge genuinely different positions and understate the ceiling; fine buckets memorise and overstate it. The trend is the reading.

```
  resolution     buckets   covered   ceiling
  very coarse         21      100%    57.6%
  coarse              88      100%    61.7%
  medium             146       99%    62.3%
  fine               296       97%    62.6%
  very fine          721       90%    62.7%
```

It converges to about 62.7% and stays there while the bucket count grows thirty-fold. Positions that look the same really do end differently, about a third of the time.

## What this means for search

The turn breakdown is the part that bears on Milestone 11:

```
  turns 1-2   n=2334   54.8%
  turns 3-5   n=7477   61.5%
  turns 6-9   n=5040   69.1%
  turns 10+   n=1230   67.6%
```

**A search compares positions one or two plies apart, and one or two turns in is where the evaluator is nearly blind.** 54.8% on turns 1-2 is a coin flip with a lean. This is the same conclusion 0022 reached from the other direction — the lookahead was inert, and waking it cost nine points — now with a reason attached rather than a diagnosis.

## What this settles

- **The learned value model is not worth building against these features.** About a point of headroom over a hand-written function, on a task whose ceiling is 63%.
- **The evaluator is not the thing holding search back.** It is close to the limit of what a position can tell you. Search's problem is that the limit is low.
- **The sequence of falling numbers was not a series of regressions.** 79.7% was measured on the wrong pool, 74.6% on self-play against an opponent sharing our habits, 63.2% on real positions. Each step was a better instrument, and 63% is what was there all along.

## Not established

- **Whether richer features have more room.** These are aggregates: health difference, living count, boost stages. They discard species, movesets, items and matchup entirely. A model that could see *which* Pokemon are on the field might do better, and nothing here rules that out — it rules out the aggregate view, which is what Milestone 7 specified.
- Whether a ceiling measured on human games binds a self-play agent. The corpus is 1500-1850 Elo; more decisive play might be more predictable.
- Whether ranking two positions one ply apart is easier than naming the eventual winner. It is a different task and this does not measure it, though 54.8% on turns 1-2 is not encouraging.
