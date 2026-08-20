# Experiment 0006 — Imitating humans better makes the agent play worse

**Date:** 2026-08-20
**Result:** A learned policy beats the heuristic by **+4.2 points** of human agreement on held-out data (p<0.01) and loses to it **520–1080 over 1,600 battles**. Both results are well powered. **Human agreement is a diagnostic, not an optimisation target.**

## Setup

Experiment 0005 found the binding constraint was the decision rule rather than
the inputs, so this keeps the features and learns the mapping: a conditional
softmax over the legal actions in a slot, trained by SGD on cross-entropy
against what a rated human chose.

`heuristic_score` is one of the 26 features, so the model can reproduce the
heuristic exactly by putting all its weight there. Any gain is therefore a gain
*over* the hand-written rule on identical information.

Trained on 405 replays, judged on 95 held out by a hash-stable split.

## Result 1 — agreement improved, clearly

```
linear-policy  995/2076 = 47.9%  (CI 45.8-50.1%)
heuristic-v1   907/2076 = 43.7%  (CI 41.6-45.8%)
random         485/2076 = 23.4%

gained 204, lost 116, McNemar chi2 = 23.65, p<0.01, +4.24 points
```

For scale, the entire move-effects arc (experiments 0002–0003, four commits of
mechanics work) gained 1.4 points.

## Result 2 — it plays far worse

```
seed 31     247-553 = 30.9%  (CI 27.8-34.2%)  significant, ahead in 29/125 matchups
seed 4242   273-527 = 34.1%  (CI 30.9-37.5%)  significant, ahead in 36/127 matchups
pooled      520-1080 = 32.5% over 1,600 battles

vs Random:  linear 93.7% (281-19)    heuristic 99.0% (297-3)
```

Not a marginal effect and not an underpowered one. Two seeds, 1,600 battles,
both significant, and worse against Random as well.

## The mechanism, measured

The learned weights put **`guaranteed_ko` at −1.63**, second only to
`heuristic_score` at +1.63. Checked directly on the test split:

```
slots where a guaranteed knockout was available : 633
  heuristic took it   : 630  (99.5%)
  learned policy took : 478  (75.5%)
```

**It declines a free knockout one time in four.** In a format where battles last
five turns, that alone accounts for the win rate.

### Why imitation learned that

Two causes, and the second is the uncomfortable one:

1. **Humans decline apparent knockouts for reasons we cannot see** — protecting,
   setting up, positioning for a later turn. Every one of those is scored as the
   agent being wrong to take the knockout.
2. **Some of those knockouts are not real.** `guaranteed_ko` is computed against
   *estimated* opponent stats, since Stat Points are never published. The human,
   who could see the actual result, did something else. The model correctly
   learned "do not trust this feature" — which is right for imitating humans and
   catastrophic in play, where our own estimate is what decides the action.

So the model absorbed our estimation error as a policy bias. It is not
mis-trained; it is trained on exactly the right objective, and that objective is
not the one we want.

## What this changes

**Agreement generates hypotheses. Strength validates them. Neither is optional.**

That is not a retreat to "strength is the only real metric" — experiment 0003
showed agreement detecting at p<0.01 a change that 800 battles could not see.
The two answer different questions and the failure mode is treating either as
sufficient:

| | Detects | Fails at |
|---|---|---|
| Human agreement | Small behavioural changes, cheaply, on real human decisions | Rewards imitating human limits, and our own estimation errors |
| Head-to-head | Whether the agent actually wins | Blind to changes smaller than ~3 points; needs 1,500+ battles |

It also puts earlier disagreement analysis in a new light. The recurring finding
that "the heuristic over-values damage and knockouts relative to humans" is
real — and is **not necessarily a defect**. The heuristic beats Random 99% and
beats a policy trained to correct exactly that tendency. Some of the gap between
our agent and human choices is the agent being right.

Move effects (0002–0003) remain justified: they improved agreement *and* cost
nothing in strength. That is the bar.

## Decision

**The learned policy is not adopted as the agent.** `HeuristicAgent` remains the
strongest thing here. The `ml/` package stays: the split, features and trainer
are reusable, the finding is worth keeping reproducible, and `policy.py` carries
the warning in its docstring so nobody wires it in by mistake.

## Next actions

- **Do not optimise agreement directly.** Any future learned policy needs a
  training signal tied to winning — self-play, a value model, or imitation
  *filtered* to positions where the human demonstrably came out ahead.
- **The knockout feature is worth fixing on its own terms.** If `guaranteed_ko`
  is sometimes wrong because opponent stats are estimated, the honest fix is a
  calibrated confidence rather than a boolean — and that would help the
  heuristic too.
- Weight-inspection stays valuable as a *diagnostic*. It named the heuristic's
  biases in one run, which is faster than the by-hand disagreement analysis that
  took three experiments to reach the same conclusions.
