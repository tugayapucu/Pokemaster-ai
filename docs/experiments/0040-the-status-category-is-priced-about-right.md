# Experiment 0040 — The status category is priced about right, and the gap is not where it looked

**Date:** 2026-09-04
**Result: sweeping how far the status scorer is trusted finds a clean peak at the value already shipped.** Every alternative loses, four of five significantly, and the curve is an inverted U — 26.5% at scale 0, 39.0% at 0.5, 44.9% at 2, 34.1% at 4, 15.3% at 8. **But the question it was built to answer turned out to be the wrong one.** Low per-move agreement is not a difference in usage: humans play non-damaging moves on 34.2% of move choices and this agent on 29.6%, flat across every rating band the corpus covers. The disagreement is over *which* status move and *when* — which a single scalar cannot move, and which this experiment therefore does not test.

## Where the question came from

`review --all`, added the same day, walks all 1,769 replays and reports where the human's action sat in our shortlist. The disagreement it found was not a move but a category:

```
  Charm 3%     Disable 4%     Hypnosis 4%     Will-O-Wisp 4%
  Reflect 5%   Substitute 6%  Roost 8%        Calm Mind 8%
  Swords Dance 8%   Yawn 8%   Parting Shot 8%
```

on 44 to 449 plays each, consistently across setup, recovery, screens, status, disruption and pivoting.

**Corrected after publication — this paragraph originally read "humans reach for non-damaging moves far more often than this agent ranks them", and that is not true.** Low per-move agreement is not the same as a difference in how often the category is used, and the aggregate rates are close:

```
  status share of move choices
    humans, 1500-1599    34.1%   n=20029
    humans, 1600-1699    34.5%   n=11918
    humans, 1700-1827    33.6%   n= 2503
    humans overall       34.2%
    this agent           29.6%
```

**A 4.6 point gap, not a chasm** — and flat across the whole rating range the corpus covers. So the disagreement is not *how much* status to use. It is **which one, and when**, which is a different claim and the one the rest of this experiment fails to test.

## Why it was worth re-opening

The closest existing measurement is `tenure_boosts`, which 0023 and 0025 put at +0.9 points, p = 0.48, and left off by default. **It is a boolean.** Two settings is the exact shape 0032 warned about: switching was called a null three times, by three experiments that each sampled a single horizon, and the answer changed sign the moment somebody swept it.

So `status_scale` was added as a scalar on the non-damaging branch — the one place all eleven of those moves are priced — and both of 0033's preconditions were checked before any number was read.

**Per-agent**, so a head-to-head does not silently compare an agent with itself and tie every matchup. And the range **bites**, measured rather than assumed:

```
  status_scale   0.0    0.5    1.0    2.0    4.0    8.0
  status moves   0.0%  15.7%  29.6%  39.7%  47.4%  54.1%
```

## The sweep

Frozen 200-team pool, 800 battles per scale, paired with teams exchanged and common random numbers, against the shipped 1.0. The mirror check passed first: an agent tied every matchup against a copy of itself.

```
  scale         paired            95% CI          p      tied
  0.0        30/113   26.5%   19.3%-35.4%    0.0000      286
  0.5        39/100   39.0%   30.0%-48.8%    0.0278      299
  2.0        40/89    44.9%   35.0%-55.3%    0.3401      310
  4.0        45/132   34.1%   26.6%-42.5%    0.0003      267
  8.0        29/189   15.3%   10.9%-21.2%    0.0000      210
```

**Nothing leads, so nothing is confirmed.** 0036 ran a pre-registered confirmation because a scale led its sweep and the leader had to be tested on fresh seeds before being believed. Here there is no positive claim to test: every alternative is at or below even, and the shipped value sits at the top of an inverted U.

The shape matters as much as the significance. Turning status off entirely costs 23 points, so the scorer is doing real work. Doubling its weight costs about 5 and is not distinguishable from noise. Beyond that it falls away fast. That is a broad peak containing the shipped value, not a knife edge somebody guessed correctly.

## What it says about agreement

0010 found Trick Room's fitted value climbing without bound because a team that brings it nearly always uses it. 0013 found target selection looked like the largest gap in the project when humans are near-random on it. Both were single judgements, and both were cases where agreement pointed somewhere the win rate did not.

This looked like a third and larger instance, and the first draft of this write-up called it one. **It is not.** Agreement remains a ranking signal rather than a target, and pushing the category's price in either direction is measurably worse — but that is a much narrower claim than the one the low agreement figures seemed to invite.

**But "humans over-use status" is not what this shows**, and the usage table above is why: at 34.2% against our 29.6%, they barely use it more at all. What the sweep rules out is that the category is *uniformly* underpriced. It says nothing about the disagreement that actually exists, which is over selection and timing inside a category we already reach for about as often as they do.

**A scalar was the wrong instrument for the gap that was found.** It can only move all eleven moves together, and the evidence says they do not need moving together.

## Not established

- **Whether individual moves in the category are mispriced.** A scalar moves all eleven together, so a category priced correctly on average can still contain moves that are individually wrong in opposite directions. Parting Shot at 449 plays and 8% agreement is the obvious candidate to price on its own.
- **Whether a different opponent would punish or reward status differently.** This is self-play: the status-keen agent does use the moves, so the mechanic is exercised and 0026's blindness does not apply in its strict form — but whether *our* agent punishes an opponent's setup correctly is a separate question this does not touch.
- **Whether a one-turn scorer can price a multi-turn move at all.** Reflect lasts five turns, Will-O-Wisp halves physical damage for the rest of the battle, Calm Mind pays off only on subsequent turns. The scorer is explicitly one-turn, and scaling a price that cannot see the payoff amplifies a number rather than correcting it. This is the strongest untested explanation for the null and it is not addressed here.
- **Whether any of this holds above 1827.** The corpus tops out there with a median of 1585, and usage is flat across it — but flat over 300 Elo points is no evidence about championship play, where the observation prompting this note is that status moves are used heavily. The corpus cannot answer that question, and a corpus that could would have to be collected from a different population.
- Whether the peak sits exactly at 1.0. Scale 2.0 is 44.9% with p = 0.34, so anything between roughly 1 and 2 is indistinguishable here. The claim is that the shipped value is inside the peak, not that it is the argmax.
