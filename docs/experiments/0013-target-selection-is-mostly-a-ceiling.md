# Experiment 0013 — Target selection is mostly a ceiling

**Date:** 2026-08-24
**Result: the hypothesis is refuted, and the gap is smaller than it looked.** Preferring the more dangerous of two opponents made agreement **significantly worse on both halves** and *increased* the wrong-target count it was built to reduce. Probing what humans actually target found no strong signal in anything computable. And the agent turns out to be at **77.5% / 79.7%** on genuine two-target choices against a 50% floor — so the 858 "wrong target" labels are largely irreducible rather than a gap to close.

This corrects the framing in experiment 0011, which called it "the largest measured gap".

## The hypothesis

0011 eliminated two causes for the 858 wrong-target labels — not focus fire, and not a slot bias (495 against 432, near-symmetric) — and left one untested:

> Removing a *dangerous* opponent is worth more than removing a harmless one, and nothing in the score says so, while `_incoming_threat` already computes exactly that per opponent and is used only for Protect.

Implemented as damage *avoided*, in the currency Protect already uses: a knockout's value scaled by how much of our health bar that particular opponent would remove next turn.

## It made things worse

```
                              train              test
  overall                45.42% -> 44.77%   47.25% -> 46.19%
  right move, wrong target   938 -> 962         204 -> 213
  McNemar                104 up, 163 down    16 up, 38 down
                            p = 0.00039        p = 0.0043
```

Both halves agree, both are significant, and the count it was designed to reduce went **up**. Reverted in full; only the `_threat_from` refactor is kept, because splitting the per-opponent half out of `_incoming_threat` makes that function clearer regardless.

## What humans actually target

Rather than guess a second time, the question was asked of the data: over **3,333** attacks where both opponents were alive, which one did the human pick?

```
  chose the more damaged        45.9%      (so: mildly prefers the healthier)
  chose the faster              44.6%      (so: mildly prefers the slower)
  chose the more threatening    53.7%      (directionally right, very weak)
  chose the already boosted     57.1%      (the strongest signal found)
```

Everything is close to a coin flip. The threat hypothesis was *directionally* correct at 53.7% — and weighting it as though it were decisive is precisely why it did damage.

A separate check: do humans focus-fire? Over **709** turns where one player attacked with both slots and both opponents were alive, they aimed at the same target **48.1%** of the time. They do not. That agrees with 0011's refutation from the other direction — 0011 asked whether *scoring* combined damage helps, this asks whether humans do it at all.

## The number that reframes the item

Restricted to labels that are genuinely a choice — we picked the same move, the move is single-target, both opponents were alive, and the log recorded which one:

```
  TRAIN   3173/4096 = 77.5%
  TEST     754/946  = 79.7%
  chance             50%
```

The agent is already most of the way from chance to perfect. The remaining ~22% sits in a space where **no computable feature predicts the human's choice better than 57%** — which is what an irreducible residual looks like, not a gap.

## What this means for the backlog

Item "target selection" is closed as **mostly a ceiling**. It was the largest remaining *category* of disagreement, and it turns out most of that category is not addressable with the information available. Reporting it as "the largest gap" overstated it, and this correction matters more than the failed hypothesis does.

The one thread left unpulled is the boosted-opponent signal at 57.1% on 849 comparisons — the strongest of the four, and still weak. It is recorded rather than implemented, because implementing a 57% signal as though it were decisive is the exact mistake this experiment just made.
