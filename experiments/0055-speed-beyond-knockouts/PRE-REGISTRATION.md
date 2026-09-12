# 0055 — Moving first, valued over a race of any length

**Written before the measurement was run.** Registered 2026-09-13.

## The defect

`matchup()` — Team Preview and every switch — priced the turn order as

    faster:  our_knockout_chance × their_hit
    slower: -their_knockout_chance × our_hit

so speed counted only in a **one-hit** race. A Pokemon that outspeeds the whole
field but rarely knocks out in one hit got close to nothing for it. Measured on
one fast set: outspeeding every previewed opponent, its speed contributed in
6% of those pairings — the ones with a one-hit knockout.

## The change

`order_edge` runs the race over as many hits as it takes. Moving first is worth
the hit it denies on the turn a side finishes: the faster side denies the slower
side's hit whenever it needs **no more hits** than the slower side does.

| we need | they need | faster side | value |
| --- | --- | --- | --- |
| 1 | any | us | our knockout chance × their hit (unchanged) |
| 2 | 2 | us | their hit — moving first wins a race moving second loses |
| 2 | 3 | us | their hit — one fewer taken on the way |
| 3 | 2 | us | nothing — they finish first either way |

Hits are counted from the expected fraction per hit.

## Why it is measured rather than shipped

The turn order is a fact; the race model is a judgement. It is still two
Pokemon trading hits — no switching, no Protect, no partners, no damage rolls
beyond the one-hit case. So `speed_beyond_knockouts` is **off**, and turns on
only if its interval clears 50% upward.

## Instrument checks

Teams drawn at random (0053's note).

| | |
| --- | --- |
| Team Preview picks differ, 40 random teams | reported |
| battle decisions differ, 20 random matchups | reported |
| matchups decided in the A/B | reported — so a 200/200 is read correctly the first time (0054) |

**No must-be-0 row.** Speed enters nearly every matchup, so there is no natural
set of previews or decisions where this change cannot apply. Stated rather than
invented.

## Predictions

| | prediction |
| --- | --- |
| Team Preview picks differ | 20–60% |
| battle decisions differ | 1–6% |
| A/B, 800 battles | neutral to positive; not expected to clear |

## Hygiene

Pool teams and synthetic fixtures only.
