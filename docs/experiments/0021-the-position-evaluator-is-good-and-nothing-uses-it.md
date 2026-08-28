# Experiment 0021 — The position evaluator is good, and nothing uses it

**Date:** 2026-08-25
**Result: `evaluate_position` names the eventual winner 79.7% of the time, 85.7% by mid-game, and is well calibrated — and it has no production caller.** Search does not use it. That reframes experiment 0001's finding that one-turn search is inert: the search had nothing to look ahead *with*.

Also fixes a bias in the evaluator worth 80 points on a turn-one board, and a flaw in the measurement that would have reported the opposite conclusion.

## Why this was run first

Experiment 0020 established that what the agent *chooses* is worth more than what it *knows*, which points at a value model (Milestone 7) and search (Milestone 11). Both need one thing before either is worth building: **something worth maximising.** A lookahead over an evaluator that cannot tell winning from losing reproduces the scorer underneath it.

`evaluate_position` already exists. It is exported, has unit tests, and its own docstring says search needs it and that Milestone 7 replaces it. Nothing had ever checked whether it predicts anything.

Measured on self-play, because the corpus cannot label a *position* — only the engine will play a given board out to its end on demand.

## The measurement nearly said the opposite

The first run reported turns 1–2 at **43.7%** — worse than a coin flip on n=900, which is not noise. It was the harness: battles paired `teams[i]` against `teams[i+1]` **without exchanging them**, so player 0 systematically held one side of every matchup. "The evaluator says we lead and we lose" was measuring the pairing.

`evaluate` does the exchange by construction. A hand-rolled loop has to remember, and this one did not.

```
                 unexchanged      exchanged
turns 1-2           43.7%           70.2%
turns 3-5           69.6%           82.3%
turns 6-9           74.1%           81.3%
overall             62.7%           77.6%
```

## A real bias, found on the way

An unrevealed opponent scored `POKEMON_WEIGHT` alone — 100 — while one of ours at full health scored `POKEMON_WEIGHT + HP_WEIGHT` = 140. **But a Pokémon that has not been sent out is at full health; that is the whole point of not having sent it out.**

At turn one that made a dead-even board read **+80 in our favour**. A bias rather than noise: it always pointed the same way, and it was largest exactly when the least was known.

```
                 before fix    after fix
turns 1-2          70.2%        71.0%     (n = 900 -> 600)
turns 3-5          82.3%        81.0%
turns 6-9          81.3%        85.7%
turns 10+          74.5%        74.5%
overall            77.6%        79.7%

slim   (<50)       59.8%        66.1%
clear  (50-150)    77.4%        82.7%
large  (>150)      86.7%        86.2%
```

The sample size on turns 1–2 falling from 900 to 600 *is* the fix working: an even board now evaluates to exactly zero and is abstained on, rather than claiming a lead. And the biggest gain is in slim advantages — the ones an 80-point offset could flip.

## What this settles

**The evaluator is good enough to maximise.** 79.7% overall, 85.7% mid-game, and monotone in its own confidence: the larger the advantage it claims, the more often it is right. That is the property search actually needs, and it is not obvious a hand-written function would have it.

**So experiment 0001 needs a better explanation.** It found one-turn search inert (49.3%, not significant) and blamed opponent knowledge — an explanation since refuted three times over (0005, 0018, 0019). The likelier cause is visible in the code: `search.py` scores actions with the heuristic's own per-move numbers and never calls `evaluate_position` at all. It was not searching over positions; it was re-deriving the heuristic with extra steps.

**And a learned value model is not the next thing.** 79.7% is a high floor for a hand-written function. Milestone 7's headroom over it is real but modest, and it is worth less than giving search an evaluator it currently does not use.

## Not established

- Whether search *with* this evaluator beats the heuristic. That is the next item and it may well fail; 0001 is a standing reminder that lookahead has disappointed here once already.
- How well the evaluator ranks *close* positions, which is what search actually compares. Sign-versus-winner is the coarsest possible test, and 66.1% on slim advantages is the weakest cell in the table.
