# 0057 — The pool now carries what sets actually carry

Run 2026-09-14 against the pre-registration in this directory, which was
committed and pushed (`858b418`) before the rebuild was measured.

## What was built

| commit | what |
| --- | --- |
| `72dcfdb` | `data.usage`: Smogon chaos files and open team sheets read into per-species item, nature and spread distributions; `harvest.build_set(usage=...)` draws from them, and a harvest without `usage` is unchanged |

## The sources

| | |
| --- | --- |
| train split | 2,990 M-C replays of 3,750 |
| Smogon, Reg M-B, 1500+, August 2026 | 233 species |
| open team sheets in the train split, 20+ sheets | 21 species |

## Results

| | old method | with usage |
| --- | --- | --- |
| teams assembled | 5,964 | 5,964 |
| teams the engine validates | 5,858 — **98.2%** | 5,851 — **98.1%** |
| weighted item distance to the truth source | **0.569** | **0.083** |

Total variation distance: 0 is identical, 1 is nothing in common. Weighted by
how often each species appears in the pool.

Coverage of the new pool's 35,106 Pokemon:

| source | Pokemon | share |
| --- | --- | --- |
| Smogon | 26,669 | 76.0% |
| open team sheets | 7,002 | 19.9% |
| fallback (old method) | 1,435 | 4.1% |

A sample of the most-drawn species:

| species | source | pool sets | old | new |
| --- | --- | --- | --- | --- |
| Rillaboom | open sheets | 2,323 | 0.80 | 0.04 |
| Sneasler | Smogon | 2,168 | 0.97 | 0.08 |
| Salamence | open sheets | 1,506 | 0.04 | 0.01 |
| Kingambit | Smogon | 1,385 | 0.60 | 0.07 |
| Basculegion | Smogon | 1,340 | 0.80 | 0.09 |
| Golisopod | open sheets | 1,305 | 0.00 | 0.00 |
| Indeedee-F | open sheets | 1,303 | 0.64 | 0.03 |
| Pelipper | Smogon | 944 | 0.31 | 0.09 |
| Sinistcha | Smogon | 683 | 0.45 | 0.11 |

The new distance is not zero because it is a draw, not a copy: a thousand-odd
sets drawn from a distribution land a few points off it, and Item Clause removes
an item a teammate already holds.

The reference team (pool team 0, built by the old method) scouted at seed 0:

| against | measuring run | `--write` run |
| --- | --- | --- |
| old pool | 127 / 240 — 52.9% | 127 / 240 — 52.9% |
| new pool | **81 / 240 — 33.8%** | **79 / 240 — 32.9%** |

The `--write` run rebuilt both pools from scratch and reproduced every assembly,
coverage and distance figure exactly, yet the new-pool scout came out two wins
lower on the same seed. **A scout is not bit-reproducible across processes**
on the new pool; the cause is not yet known. Two wins in 240 does not move the
reading, but a paired scout that differs by two wins should not be over-read.

As a consistency check on the written pool: 8,437 of its 35,106 Pokemon still
carry even 11s, which is exactly the open-sheet plus fallback count — the only
sources without Stat Points.

## The decision

**The adoption rule is met.** Survival 98.1% is above 90% and 0.1 points from
the old method's; the weighted item distance fell from 0.569 to 0.083. The new
pool is written to `data/pool-champions.txt` and the old one is kept beside it
as `data/pool-champions-pre0057.txt`. Both are local and gitignored.

## Against the predictions

| prediction | result |
| --- | --- |
| coverage ~77% Smogon, 10–20% open sheets, under 15% fallback | ✓ 76.0 / 19.9 / 4.1% |
| engine survival within 3 points of the old method's | ✓ 0.1 points |
| weighted item distance: old above 0.4, new under 0.15 | ✓ 0.569 → 0.083 |
| reference team's scout result moves by 2–10 points | ✗ **19.1 points** (20.0 on the repeat) |

## Reading the scout shift

The miss is the finding. It is larger than predicted, and it is not only
"opponents got stronger":

- **The reference team was built by the old method.** Even 11 Stat Points and
  noise-selected items, now facing opponents with invested spreads and the items
  that never announce themselves — Life Orbs, Focus Sashes, White Herbs. Part of
  the drop is that team being badly built, which the old pool could not show
  because every opponent was built the same way.
- **The two scouts are not paired.** Same seed, but different pools draw
  different opponents, so the 19.1 points carries opponent-draw noise on top.
  One team, 240 battles: the size is uncertain; the direction is not in doubt.

The consequence runs the other way for a team built properly. A real team
scouted against the old pool was facing opponents built worse than real ones,
so **every scout result before 0057 is likely flattering**, and by an amount
that differs team to team.

## What this does not change

- **Paired A/Bs before 0057 stand as comparisons.** Both agents met the same
  pool, so an A/B's direction is not biased by a pool both sides shared. Their
  levels, and any effect that depends on what opponents carry, were measured on
  the old pool.
- **Moves are still imputed.** Each set is still filled to four moves from the
  species' most common revealed moves — the separate, already-recorded
  mode-inflation defect, about 6–10 points on well-sampled moves. Chaos files
  carry move rates too; that is the natural follow-up and is not done here.
- **Opponent spread beliefs in the agent** still assume even 11s. This changes
  the teams the agent plays against, not what it assumes about them.

## Hygiene

Pool teams and synthetic fixtures only. The usage file and the open-sheet
distributions stay local under gitignored paths.
