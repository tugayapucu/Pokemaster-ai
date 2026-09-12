# 0053 — Our own set and our own field: both ship, and one check proved nothing until re-run

Run 2026-09-13 against the pre-registration in this directory.

## What was built

| commit | what |
| --- | --- |
| `2d1d52f` | `TERRAIN_ON_ARRIVAL`, transcribed from `data/abilities.ts`; Seed Sower excluded (sets terrain when hit) |
| `f7deb91` | `matchup()` can read our ability and item: our attacks, their attacks on us, our effective Speed |
| `3917679` | **C**, `matchup_reads_our_set` (on): switch scoring passes the battle's current ability and item, Team Preview the sheet's, converted to ids |
| `9d758c9` | **D**, `own_field` (on): each candidate four at Team Preview scored in the weather and terrain its own setters create |

## C — our own ability and item

| | | pre-registered |
| --- | --- | --- |
| Team Preview picks differ, 380 previews | 208 — 55% | 20–60% ✓ |
| in-battle decisions differ, 20 battles | **2 of 456 — 0.4%** | 1–8% ✗ |
| reads-our-set vs blind, 400 battles | **207 / 193 — 51.7%** | neutral to positive ✓ |
| 95% Wilson | [46.9%, 56.6%] | |

**Ships**, as pre-registered: a fact about our own team, and it did not clear
downward. The in-battle effect is 0049's shape again — switch scores move and
the chosen action almost never does. The calibration canary, which this change
could have moved for real, still passes.

## D — the field our own four creates

| | first run | pre-registered |
| --- | --- | --- |
| our team has an arrival setter | 380 of 380 — **100%** | 50–85% ✗ |
| Team Preview picks differ | 227 — 60% | 10–40% ✗ |
| differed without a setter | 0 | must be 0 |
| own-field vs bare ground, 400 battles | **210 / 190 — 52.5%** | neutral to positive ✓ |
| 95% Wilson | [47.6%, 57.3%] | |

**Ships**, on the same rule.

### The must-be-0 row was vacuous, and was re-run

100% means every previewed team had a setter, so "differed without a setter"
could not be anything but zero. The row tested nothing.

The 100% was checked before being believed. It is mostly real: **85% of the
whole pool** — 4,957 of 5,858 teams — carries a Pokemon that sets weather or
terrain on arrival, and a random twenty drew 17. The first twenty drawing all
twenty is a roughly 4% event at that base rate; they are not near-copies of one
team (18 distinct rosters). The prediction band was simply too low.

Re-run on **40 teams drawn at random**:

| | |
| --- | --- |
| previews compared | 1,560 |
| previews **without** a setter | **273** |
| picks that differ | 827 — 53% |
| **differed without a setter** | **0** |

With 273 previews where D cannot apply and no pick changed among them, the
check now says something: D changes Team Preview only where our own team sets a
field.

**Every instrument check in 0048, 0052 and 0053 drew the first twenty pool
teams in file order.** It did not bias these results, but it can make a
precondition row vacuous, as here. Checks from now on draw at random.

## Still not modelled

- The field is treated as up for the whole matchup: no duration, and no
  opposing setter taking it back.
- With two setters of one kind in a four, the first in team order wins.
- The opponent's ability and item remain unknown at Team Preview.

## Hygiene

Pool teams and synthetic fixtures only.
