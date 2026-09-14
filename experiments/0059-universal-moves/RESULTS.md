# 0059 — Near-universal moves are back on the sets that carry them

Run 2026-09-14 against the pre-registration in this directory, which was
committed and pushed (`6dac88e`) before either arm was measured.

## What was built

| commit | what |
| --- | --- |
| `568e490` | `sample_moves(by_inclusion=True)`: slots picked by conditional Poisson sampling |
| `b56cb87` | `move_fill="inclusion"` in the harvest; "corrected" and the default unchanged |

## Results

| | corrected (0058 pool) | inclusion |
| --- | --- | --- |
| validated | 5,852 of 5,964 — 98.1% | 5,852 of 5,964 — 98.1% |
| **weighted move distance** | 0.069 | **0.053** |
| near-universal carry (moves on 95%+ of real sets) | 89.9% | **98.6%** |
| mid-rate moves (40–80% real), mean pool minus truth | −0.2 points | +1.1 points |

A sample of the most-drawn species — carry rate, truth / corrected / inclusion:

| species | move | truth | corrected | inclusion |
| --- | --- | --- | --- | --- |
| Rillaboom | Fake Out | 100% | 93% | **100%** |
| Sneasler | Close Combat | 99% | 88% | **99%** |
| Kingambit | Sucker Punch | 99% | 89% | **99%** |
| Basculegion | Last Respects | 100% | 90% | **100%** |
| Indeedee-F | Follow Me | 100% | 91% | **100%** |
| Salamence | Protect | 95% | 84% | **96%** |
| Sinistcha | Rage Powder | 96% | 88% | **96%** |
| Kingambit | Iron Head | 66% | 68% | 72% |
| Indeedee-F | Helping Hand | 71% | 70% | 75% |

Per-species distance, corrected → inclusion: Rillaboom 0.053 → 0.034,
Sneasler 0.062 → 0.035, Basculegion 0.055 → 0.016, Kingambit 0.043 → 0.030,
Golisopod 0.053 → 0.041, Pelipper 0.036 → 0.033. Inclusion is lower for every
species printed.

Pool team 0 of the corrected arm, scouted at seed 0:

| against | record |
| --- | --- |
| corrected | 125 / 240 — 52.1% |
| inclusion | 138 / 240 — 57.5% |

## The decision

**The rule is met.** Survival is identical at 98.1%, and the weighted move
distance fell from 0.069 to 0.053. The inclusion pool is written to
`data/pool-champions.txt`; the 0058 pool is kept as
`data/pool-champions-pre0059.txt`. Both local and gitignored.

## Against the predictions

| prediction | result |
| --- | --- |
| near-universal carry, corrected, 88–93% | ✓ 89.9% |
| near-universal carry, inclusion, 96% or higher | ✓ 98.6% |
| distance below corrected's, by less than 0.02 | ✓ 0.016 |
| mid-rate moves a few points higher than corrected | ✗ **1.3 points** — smaller than feared |
| survival within 2 points | ✓ identical |
| reference scout moves by under 5 points | ✗ +5.4 |

## Reading it

**The defect 0058 recorded is gone.** Moves on 95%+ of real sets went from
89.9% to 98.6%, and the cost the pre-registration worried about — conditional
Poisson sampling pushing mid-rate moves up — came to about a point. The second
tier drifts up slightly where the top is certain (Kingambit's Iron Head 66% →
72%), because a set that no longer loses a slot to the wrong move has one more
slot for the next.

**The reference is not 0058's.** As pre-registered, it is pool team 0 of the
corrected arm — the same six species as 0057 and 0058, with this arm's moves —
so its 125 / 240 is not comparable with 0058's 106 / 240. The scout is not a
criterion.

## What is left in the pool

Nothing named. Items, natures, spreads and moves are drawn from sources that
see whole sets for the 95.9% of pool Pokemon that have one; the other 4.1% keep
the replay-revealed fallback. Remaining limits are the sources: Smogon's file is
Reg M-B, not M-C, and open sheets cover 21 species.

## Hygiene

Pool teams and synthetic fixtures only. The usage file, open-sheet distributions
and pools stay local under gitignored paths.
