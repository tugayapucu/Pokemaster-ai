# Experiment 0041 — The one-turn scorer prices delay correctly, and its scores are calibrated

**Date:** 2026-09-04
**Result: the hypothesis is dead, and something better turned up in its place.** A one-turn scorer was supposed to be structurally blind to moves that pay off over several turns — Reflect lasts five, Will-O-Wisp lasts the battle, Calm Mind is worth nothing on the turn it is used. Measured by rollout against a damage control, **the most unambiguously multi-turn class sits exactly on the floor** (−4.3% against −4.6%, p = 0.947). The one class that appeared to clear it turned out to be a single move and then an artefact. What survives is a positive finding nobody was looking for: **the scorer's score gaps predict real win-rate gaps, monotonically.**

## The hypothesis, and why it was worth a run rather than a build

0040 closed the status category as priced about right and then found the gap it was built to close does not exist: humans play non-damaging moves on 34.2% of move choices and this agent on 29.6%. The disagreement is over which one and when.

The leading explanation was structural, and it sounded obviously true. That is exactly why it got measured: this project has twice named a "largest gap" that was really a ceiling (0013's target selection, 0018's opponent knowledge).

## Method

0038's fork, pointed at a single slot. At 582 decision points across 380 battles, candidates were taken from the engine's own legal list and **differ in exactly one slot**, with the rest held at the agent's own choice, so a difference between two rollouts is attributable to one move rather than a pair. Each was rolled out fourteen times to the end. 1,633 candidates in all.

Regret is the candidate's true win rate minus the pick's. Candidates are chosen by our scorer, which never sees the rollouts that grade them, so nothing can be selected because it got lucky.

Payoff classes are read off dex fields rather than a hand-kept list. The control is `damage (now)`: those moves have no delayed payoff to miss, so their regret is the floor — the part that is simply the agent not being a perfect ranker, which 0038 measured at 57% best-of-four.

## The hypothesis dies

```
  payoff class                 n  mean regret   +- 1 se   we scored it
  other status                39        4.2%      3.5%           76
  boost (later turns)         46        1.1%      4.3%          107
  volatile (varies)          263       -3.7%      1.8%          119
  field (many turns)          50       -4.3%      4.7%          116
  damage (now)               642       -4.6%      1.2%          184  <-- control

  above the damage floor:
    other status        +8.8%   p = 0.016
    boost               +5.7%   p = 0.199
    volatile            +0.9%   p = 0.697
    field               +0.3%   p = 0.947
```

**`field (many turns)` is Reflect, Tailwind, Trick Room and Aurora Veil — the least ambiguous multi-turn moves in the format — and it sits on the floor.** So does `volatile`, on 263 candidates. If a one-turn scorer were blind to delayed payoff, these are the two classes where it would show, and it does not.

## And the one class that looked real was not

`other status` cleared the floor at p = 0.016, which does not survive a Bonferroni threshold of 0.0125 for four classes. Two further checks killed it outright.

**It is not a class.** Of its 39 candidates, 36 are Parting Shot, 2 Perish Song, 1 After You. A "category effect" that is one move is a move.

**And Parting Shot does not hold up.** Mean regret +4.6% on 36 sightings, but the sign test is **8 better, 8 worse, 20 tied — p = 1.000**. The mean is carried by magnitude on a handful of points, not by consistency.

**Then the score gap explains all of it.** The classes were never score-matched: `other status` alternatives were scored 76 below the pick and damage alternatives 184 below, so the first were near-ties the agent almost chose anyway and the second included many it rightly discarded. Comparing like for like:

```
  score gap            class                   n   mean regret
  near (<100 below)    other status           29         0.2%
  near (<100 below)    other non-damaging    166        -0.7%
  near (<100 below)    damage (now)          261        -0.5%

  like-for-like gap +0.7%,  p = 0.8472
```

Nothing. The effect was the confound, and the column that caught it was added before the run for exactly this reason.

## What survives, and it is the useful part

Regret tracks the score gap, in the direction and roughly the proportion it should:

```
  score gap            damage (now)     other non-damaging
  near (<100 below)         -0.5%              -0.7%
  mid  (100-250)            -4.3%              -5.8%
  far  (250+)               -9.8%              +0.6%   (n=22)
```

**An action the scorer puts slightly below its pick really is slightly worse; one it puts far below really is much worse.** That is not something any earlier experiment established. 0038 measured that the agent picks the best of four 57% of the time, which says the ordering is imperfect; this says the *magnitudes* mean something, and that they mean the same thing whether the move deals damage or not.

Which also removes the need to explain 0040's null. There is nothing to explain: the category is priced correctly, including the half of it that pays off later.

## Not established

- **Whether the scores are calibrated in absolute terms.** This shows the gaps are ordered and roughly proportional, not that a gap of 100 is worth a specific number of win-rate points. Nothing here fits that mapping.
- **The `far (250+)` non-damaging bucket, at +0.6% on 22 candidates**, is the one cell that does not fit the pattern. Too thin to interpret and worth a second look if this apparatus is ever re-run.
- **Whether any of it holds against an opponent that is not our own heuristic.** The rollouts play our agent on both sides. A move that is undervalued *because our opponent model fails to punish it* would be invisible here in exactly the way 0026 described, and `field` moves are the plausible candidate for that.
- Whether Parting Shot is priced right. It is not shown to be *wrong* — the claim retracted here is that it was shown to be wrong. On 36 sightings with a 50/50 sign test, it is simply unmeasured.
