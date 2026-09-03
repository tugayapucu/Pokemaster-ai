# Experiment 0033 — Redirection, priced and swept, still loses

**Date:** 2026-09-03
**Result: pricing redirection makes the agent worse at every weight that changes a decision — 23.5% to 26.7% on the matchups it moves, all p < 0.05 — and the whole mechanic is capped at about a point of win rate regardless.** 0026 called it a null from a strawman test; 0032's lesson said sweep the price before believing that. Swept, it is not a null but a loss. Ships at weight zero, which means unchanged.

## Why it was worth re-opening

0026 measured two things: how often *our* attacks get diverted (2.0%, against an opponent redirecting at every legal opportunity), and what happens when an opponent is forced to redirect constantly. Neither is the question that matters for our own play.

**What a redirect is worth when we choose one had never been priced.** With a living partner it collected the flat unknown-support value. A flat constant standing in for a trade is exactly what 0032 found wrong with switching, where the curve crossed even between two settings nobody had tried.

## The price

Redirection moves damage rather than removing it, so the value is the difference in what the hit costs. Both `_incoming_threat` figures are fractions of their own bearer's health bar, which is what makes the subtraction mean anything: an attack taking 60% of a frail partner and 30% of a bulky redirector converts a 60% loss into a 30% one, and a partner that would faint into one that does not.

```
score = (theirs - ours) * weight * DAMAGE_WEIGHT  -  forgone_attack * DAMAGE_WEIGHT
```

The second term was missing from the first attempt, and adding it was the one legitimate correction this got. Every other turn-consuming move here charges for the turn — Protect has `PROTECT_TEMPO_COST`, the switch scorer subtracts the forgone attack — and leaving it out priced the benefit and none of the cost.

## The result

```
paired over the matchups the two agents actually decided differently

                    without tempo cost        with tempo cost
  weight  4.0    7/21 = 33.3%  p = 0.13     4/17 = 23.5%  p = 0.029
  weight  8.0    4/22 = 18.2%  p = 0.003    5/20 = 25.0%  p = 0.025
  weight 16.0    7/28 = 25.0%  p = 0.008    6/25 = 24.0%  p = 0.009
  weight 32.0    8/31 = 25.8%  p = 0.007    8/30 = 26.7%  p = 0.011

  mirror control              798 tied, none split
```

Negative everywhere, with and without the correction. A stopping rule was written down before the second run — *if the tempo-corrected version is not positive, redirection is closed* — and it fires.

**The two statistics disagree, and that is the point.** The pooled win rate sits at 49.1-49.4% and reads as nothing at all; the paired figure says that when the pricing changes a decision, it is clearly the wrong decision. Only ~3% of matchups are touched, so a real effect on the mechanic hides inside a nothing-sized effect on the match.

## Two bugs in this measurement, both mine

**A module global faked a null.** `REDIRECT_WEIGHT` was read by whichever agent was scoring, so setting it made *both* sides of the head-to-head priced. Every weight tied every matchup — which reads exactly like a null and would have been written up as one. The tell was that a separate diagnostic had already shown the weight moving redirect usage from 1.9% to 12.2%: two measurements disagreeing is a bug, not a result. `redirect_weight` now sits on the agent, the shape `matchup_switching` already had, which is why the switching sweep worked and this one did not.

**The first sweep swept a range where nothing happens.** Weights 0.5 to 2.0 leave usage at 1.9%; the parameter does not bite until 4. A sweep across a range the parameter does not move is a sweep of nothing — the same error as testing a single point, wearing a different hat.

## What this settles

- **Redirection is closed.** Not neutral, as 0026 had it, but actively worse when priced this way — and capped at roughly a point of win rate even if some other pricing worked, because it only reaches 3% of matchups.
- **The agent's near-zero use of Rage Powder is correct**, and now for a reason rather than by accident.
- **"Sweep it" is not sufficient on its own.** It has to be a sweep across a range where the parameter changes behaviour, and between agents that actually differ. Both checks are cheap and both were needed here.

## Not established

- Whether a different pricing works. This tests damage-moved, with and without a tempo cost. The obvious missing term is *what the partner does with the turn it is given* — redirection in real play protects a setup sweeper or a Trick Room setter, and the value is in what they get to do, not in the damage arithmetic.
- Whether the small ceiling would grow against an opponent that punishes an unprotected partner harder than this heuristic does. 0026's blind spot applies.
