# 0057 — Build the team pool from what sets actually carry

**Written before the rebuild was measured.** Registered 2026-09-14.

## The defect

The pool every scout and every A/B plays against was built from what replays
**reveal**. An item enters a replay only when it announces itself, so silent
items went missing, and every set carried an even 11 Stat Points in each stat
with a neutral nature.

Against sources that see sets whole:

| species | truth | pool | truth source |
| --- | --- | --- | --- |
| Kingambit | Chople Berry 37%, Black Glasses 27%, Life Orb 21% | Chople Berry 93% | Smogon Reg M-B usage |
| Sneasler | White Herb 46%, Focus Sash 43% | Grassy Seed 67%, Psychic Seed 30% | Smogon Reg M-B usage |
| Baxcalibur | Mega Stone 96% | Roseli Berry 98% | open team sheets, Reg M-C |
| Rillaboom | Miracle Seed 56% | Grassy Seed 83% | open team sheets, Reg M-C |

And among the thirty most-used Reg M-B species, 0.2% of real spreads look
anything like an even 11 per stat.

## The change

`harvest.build_set` takes an optional `usage` distribution and **draws** — not
the mode — each Pokemon's item, nature and Stat Points from it. Sources, first
wins:

1. **Smogon's chaos file**, Reg M-B, 1500 cutoff, August 2026: items, natures,
   spreads. Mega entries folded into the species holding the stone.
2. **Open team sheets** in the Reg M-C *train* split, species with 20+ sheets:
   items and natures; Stat Points stay even.
3. Otherwise the old behaviour, **counted**.

Moves and abilities are unchanged.

## Measurement

Both pools are built **now**, from the same M-C train split, with seed 0 — one
without `usage` (the old method) and one with it — so only items, natures and
spreads differ.

| | reported for both pools |
| --- | --- |
| teams assembled, teams the engine validates, survival rate | |
| Pokemon covered by Smogon / open sheets / fallback | |
| item distance to the truth source: total variation, per species and weighted by pool appearances | |
| a pool reference team scouted against 120 opponents, seed 0 | |

## Predictions

| | prediction |
| --- | --- |
| coverage | ~77% Smogon, 10–20% open sheets, under 15% fallback |
| engine survival | within 3 points of the old method's |
| weighted item distance | old above 0.4; new under 0.15 |
| reference team's scout result | moves by 2–10 points; direction unknown |

## Adoption rule

The rebuilt pool replaces `data/pool-champions.txt` (the old file is kept beside
it) if **both**:

- engine survival is at least 90% and within 5 points of the old method's, and
- the weighted item distance to the truth source goes down.

The scout shift is recorded, **not** a criterion: this is a correction to the
measuring stick, and a stick that reads differently once corrected is the
point. Every pool-based number before 0057 was measured on the old pool, and
the write-up says so.

## Hygiene

Pool teams only; no scouted candidate is used here. The usage file and open-sheet
distributions stay local.
