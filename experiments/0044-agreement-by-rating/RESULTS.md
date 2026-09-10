# 0044 — Agreement does not track how good the players are

Run 2026-09-10 against the pre-registration in this directory. Bands were fixed
from each corpus's quartiles before any agreement number existed, and were not
moved afterwards.

## Reg M-B — 1,769 replays, 31,596 decisions

| band | agreed | n | 95% Wilson | replays |
| --- | --- | --- | --- | --- |
| <1540 | 45.1% | 7,933 | [44.0%, 46.2%] | 436 |
| 1540–1584 | 44.6% | 7,961 | [43.5%, 45.7%] | 448 |
| 1585–1638 | 44.4% | 7,789 | [43.3%, 45.5%] | 441 |
| >=1639 | 44.5% | 7,913 | [43.5%, 45.6%] | 444 |

## Reg M-C — 2,000 replays, 33,986 decisions

| band | agreed | n | 95% Wilson | replays |
| --- | --- | --- | --- | --- |
| <1050 | 44.4% | 14,324 | [43.6%, 45.2%] | 868 |
| 1050–1099 | 45.2% | 6,624 | [44.0%, 46.4%] | 383 |
| 1100–1199 | 45.3% | 6,378 | [44.0%, 46.5%] | 387 |
| >=1200 | 45.7% | 1,653 | [43.3%, 48.1%] | 98 |
| unrated | 43.5% | 5,007 | [42.1%, 44.8%] | 264 |

## The result

**Flat, in both, and flat between them.** Every interval within a corpus
overlaps every other. M-B drifts 0.6 points *down* across 330 Elo; M-C drifts
1.3 points *up* across 340 Elo. Neither is significant and they point opposite
ways, which is what noise looks like.

The stronger version is the comparison the pre-registration refused to treat as
evidence of a regulation difference — but which is perfectly good evidence
here, because it is the *rating* axis stretched much further:

```
  Reg M-C corpus   1000-1341 Elo    44.6% agreement
  Reg M-B corpus   1500-1827 Elo    44.7% agreement
```

**Eight hundred Elo apart, one tenth of a point.** Beginners on a one-day-old
ladder and established ladder players match our top recommendation at
indistinguishable rates.

## What follows, per the pre-registration

> flat across bands → a rating weight changes nothing measurable. **Close the
> weighting item** and record that agreement does not track strength here.

So the weighting item is closed. Building a rating weight would have added a
parameter, a sweep and a caveat to every reported number, in exchange for
moving nothing.

**A useful side effect: the 1000-rated M-C corpus is not the liability it
looked like.** It was collected unfiltered out of necessity and written down as
"unusable as an agreement signal". On this evidence it is exactly as usable as
the 1500+ one — which is a statement about how little agreement varies, not a
promotion of the corpus.

## What it actually means, and the honest limit

This is the third time agreement has failed to behave like a quality measure.
0010 fitted Trick Room's value without bound because a team that brings it
nearly always uses it. 0013 found humans near-random on target selection while
it looked like the project's largest gap. Now: agreement is **the same for a
1000-rated player as for an 1800-rated one**.

The natural reading is that agreement mostly measures **how forced the format's
decisions are**, not how well anyone plays them. A Pokemon with one good attack
into one good target has one good move whoever is holding the controller, and
that floor is the same at every rating.

**That reading is not tested here.** The obvious next measurement is to band
agreement by *how many legal actions the position offered* — if the flatness is
forcedness, agreement should fall as the branching factor rises, and fall
equally at every rating. That is one more banding of a survey that already
runs.

**And the limit worth stating plainly:** a flat result means weighting is
pointless. It does **not** mean agreement is a sound target. Everything this
project already believes about that still holds.
