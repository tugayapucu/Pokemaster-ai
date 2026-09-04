# Experiment 0042 — A calibrated number, without the value model that was supposed to provide it

**Date:** 2026-09-04
**Result: the recommender now says what a choice costs, in win-rate points, and the number is measured rather than invented.** Three bands — level, about 5 points behind, about 10 points behind — held out by battle over eight random splits and **correctly ordered on all eight**. This is the number `PROJECT_PLAN.md` said would come from Milestone 7, which was measured and closed in 0035 and 0037, so on the plan's own terms it was never going to arrive.

## The number that was there before

The recommender has always shown a confidence beside each option:

```
  1. Basculegion: Wave Crash -> Farigiraf | Sneasler: switch to Farigiraf   19%
  2. Basculegion: Wave Crash -> Farigiraf | Sneasler: Fake Out -> Farigiraf  11%
```

It is a share of a softmax over scores, at a temperature of 12.0 that nobody has ever swept — which makes it the same shape as every constant this project has had to go back and measure. The plan was explicit that it is not a win probability, and equally explicit about the fix: *"A calibrated one comes from Milestone 7."*

Milestone 7 is the learned value model. 0035 measured its ceiling at about a point of headroom over a hand-written function, 0037 confirmed it with a richer feature set, and it was closed. **The stated route to an honest number had been removed, and the dishonest number stayed on screen.**

## The number that replaced it

0041 rolled out 1,633 candidate actions at 582 real decision points and found that the magnitude of a score gap predicts the real difference in win rate. That is the calibration, and it needs no value model — the scorer already produces the input.

Held out by battle, eight random splits:

```
  score gap from the top choice     mean      min      max
    under 60                       -0.7%    -4.1%    +1.2%
    60 to 250                      -4.7%    -6.6%    -2.8%
    250 and above                 -10.2%   -12.8%    -7.8%

  correctly ordered on 8 of 8 splits
```

Three bands, not a curve. The deciles between them are noise at this sample size: the middle of the range ran +2.1%, −1.3%, +0.5%, −3.1%, −3.5%, −7.8%, −2.0%, −3.5% with about 1.9 points of standard error each. **Offering a continuous mapping would be reporting the noise**, so this offers what replicated.

The displayed points are rounded to whole numbers for the same reason. A band whose held-out spread is −6.6% to −2.8% cannot honestly print "4.7".

## Where it refuses to answer

The two cases 0041 did not measure return nothing rather than a plausible-looking guess, because a number beside a move is read as authoritative and an unmeasured one is indistinguishable from a measured one on screen.

**A difference spread across both slots.** 0041 varied exactly one slot at a time. Two slots is a sum of two effects nobody has checked adds up. That matters less than it might: measured over 1,313 shortlist entries, **94.2% differ from the top choice in a single slot**, so the refusal costs almost nothing.

**An action the scorer ranked above its own pick.** The joint scorer can produce this — a slot action can score higher on its own while the pair scores worse, because the joint score carries a targeting-overlap term. It was 7% of 0041's candidates and is also unmeasured.

## What it changes on screen

```
  1. Basculegion: Wave Crash -> Farigiraf | Sneasler: switch to Farigiraf
       top choice
  2. Basculegion: Wave Crash -> Farigiraf | Sneasler: Fake Out -> Farigiraf
       about level with the top choice
```

The old display put 19% against 11% and made the top choice look meaningfully better. It is not: on this position all four shortlisted options are inside the band where rollouts find no difference. **The honest number says the decision does not matter much, which the invented one hid.**

## Not established

- **Whether the calibration holds against an opponent that is not this agent.** The rollouts play our heuristic on both sides, so the cost is what a choice is worth *against an opponent like us*. 0026's caution applies to any mechanic we systematically under-use.
- **Whether the bands hold at their edges.** A gap of 59 and a gap of 61 are reported differently and are certainly not different. The boundaries are where the data was cut, not joints the game has.
- **Whether the mapping is stable as the agent changes.** It is calibrated against the shipped scorer, so a change to that scorer invalidates it. Nothing currently notices if it drifts, which is a defect waiting to happen and is recorded rather than solved.
- The softmax confidence is still computed and still on `Recommendation`, because `is_clear` uses it. That is now the last unswept constant in the recommender.
