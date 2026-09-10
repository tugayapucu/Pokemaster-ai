# 0044 — Does agreement rise with the players' rating?

**Written before the measurement was run.** Registered 2026-09-10.

## Why

Collection dropped from "both players 1500+" to "anything 1000+" on 2026-09-10,
because Reg M-C's ladder was one day old and nobody on it was above 1182. That
was the right call for *getting* the data and it leaves a question open: a
1000-rated game and an 1800-rated game currently count for exactly the same in
every number this project computes.

The proposal was to weight games by rating. **This measures whether a weight
would change anything before one is built**, which is the same discipline as
0026 — check the instrument before trusting what it reports.

## The instrument check, done first

Both corpora have usable spread, so the question is answerable:

| corpus | rated | min | q1 | median | q3 | max |
| --- | --- | --- | --- | --- | --- | --- |
| Reg M-B | 1769 of 1769 | 1500 | 1540 | 1585 | 1639 | 1827 |
| Reg M-C | 1736 of 2000 | 1000 | 1000 | 1050 | 1108 | 1341 |

`minimum_rating` is the **weaker** player of the two, which is the honest bar
for "both were strong".

## Bands

Chosen from the quartiles above, before any agreement number was computed, so
the bands are not fitted to the answer. Within a regulation only.

- **Reg M-B**: `<1540`, `1540–1584`, `1585–1638`, `>=1639`
- **Reg M-C**: `<1050`, `1050–1099`, `1100–1199`, `>=1200`

Unrated replays are reported separately and never folded into a band.

**Cross-regulation comparison is confounded and will not be treated as
evidence.** M-C's corpus is 1000–1182 and M-B's is 1500+, so a difference
between them is a difference in regulation *and* in player strength at once.

## Prediction

**Flat, or very slightly rising, within each corpus.** The usable spread inside
one corpus is only about 300 Elo, and most decisions in this format are close
to forced — a Pokemon with one good attack has one good attack whoever is
holding the controller. I expect any trend to be smaller than the gap between
the two corpora's *midpoints*, which is itself confounded.

## Stopping rule

One run per regulation over the whole corpus. No re-slicing after seeing the
result, no band boundaries moved. If the trend is not visible at these bands it
is reported as not visible.

## What each outcome means

| result | conclusion |
| --- | --- |
| flat across bands | a rating weight changes nothing measurable. **Close the weighting item** and record that agreement does not track strength here |
| rises with rating | the weight is justified, and the shape of the rise says what it should be |
| falls with rating | far more interesting: agreement would be actively misleading, and a reason to trust it less than the project already does |

## What this cannot show

Whether agreement is a good target at all. 0010 and 0013 both caught cases
where following the corpus was the error. A flat result would mean weighting is
pointless, **not** that agreement is sound.
