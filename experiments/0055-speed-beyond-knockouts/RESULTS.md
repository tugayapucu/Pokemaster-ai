# 0055 — Speed beyond knockouts: a real measurement, pointing the wrong way

Run 2026-09-13 against the pre-registration in this directory.

## What was built

| commit | what |
| --- | --- |
| `1243369` | `order_edge` and `hits_to_knock_out`: moving first valued over a race of any length; off is the old rule exactly |
| `ece7df5` | `speed_beyond_knockouts` wired into Team Preview and switch scoring, off by default |

## The measurement

| | | pre-registered |
| --- | --- | --- |
| Team Preview picks differ, 40 random teams | 1,256 of 1,560 — **81%** | 20–60% ✗ |
| battle decisions differ, 20 random matchups | 25 of 370 — **6.8%** | 1–6% ✗ |
| speed-beyond-ko vs one-hit, 800 battles | **385 / 415 — 48.1%** | neutral to positive ✗ |
| 95% Wilson | [44.7%, 51.6%] | |
| matchups decided | **133 of 400** | |

Unlike 0054's even records, this one measured something: a third of the
matchups were decided. The direction is **negative**. It does not clear its
interval downward, but it is the opposite of what was predicted.

**By the stopping rule, `speed_beyond_knockouts` stays off.**

## Why — measured before the A/B finished

While the battles ran, the new rule's size was checked across 32,400 pairings
of 180 pool sets against 180 pool species:

| | one-hit rule | race of any length |
| --- | --- | --- |
| median speed edge | 0.000 | **0.152** of HP |
| speed edge larger than a typical neutral hit (0.224) | 6% | **43%** |
| speed edge larger than the whole damage trade | 3% | **35%** |
| pairings whose verdict flips | — | 10% |

In a third of pairings, being faster now outweighs everything either side does
to the other. `matchup.py` already carries a warning about this shape: a flat
speed bonus once beat a doubled type advantage on 78% of hits, which is not how
the format plays. This rule is milder and still leans the same way.

The derivation holds for a clean race between two Pokemon. Doubles rarely runs
one — switching, Protect, partners and spread moves all interrupt it — and
pricing a whole denied hit assumes the race runs to the end.

## The pick counts overshot, and that fits

81% of previews changed their pick, far above the band. A term that outweighs
the damage trade in a third of pairings reorders most candidate fours. The
overshoot is the same fact as the magnitude table, seen from Team Preview.

## Not done, and why

The obvious next step is a **discounted** denied hit — some fraction of it,
standing in for how often a race actually runs to the end. That was
deliberately **not** tried here: changing the rule after seeing this result and
re-measuring on the same battles would be tuning against the measurement.

It is recorded as a proposal. If taken up, it is a separate, pre-registered
sweep over several discounts on fresh seeds, with the magnitude table above
reported for each.

## Hygiene

Pool teams and synthetic fixtures only.
