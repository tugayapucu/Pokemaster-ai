# 0058 — Empty move slots now come from usage, corrected for what replays reveal

Run 2026-09-14 against the pre-registration in this directory, which was
committed and pushed (`19eb4d8`) before any arm was measured.

## What was built

| commit | what |
| --- | --- |
| `fc49f94` | usage distributions carry move weights and whole-set weight; `carry_rates`, `sample_moves` (plain and corrected) |
| `4f74865` | `move_fill` on `build_set` / `harvest_teams` / `harvested_pool`; the default rebuilds 0057's pool byte for byte |

## Results

| arm | validated | survival | weighted move distance |
| --- | --- | --- | --- |
| baseline (0057 pool) | 5,851 of 5,964 | 98.1% | 0.196 |
| plain | 5,857 of 5,964 | 98.2% | 0.098 |
| **corrected** | 5,852 of 5,964 | 98.1% | **0.069** |

Move distance is total variation over move slots against the truth source,
weighted by pool appearances; 0 is identical.

A sample of the most-drawn species — carry rate, truth / baseline / plain /
corrected:

| species | move | truth | baseline | plain | corrected |
| --- | --- | --- | --- | --- | --- |
| Kingambit | Protect | 69% | **98%** | 71% | 72% |
| Sneasler | Dire Claw | 73% | **99%** | 74% | 73% |
| Salamence | Draco Meteor | 59% | **11%** | 53% | 59% |
| Indeedee-F | Helping Hand | 71% | **99%** | 68% | 70% |
| Golisopod | Leech Life | 69% | **99%** | 74% | 69% |
| Basculegion | Protect | 54% | **82%** | 66% | 63% |
| Sinistcha | Trick Room | 65% | **96%** | 68% | 69% |
| Rillaboom | Fake Out | 100% | 100% | 91% | **93%** |
| Pelipper | Hurricane | 97% | 99% | 87% | **90%** |

Per-species distance, baseline → corrected: Rillaboom 0.08 → 0.05, Sneasler
0.14 → 0.06, Salamence 0.16 → 0.04, Kingambit 0.12 → 0.04, Golisopod 0.18 →
0.05, Sinistcha 0.13 → 0.05. Corrected is lowest for every species printed.

Pool team 0 scouted at seed 0:

| against | record |
| --- | --- |
| baseline | 92 / 240 — 38.3% |
| plain | 120 / 240 — 50.0% |
| corrected | 106 / 240 — 44.2% |

## The decision

**Corrected is the candidate** (0.069 against plain's 0.098), and **the rule is
met**: survival 98.1% is above 90% and level with baseline's, and its distance
is below baseline's 0.196. The corrected pool is written to
`data/pool-champions.txt`; the 0057 pool is kept as
`data/pool-champions-pre0058.txt`. Both are local and gitignored.

## Against the predictions

| prediction | result |
| --- | --- |
| baseline move distance 0.10–0.25 | ✓ 0.196 |
| plain below baseline | ✓ 0.098 |
| corrected below plain | ✓ 0.069 |
| plain overshoots most on the moves revealed most | ✗ — see below |
| survival within 2 points of baseline | ✓ within 0.1 |
| pool team 0's scout moves by under 5 points | ✗ +5.9 corrected, +11.7 plain |

## What the misses say

**The mode fill's error was not mainly inflation of the top move.** It was
committing every set to the same *second* tier: Kingambit's Protect, Sneasler's
Dire Claw and Indeedee-F's Helping Hand on nearly every set where real players
split, and the alternatives — Salamence's Draco Meteor, carried by 59% — almost
never. That is what 0.196 → 0.069 removes.

**Plain did not overshoot the most-revealed moves; both fills undershoot the
near-universal ones.** Moves on 97–100% of real sets land at 85–93%. Drawing
slots in proportion to weight does not give each move an *inclusion*
probability equal to its rate: when several slots are drawn without
replacement, high-weight moves are included less often than their weight, and
a partial set with a move the truth never lists spends a slot on it. Corrected
recovers a few points of that because it zeroes out what the partial set
already covers. Recorded as the remaining move defect, not fixed here.

**The scout moved more than predicted, and upward.** Opponents whose sets split
the way real ones do are less uniform, and the reference team did better
against them. Not a criterion; recorded.

**A wording error in the pre-registration.** It called the reference "the same
team as 0057's reference". It is the same six species, but 0057 drew it from the
old-method pool and here it comes from the usage pool, with usage-drawn items
and spreads. That is why baseline here reads 92 / 240 where 0057's new-pool
scout read 81 / 240. The scout is not a criterion, so the decision is untouched.

## What this does not change

- The agent's own beliefs about opponent sets. This changes the teams it plays
  against, not what it assumes about them.
- Species with no usage source (4.1% of pool Pokemon) keep the mode fill.

## Hygiene

Pool teams and synthetic fixtures only. The usage file, the open-sheet
distributions and the pools stay local under gitignored paths.
