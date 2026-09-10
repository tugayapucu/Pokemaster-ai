# 0046 — Is the damage model as accurate on M-C's new species?

**Written before the measurement was run.** Registered 2026-09-10.

## Why this and not the absolute number

The project publishes **93.9% of hits inside the predicted range, no Mega**
(86.9% with Mega on), measured on 0.11.11. That figure has not been reproduced
since the engine was pinned to `d849b22`, and an ad-hoc attempt read 73.0% —
almost certainly because it used Mega-heavy real teams against a no-Mega
reference, and because it snapshotted each side *before* a turn and then
attributed that whole turn's hits to it.

Chasing the absolute figure is a separate job. **The question that matters for
Frankfurt is comparative**: M-C added 35 species this project's damage model
was never validated against, and `position` will be giving advice about them at
a Regional. A paired comparison answers that, and every harness quirk cancels
because both arms come out of the same battles.

## The hypothesis, which is not a formality

The damage formula is species-agnostic: it reads base stats and types from the
dex, and the engine supplies those for new species exactly as for old ones. So
the formula cannot care.

**Abilities can.** New species bring abilities the model may not handle, and
the ones that actually see play are exactly the awkward kind:

| species | slots in 400 teams | ability worth worrying about |
| --- | --- | --- |
| Rillaboom | 156 | Grassy Surge — terrain, which feeds a damage multiplier |
| Golisopod | 95 | Emergency Exit |
| Salamence | 89 | Intimidate / Moxie — an Attack modifier |
| Baxcalibur | 35 | Thermal Exchange |
| Pawmot | 21 | Volt Absorb — an immunity |

## The instrument check, done first

New-in-M-C species fill **443 of 2,400 team slots (18.5%)** in the harvested
M-C pool. There is plenty to measure.

## Design

Self-play on `data/pool-eval-m-c.txt`, the pool harvested from real M-C games.
Every damage sample is classified into one of two arms:

- **new** — the attacker or the defender is one of the 23 new non-forme species
- **old** — neither is

Both arms come from the same battles and the same seeds, so any bias in the
harness applies to both.

**Mega formes are excluded from both arms.** Twelve of M-C's 35 additions are
alternate formes, and Mega is already known to cost seven points of accuracy
(93.9% → 86.9%). Leaving them in would confound "new species" with "Mega". It
also removes the reason the species-matching lookup is unsafe, so the sample
attribution can use whole teams and avoid the stale-snapshot flaw.

## Prediction

**No meaningful difference.** The formula cannot care about species identity,
and the abilities above are mostly handled or mostly irrelevant to a damage
roll. I expect both arms within a couple of points of each other.

If they differ by more than that, the cause will be an ability rather than the
formula, and the table of which species drive the gap will say which.

## Stopping rule

One run, 60 battles, whole pool, fixed seeds. No re-slicing after the fact. The
arms are defined above and are not moved.

## What each outcome means

| result | conclusion |
| --- | --- |
| arms within ~2 points | the model transfers to M-C's new content; `position` can be trusted on them as much as on anything else |
| new arm clearly worse | there is a real gap at a Regional, and the per-species table names where. Fix before Frankfurt |
| new arm clearly better | suspicious rather than good — likely a composition artifact (which moves, which HP ranges), and to be investigated rather than banked |

## What this cannot show

Whether **93.9% still holds at all** on the pinned build. Both arms could be
equally bad. This is a comparison, and it is reported as one; the absolute
figure stays open and is recorded as such in the backlog.
