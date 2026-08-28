# Experiment 0020 — What damage accuracy is actually worth in wins

**Date:** 2026-08-25
**Result: about a fifth of a point of win rate per point of damage accuracy.** Removing abilities — the single largest accuracy term this project has ever measured, worth **11.9 points** of prediction accuracy — costs only **2.7 points** of win rate (52.7%, 95% CI 50.2–55.1%, p = 0.032). Significant, and small.

That exchange rate prices every remaining engine-correctness item, and it prices the Mega gap out.

## Why this needed measuring

Every damage figure this project reports is "predictions inside a range". Nothing had ever shown that moving it is worth anything at the objective — and experiments 0018 and 0019 had just demonstrated, in one afternoon, how easily a carefully measured ceiling turns into no wins at all.

The sharpest available test is abilities, because they are the biggest accuracy term on record: fully random teams read **80.1%** before they were modelled and **92%** after. An agent that ignores them carries a materially worse damage model and nothing else different.

The comparison originally proposed — "this morning's agent versus today's" — does not work. Today's fixes live in shared modules that both sides of a head-to-head would import, and two versions of one package cannot be loaded in one process. Running across processes against Random hits a ceiling instead, since the heuristic already beats Random 96%+. Removing one term in-process is the honest equivalent, and a better-posed question besides.

## The measurement

```
paired head-to-head, teams exchanged, 800 battles x 2 seeds

  seed 1   410/800  = 51.2%   (95% CI 47.8%-54.7%)
  seed 7   433/800  = 54.1%   (95% CI 50.7%-57.6%)
  pooled   843/1600 = 52.7%   (95% CI 50.2%-55.1%)   z = 2.15, p = 0.032
```

```
11.9 points of damage accuracy  ->  2.7 points of win rate
1 point of damage accuracy      ->  ~0.23 points of win rate
```

**The true rate is lower than that.** Abilities do more than damage — `_known_ability` also feeds turn order through the weather Speed abilities, and the immunities. So `AbilityBlind` lost slightly more than damage accuracy alone, which makes 0.23 an over-estimate and the conclusion below stronger rather than weaker.

## What it prices out

```
closing the Mega gap (7.0 points of accuracy)      ~1.6 points of win rate
closing multi-hit moves                            ~0.1

for comparison:
  scoring the Mega forme -- a *decision* fix       +10.1  (measured, 0018-era)
  perfect opponent knowledge -- a ceiling           +4.3  (0018)
  inferring spreads from damage                     +0.8  (0019, null)
```

The Mega gap has survived five eliminated hypotheses and is the largest known defect in the damage model. Closing it **entirely** is worth about a point and a half, and after 0016 and 0017 what remains of it is a long tail rather than one bug.

## The conclusion, which is about the project rather than about Mega

**The engine-correctness direction has a poor exchange rate into wins, and it is now close to exhausted.** Damage is at 93.9% on the control arm, turn order 97.8%, the knockout claim 99.0%, and 161 of 176 status moves priced. What is left converts at roughly 0.2 points of win rate per point of accuracy.

The single largest agent improvement this project has ever measured was **+10.1 points, and it was not an accuracy fix at all** — it was noticing that the agent never Mega Evolved, because `action.special` was unread. A decision the agent was not making, rather than a number it was getting slightly wrong.

That is the pattern worth carrying forward: at this point, **what the agent chooses is worth more than what it knows.**

## What this does not say

- It does not say the damage work was wasted. An agent that cannot predict damage cannot choose well either, and everything here rests on it. It says the *remaining* accuracy is cheap to have and dear to buy.
- It does not measure accuracy against *human* opponents, only self-play. A stronger opponent might punish mispredictions harder.
- The exchange rate comes from one term. It is a first estimate of a slope, not a law.
