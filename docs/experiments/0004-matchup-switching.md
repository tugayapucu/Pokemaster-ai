# Experiment 0004 — Switching on the matchup, and two metrics that disagree

**Date:** 2026-08-20
**Git commit:** see `git log` for the `feat(agents): switch on the matchup` commit
**Result: the headline finding is not about switching.** Human agreement says the change is significantly **worse**. Play strength says it is significantly **better**. Both were measured properly, and they point in opposite directions.

## Hypothesis

Experiment 0002 found the largest behavioural gap in the agent: rated humans
switch on **10.7%** of decisions and `heuristic-v1` on **1.8%**, agreeing on 11
of 117 switch labels. The cause was structural — switching scored a flat −25
with a bonus when weakened, so it was almost never worth a turn.

Pricing a switch by **the matchup it buys**, minus the turn and the free hit it
costs, should close that gap.

## Change

```
value = (incoming_matchup − current_matchup) × SWITCH_HORIZON
        − forgone_attack
        + bonus if staying in would be knocked out
```

The matchup comes from `mechanics/matchup.py`, the same function Team Preview
uses, now given the engine's computed stats, current HP on both sides, and
whichever opponent moves have actually been revealed.

`SWITCH_HORIZON` was calibrated to the **human switch rate**, not to the
agreement score: at 1.0 the agent switches on 11.0% of decisions against a human
10.7%. Fitting it to agreement would have been fitting it to the thing this
experiment goes on to show is the wrong target.

## Result 1 — human agreement got worse

```
flat-switch     476/1091 = 43.6%
matchup-switch  438/1091 = 40.1%     (at the uncalibrated first attempt)
                455/1091 = 41.7%     (at the calibrated rate)

only OLD agreed 69   only NEW agreed 31
McNemar chi2 = 13.69 — significant at p<0.01, against the change
```

Switch labels specifically improved a great deal — 11 → 38 of 117 — but every
gain there was outweighed by losses on move turns. A parameter sweep confirmed
this is not a tuning artefact: **at every setting tried, overall agreement was
below the flat baseline.**

| horizon | KO bonus | switch rate | agreement | switch labels |
|---|---|---|---|---|
| 0.50 | 0 | 5.6% | 42.3% | 16/117 |
| 1.00 | 35 | **11.0%** | 41.7% | 31/117 |
| 1.50 | 70 | 15.7% | 40.1% | 38/117 |

Matching the human switch *rate* does not mean switching on the *same turns*.

## Result 2 — play strength got better

```
matchup-switch vs flat-switch:  354-246 over 600 battles
win rate 59.0% (95% CI 55.0%-62.9%, significant), ahead in 32/56 matchups

matchup-switch vs random: 190-10 = 95.0%
flat-switch    vs random: 191-9  = 95.5%
```

Significant over 600 battles, and spread across matchups rather than
concentrated in a few favourable pairings.

## The finding

**The two instruments disagree, both significantly, in opposite directions.**
This is the first time that has happened in this project, and it is worth more
than the switching change itself.

Agreement was built with the caveat stated in its own module docstring —
*"it rewards imitating the reference player, so a genuinely better move counts
as a miss"*. Until now that was a disclaimer. It is now a measurement.

The reconciliation is not that either metric is broken:

- **Agreement is a proxy for reasoning like a competent player.** Our sample is
  Elo 1500–1782, median 1589 — competent, not optimal. Humans switch on
  particular turns for reasons the agent cannot see: predicting an opposing
  switch, preserving a Pokémon for a later matchup, positioning for Trick Room.
  Our agent switches on *different* turns, and agreement scores every one of
  those as a miss whether or not it was right.
- **Head-to-head is a direct measure of the thing we want**, but only against
  one specific opponent, and it was blind to the Protect change in experiment
  0003 that agreement caught at p<0.01.

Neither dominates. They measure different things and both are worth keeping.

## Decision

**Kept.** Play strength is the goal; agreement is a proxy for it. When a proxy
and the thing it proxies for disagree at significance, the thing wins.

This inverts the rule experiment 0003 proposed — "use self-play to confirm no
regression, and agreement to detect improvement". The corrected rule:

- **Agreement is the more sensitive instrument for scoring changes**, which
  0003 demonstrated by detecting at p<0.01 what 800 battles could not.
- **Head-to-head is the arbiter when they conflict**, because it measures the
  objective rather than a stand-in for it.
- **A change that moves them in opposite directions is interesting, not
  broken**, and should be recorded rather than resolved by dropping whichever
  result is inconvenient.

## Next actions

- Re-run both metrics on any change touching switching, and expect them to
  diverge again.
- The agreement drop is concentrated on **move** turns where the agent now
  switches instead. Worth inspecting directly: some of those are likely genuine
  errors rather than the agent knowing better, and separating the two would
  sharpen both metrics.
- Collect more replays. At 1,091 labels the agreement interval is ±3 points;
  the switch subset is only 117 labels and carries far more noise than the
  headline suggests.
