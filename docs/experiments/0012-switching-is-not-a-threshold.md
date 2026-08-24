# Experiment 0012 — Switching is not a threshold problem

**Date:** 2026-08-24
**Result: negative, and informative.** Fitting the switching constants **overfits** — it improves the training half and degrades the held-out half. Forcing the agent to switch as often as humans do makes it *worse overall* while still disagreeing with three quarters of their switches. This is the third independent failure to close the switching gap, and together they say the gap is not about *how readily* the agent switches.

## Why this was the obvious next thing

The disagreement map puts switching at **19% of every disagreement** — 950 labels, second only to target selection. And the numbers looked exactly like a mis-set threshold:

```
humans switch  11.7%        agent switches  2.2%        a 5x gap

when the human switched, we switched too   11.7%
when WE switched, the human also switched  62.9%
```

High precision, low recall. `SWITCH_COST` and `SWITCH_WHEN_WEAKENED_BONUS` had **never been fitted** — exactly the situation that, for Protect, produced the largest gain in the project (44.3% → 57.6% on its own labels). The same recipe was the natural move.

## It overfits

Fitted on the training half with the split that already exists, reported on the test half the sweep never saw:

```
                    train              test
  before          45.357%            47.062%
  after           45.468%            46.821%
```

**Train up, held-out down.** That is the textbook overfitting signature, and it is exactly the check the split exists to make. The change was not applied.

Two details worth noting. The full sweep (all thirteen knobs) showed the same divergence and additionally re-made two mistakes already diagnosed and reverted in 0010 — Trick Room back to its degenerate value, Leech Seed back to noise — because a sweep maximising training agreement will happily undo a correction made on principle. And the switch-only sweep wanted the cost to go **more** negative, from −25 to −60: switch *less*, not more, which is the opposite of what the 5× rate gap suggested.

## What the rate actually buys

Sweeping the cost by hand shows the whole trade at once:

```
switch cost   we switch    recall   precision    overall
      -90        1.0%       7.0%      91.2%      45.38%
      -60        1.1%       7.6%      88.3%      45.41%
      -25        2.2%      10.3%      62.9%      45.36%   <- current
        0        4.2%      14.1%      47.0%      44.97%
      +25       11.2%      26.7%      34.9%      43.52%   <- the human rate
      +60       26.7%      41.1%      23.9%      38.37%
```

At +25 the agent switches on **11.2%** of decisions, matching the human 11.7% almost exactly. It still disagrees with **73%** of their switches, and overall agreement falls **1.8 points**.

> **Matching the rate does not mean matching the decisions.** The agent does not switch too rarely; it does not know *when*.

Turning the dial adds switches at moments humans would have attacked, and the ones it adds are not the ones they made.

## Three failures, and what they rule out

| Attempt | Result |
|---|---|
| Matchup-based switch scoring (0004) | reverted — measured worse |
| Fitting the constants (here) | overfits — train up, test down |
| Matching the human rate (here) | worse overall, recall still 27% |

And a fourth from a different direction: **experiment 0005** found that perfect knowledge of the opponent's moveset buys +0.09 points, and perfect knowledge of the move they use *this turn* makes the agent **worse**. So the missing signal is not the opponent's immediate action either.

What is left is that human switching is driven by something this agent structurally cannot express. The hypothesis worth naming — and it is a hypothesis, recorded rather than acted on — is that switches are **plans about the game rather than the turn**: preserving a win condition, keeping a check healthy for a threat that has not appeared yet, conceding a turn now to be positioned three turns later. This agent scores one turn at a time and sums two slots, so no single-turn signal it could be given would express any of that.

If so, closing this gap is not another constant or another feature. It is a different shape of agent, and worth being sure about before paying for it — which is precisely what experiment 0005 established as the house rule after the same mistake was nearly made there.

## What was kept

Nothing. The constants stay where they were. The value of the experiment is the three-way elimination and the rate/recall table, which say what *not* to try next.
