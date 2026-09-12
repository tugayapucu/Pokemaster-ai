# 0056 — How much of a denied hit should speed be worth?

**Written before any measurement was run.** Registered 2026-09-13.

## Why this exists

0055 valued moving first over a race of any length: the faster side denies the
slower side's hit whenever it needs no more hits to finish. Measured, it was
negative in direction (385/415 over 800 battles, 133 matchups decided) and a
magnitude check showed why — the speed edge outweighed the whole damage trade
in 35% of pairings. The derivation fits a clean two-Pokemon race; doubles
rarely runs one to the end.

The natural fix is to credit only **part** of the denied hit. 0055's write-up
refused to try that on its own battles, because choosing a discount after seeing
a result and re-measuring on the same battles is tuning against the measurement.
This is that experiment, set up properly.

## The knob

`speed_race_credit` in [0, 1]: the share of the denied hit credited in races
longer than one hit. One-hit races keep the knockout-chance rule at every value.
0 reproduces the one-hit rule exactly; 1 is 0055's rule.

## Arms

Every arm is `speed_beyond_knockouts` on, at one credit, against the shipped agent
(flag off):

| arm | credit | role |
| --- | --- | --- |
| A | 0.25 | candidate |
| B | 0.50 | candidate |
| C | 0.75 | candidate |
| D | 1.00 | **control**: 0055's rule on fresh battles — does its negative replicate? |

## Fresh battles

0055 used seed 0. Every arm here uses **seed 1**, for both the matchup draw and
the battle seeds, so no arm is judged on battles that informed the design.

## Multiple comparisons

Four arms, each at 95%, give roughly a one-in-five chance that some arm clears
by luck alone. So the bar is **Bonferroni-adjusted**: an arm counts as clearing
only if its Wilson interval at **98.75%** (z ≈ 2.50) excludes 50%. The 95%
interval is reported alongside.

## Per arm, reported in full

| | |
| --- | --- |
| Team Preview picks differ, 40 random teams | |
| battle decisions differ, 20 random matchups | |
| A/B, **800 battles**, seed 1: record, 95% and 98.75% Wilson | |
| matchups decided | so an even record is read correctly the first time |
| magnitude over 32,400 pool pairings: median edge, share above a neutral hit (0.224), share above the whole damage trade, verdict flips | so a winning arm must also be a sane size |

No must-be-0 row, for 0055's reason: speed enters nearly every matchup.

## Predictions

| | prediction |
| --- | --- |
| magnitude | shrinks roughly in proportion to the credit: share above the damage trade near 10%, 20%, 28% for A, B, C |
| picks differ | rises with the credit, all above 40% |
| D (control) | negative in direction again, within ±3 points of 0055's 48.1% |
| A, B, C | neutral; **none expected to clear the adjusted bar** |

## Decision rule

- **At most one arm is turned on**: the one with the highest win rate, and only if
  its 98.75% interval clears 50% upward.
- If none clears, `speed_beyond_knockouts` stays off, every number is recorded,
  and speed pricing is not revisited before Frankfurt.
- If D clears *upward*, 0055 did not replicate; that is reported as the main
  finding, and nothing is turned on without a further run.

## Hygiene

Pool teams and synthetic fixtures only.
