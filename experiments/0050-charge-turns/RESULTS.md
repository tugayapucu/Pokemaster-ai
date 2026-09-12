# 0050 — Charge moves now cost the turn they charge; the win rate cannot see it

Run 2026-09-12 against the pre-registration in this directory.

## What shipped, in four commits

| commit | what |
| --- | --- |
| `f1343ce` | `WEATHER_ON_ARRIVAL`: which abilities set weather on arrival, transcribed from `data/abilities.ts` |
| `83ab7e1` | `mechanics.charge`: when a charge move spends the turn charging, transcribed from `data/moves.ts` and `data/items.ts` |
| `7f97f5e` | a Mega's move is thrown in the weather its forme sets (unflagged) |
| `29b4e52` | the agent prices a charging turn at half a hit and drops it from focus fire (`charge_turns`, on) |

Every rule was read off the pinned engine rather than recalled: the queue order
(`switch: 103`, `megaEvo: 104`, moves `200`), `formeChange` calling
`setAbility` on a permanent forme change, `onTryMove` for each charge move, and
Power Herb's `onChargeMove`.

## The instrument check

| | | pre-registered |
| --- | --- | --- |
| decisions compared | 553 | |
| a charge move was legal | 27 — 4.9% | 3–15% ✓ |
| a charge move's score moved | 20 — 3.6% | "essentially all of those" ✗ |
| decisions that differed | 10 — 1.8% | 0.5–5% ✓ |
| differed with no charge move legal | **0** | must be 0 ✓ |

Seven of the 27 decisions with a charge move legal did not move a score. Sun
already up, a locked second turn, or a Mega bringing its own sun would each do
that, but **which of them it was was not checked**, so the miss is recorded as
a miss rather than explained.

## The measurement

| | |
| --- | --- |
| aware vs blind, 400 battles | 198 / 202 — **49.5%** |
| 95% Wilson | [44.6%, 54.4%] |

Neutral, as predicted. It ships on correctness, as pre-registered: the engine
spends the turn charging whatever the win rate says.

## 198/202 was exactly 0049's number, so it was checked

The project's rule is that a number which looks reasonable is not evidence it
was computed from anything. So all three were re-run on current code with
per-matchup scores kept:

| run | record | total turns | decided matchups |
| --- | --- | --- | --- |
| identical agents | 200 / 200 | 3,718 | **0 of 200** |
| 0049's arms, re-run | 199 / 201 | 3,721 | 11 |
| 0050's arms | 198 / 202 | 3,767 | 8 |

- The mirror ties every matchup, so the harness is sound.
- 0050 reproduces 198/202 exactly, so it is deterministic.
- 0049 and 0050 decide **different** matchups: one in common, ten only in
  0049, seven only in 0050.

The identical totals were arithmetic. 0049's arms now come out 199/201 rather
than its original 198/202, which is expected: both of its arms now carry the
charge and Mega-weather fixes.

## A finding on the way to the next bug

Sizing Trick Room for the next item compared the harvested pool with the
replays, and the first comparison was wrong in a way worth recording.

The pool's sets are **filled to four moves from the species' most common
moves** (`harvest.build_set`), and pool carry rates looked wildly inflated
against replay *use* rates — Indeedee-F's Trick Room on 95% of pool sets
against 28% of appearances. But use is only a floor on carry: a Pokemon holds a
move it does not click. Against sets where all four moves were revealed:

| species / move | four-move sets | carried in them | pool |
| --- | --- | --- | --- |
| Indeedee-F / Trick Room | 36 | 86% | 95% |
| Kingambit / Protect | 38 | 89% | 98% |
| Sinistcha / Trick Room | 10 | 70% | 96% |
| Torkoal / Heat Wave | 4 | 25% | 99% |
| Talonflame / Brave Bird | 6 | 17% | 97% |

Where the sample is real, mode-filling inflates carry by roughly 6–10 points.
The large gaps sit on four to six sets and are not established. Four-move sets
are themselves biased toward long games. Recorded as a backlog item, not acted
on.
