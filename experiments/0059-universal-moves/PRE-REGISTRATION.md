# 0059 — Keep near-universal moves on the sets that carry them

**Written before either arm was measured.** Registered 2026-09-14.

## The defect

0058 filled empty move slots from usage and cut the weighted move distance from
0.196 to 0.069, but left moves on 97–100% of real sets at 85–93% of pool sets
(Rillaboom's Fake Out 93% against 100%, Pelipper's Hurricane 90% against 97%).

The cause is how the slots are picked: one weighted draw per slot. With one slot
left, a move carried by every real set competes against the others' combined
weight, and is included far less often than always.

## The change

`sample_moves(by_inclusion=True)` (`568e490`) picks the slots by conditional
Poisson sampling — each move as if carried independently at its rate, keeping
only outcomes of the right size — so a set's chance is proportional to the
product of its moves' odds, rate / (1 − rate). A move at rate 1 is always kept.
The harvest exposes it as `move_fill="inclusion"`: the 0058 reveal correction,
with slots picked this way.

It is **not exact**: conditioning on the size pulls shares apart, pushing
mid-rate moves up a few points. That could offset the gain, which is why this is
measured.

## Arms

Both built now, from the same Reg M-C train split, seed 0 and usage sources:

| arm | empty move slots |
| --- | --- |
| corrected | the installed 0058 pool |
| inclusion | the same rates, slots picked by conditional Poisson sampling |

## Measurement

| | reported for both arms |
| --- | --- |
| teams assembled, validated, survival rate | |
| **weighted move distance** to the truth source, as 0058 | |
| **near-universal carry**: pool carry rate of moves on 95%+ of the truth source's sets, weighted by pool appearances | |
| carry rates of each species' top truth moves, truth against both arms | |
| pool team 0 of the corrected arm scouted against each arm's pool, 120 opponents, seed 0 | |

## Predictions

| | prediction |
| --- | --- |
| near-universal carry, corrected | 88–93% |
| near-universal carry, inclusion | 96% or higher |
| weighted move distance, inclusion | below corrected's, but by less than 0.02 |
| mid-rate moves (40–80% real) under inclusion | a few points higher than corrected |
| survival | within 2 points |
| reference scout | moves by under 5 points |

## Adoption rule

Inclusion replaces `data/pool-champions.txt` (the 0058 pool is kept beside it)
only if **both**:

- its survival is at least 90% and within 5 points of corrected's, and
- its **weighted move distance** is lower than corrected's.

Near-universal carry is the defect's own measure but is **not** the criterion:
fixing the top moves at the cost of the rest is not a better pool, and the
distance is the whole-set measure 0058 was decided on. The scout is recorded,
not a criterion.

## Hygiene

Pool teams only. The usage file, open-sheet distributions and pools stay local
under gitignored paths.
