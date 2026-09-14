# 0058 — Fill the pool's empty move slots from usage

**Written before any arm was measured.** Registered 2026-09-14.

## The defect

Each pool set starts from a real partial set — the moves one player was seen
using in one battle — and every empty slot is filled with the species' **most
common** revealed moves. Imputing the mode for every missing slot inflates the
mode. Sized earlier against sets with all four moves revealed: about 6–10
points on well-sampled moves (Kingambit's Protect 98% in the pool against 89%).

0057 fixed items, natures and spreads from sources that see whole sets and left
moves alone. Those sources carry move rates too (`fc49f94`), and the harvest can
now draw empty slots from them (`move_fill`, the commit before this one).

## Arms

All three built now, from the same Reg M-C train split, seed 0, with 0057's
usage sources (Smogon Reg M-B 1500+ August 2026, then open team sheets):

| arm | empty move slots |
| --- | --- |
| baseline | most common revealed moves — the installed 0057 pool |
| plain | drawn by carry rate |
| corrected | drawn by carry rate given not revealed, (carry − reveal) / (1 − reveal) |

Why two: the partial set is drawn first, and a move revealed often is already in
it often, so plain fill adds it a second time on the sets that did not reveal
it. Corrected removes that. The reveal rates come from M-C replays and the carry
rates mostly from M-B usage, which is why this is measured rather than assumed.

## Measurement

| | reported for every arm |
| --- | --- |
| teams assembled, validated, survival rate | |
| **move distance** to the truth source, per species and weighted by pool appearances | |
| carry rates of each species' top truth moves, truth against each arm | |
| pool team 0 (the same team as 0057's reference) scouted against the arm's pool, 120 opponents, seed 0 | |

**Move distance** for a species: half the sum, over every move, of the absolute
difference between pool carry rate and truth carry rate, divided by four. That
is total variation between the two distributions over move slots, so 0 is
identical and 1 is nothing in common, as 0057's item distance. The truth source
is the species' usage distribution; fallback species have none and are left out.

## Predictions

| | prediction |
| --- | --- |
| baseline move distance | 0.10–0.25 |
| plain | below baseline |
| corrected | below plain |
| where plain overshoots most | the moves revealed most: Protect, Fake Out, spread attacks |
| survival | every arm within 2 points of baseline |
| pool team 0's scout | moves by under 5 points in either direction |

## Adoption rule

1. Of **plain** and **corrected**, the one with the lower weighted move distance
   is the candidate.
2. The candidate replaces `data/pool-champions.txt` (the 0057 pool is kept
   beside it) only if **both**:
   - its survival is at least 90% and within 5 points of baseline's, and
   - its weighted move distance is lower than baseline's.
3. Otherwise the 0057 pool stays.

The scout result is recorded, **not** a criterion, for 0057's reason: this
corrects the measuring stick.

## Hygiene

Pool teams only. The usage file, the open-sheet distributions and the pools stay
local under gitignored paths.
