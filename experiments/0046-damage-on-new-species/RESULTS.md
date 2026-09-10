# 0046 — The damage model is ~10 points worse on M-C's new species

Run 2026-09-10 against the pre-registration in this directory, at the
registered 60 battles. **The prediction was wrong**, which is the point of
writing it down first.

## Result

| arm | inside the predicted range | n | 95% Wilson |
| --- | --- | --- | --- |
| **old** (neither side new) | **94.1%** | 254 | [90.5%, 96.4%] |
| **new** (attacker or defender new) | **84.9%** | 126 | [77.6%, 90.1%] |

**Gap: −9.2 points.** The intervals do not overlap.

## Two things this settles for free

**The harness is sound, and the published 93.9% still holds.** The old arm
reads **94.1%** against the 93.9% recorded on npm 0.11.11. So the engine pin
did not move damage accuracy, and the backlog item asking where 93.9% came from
is answered: it is self-play with **Mega excluded**, and the earlier ad-hoc
attempt read 73.0% for two reasons — it left Mega in (already known to cost
seven points) and it snapshotted each side *before* a turn, then attributed
that whole turn's hits to the snapshot.

**The gap is really about a handful of species.** 124 of the 130 new-arm
samples involve Rillaboom, with Baxcalibur (34), Golisopod (28) and Salamence
(16) behind it. This is not "new species are worse" so much as "these four are
worse", and the honest headline is the narrower one.

## A real bug found, fixed, and *not* the cause

Grassy Terrain has two rules and this project modelled one. It boosts Grass
moves by 1.3×, which was handled; it also **halves Earthquake, Bulldoze and
Magnitude against a grounded target**, which was not:

```js
const weakenedMoves = ['earthquake', 'bulldoze', 'magnitude'];
if (weakenedMoves.includes(move.id) && defender.isGrounded() && ...) {
    return this.chainModify(0.5);
```

That is not a small omission in this format: Rillaboom has Grassy Surge, so the
terrain is up the moment it is sent out, and Earthquake is a staple. Every one
was predicted at double its real damage while Rillaboom was on the field.

Fixed in `mechanics/base_power.py`, transcribed from the engine, verified
directly (Earthquake 100 → 50 base power under Grassy Terrain) and covered by
three unit tests including the case that reads the *defender's* footing rather
than the attacker's.

**And re-running 0046 with the fix in place left the gap at −10.6%.** It was a
genuine bug and it was not this one. Recorded that way because a fix that does
not move the number it was aimed at should be reported as not moving it.

## What the mismatches actually say

Two clusters, both close to a clean factor of two:

```
  Golisopod ironhead -> Incineroar:   predicted 13-16,  engine dealt 35
  Golisopod ironhead -> Baxcalibur:   predicted 78-92,  engine dealt 192
  Golisopod ironhead -> Basculegion:  predicted 25-29,  engine dealt 63
  Gholdengo shadowball -> Baxcalibur: predicted 64-76,  engine dealt 134
  Incineroar flareblitz -> Baxcalibur: predicted 54-64, engine dealt 126
  Tyranitar knockoff -> Baxcalibur:   predicted 75-88,  engine dealt 152
```

- **Golisopod attacking** is under-predicted ~2.2×, across different moves and
  different targets.
- **Baxcalibur defending** is under-predicted ~2×, across different *attackers*.

A multiplier that big, following the *species* rather than the move, points at
a stat rather than a move rule — we appear to think Golisopod hits far softer
and Baxcalibur is far bulkier than the engine does. Neither carries a
damage-modifying ability (Emergency Exit, Thermal Exchange/Ice Body), so the
next place to look is the stat line each side is being given.

**That is where this stops.** Two hypotheses were tried and neither was right;
the third is not going to be a guess. The next step is to compare our
`computed_stats` for Golisopod and Baxcalibur directly against the engine's for
the same packed team, which is a five-line check and settles it.

## Why it matters before Frankfurt

Rillaboom, Golisopod, Salamence and Baxcalibur are among the most-played new
species — Rillaboom alone fills 156 of 2,400 slots in the harvested pool. A
damage model that is ten points less accurate against them is ten points less
accurate on the advice `position` gives about them, at a Regional, in the
format being played.
