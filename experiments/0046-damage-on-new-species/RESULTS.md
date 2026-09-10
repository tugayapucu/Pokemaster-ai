# 0046 — No damage gap on M-C's new species, after fixing the instrument twice

Run 2026-09-10. **Rewritten twice.** The first version reported a −9.2 point
gap that was a harness artifact; the second corrected the comparison but not
the level. The history is kept because how the measurement was wrong is worth
more than the answer, which is a null.

## The answer

Measured on a harness whose attribution was fixed afterwards (see below). Final
numbers:

| arm | inside the predicted range | n | 95% Wilson |
| --- | --- | --- | --- |
| **old** (neither side new) | **95.5%** | 269 | [92.4%, 97.4%] |
| **new** (attacker or defender new) | **93.7%** | 95 | [86.9%, 97.1%] |

**Gap: −1.9%, intervals heavily overlapping.** The damage model handles Reg
M-C's 35 new species as well as it handles anything else. The pre-registered
prediction — "no meaningful difference" — was right.

**And the published 93.9% holds on the pinned build**, properly this time:
95.5% on the old arm, from a harness whose two failure modes are now covered by
tests rather than assumed away.

### It took three runs to get here

| run | old | new | gap | what was wrong |
| --- | --- | --- | --- | --- |
| 1 | 94.1% | 84.9% | **−9.2%** | Mega contamination: the exclusion tested the species *name*, and the lookup resolved *by* species |
| 2 | 80.8% | 83.2% | +2.4% | Mega excluded properly, but slot resolution lost every mid-turn switch |
| 3 | **95.5%** | **93.7%** | −1.9% | attribution tracks the chunk; both arms land on the reference figure |

The first run's answer was wrong in the interesting direction and I published it.
The second was right about the comparison and wrong about the level. Only the
third is both.

## What went wrong the first time

The first run reported old 94.1% against new 84.9% and I believed it, wrote it
up, and pushed it. It was **Mega contamination**.

The pre-registration said to exclude Mega formes, and the code did this:

```python
if "mega" in attacker or "mega" in defender:   # species name
```

That never fired. **It printed "0 samples dropped for involving a Mega forme"
on every run, over a pool full of Mega Stones, and I did not question it.**
That line was the tell and it was on screen the whole time.

Two mistakes compounded:

1. **The lookup resolved by species.** `active_by_ident` warns in its own
   docstring that a Pokemon which Mega Evolves keeps its protocol ident while
   its set becomes the Mega forme, so species matching returns the *base*
   forme. I chose species matching deliberately, reasoning that its Mega blind
   spot was safe *because Mega was excluded* — and Mega was not excluded,
   because the exclusion depended on the very name the lookup got wrong.
2. **The arms were not symmetric in Mega exposure.** Three of M-C's additions
   are new Megas — Golisopod, Baxcalibur and Salamence all have stones. So the
   "new" arm carried more contaminated samples than the "old" one, and the
   contamination looked exactly like a deficiency in the new species.

Fixed by excluding on the **item** — a held stone that matches its holder —
and by resolving through `Side`, which goes by slot.

With that, 202 samples are dropped per 60 battles where 0 were before, and the
gap inverts from −9.2 to +2.4.

## The harness fix, which was the real work

Both lookups were wrong in opposite ways. **Species matching** loses a Mega,
which renames itself mid-turn. **Slot matching** loses anything that switches or
faints mid-turn, because `active_slots` is read before the turn is submitted.

`DamageCollector` already corrected its snapshot for one within-turn change --
stat stages, because "a hit landing after a Swords Dance was scored against
stale stages". Occupancy is the same class of problem and now works the same
way: the collector follows `switch`, `drag`, `replace` and `detailschange`
through the chunk, and resolves each ident by the **species from the details
field** rather than by the nickname in the ident.

A Mega then resolves to a forme the pre-turn team does not contain, so the
sample is dropped -- and **counted**, in `unresolved`, because a resolver that
quietly drops half its samples looks exactly like a resolver that works. That
counter is the lesson from run 1, where "0 samples dropped" was printed on
every run and read past four times.

Worth its own line: **fixing attribution moved both arms by about thirteen
points**, from ~81% to ~95%. The mis-attribution was not a rounding error on
the measurement; it was most of it.

## What survives

- **The comparative answer**, which is what the experiment was for: no
  M-C-specific damage problem. The two arms differ by less than their noise.
- **The Grassy Terrain fix**, which is independent of all of this: Grassy
  Terrain halves Earthquake, Bulldoze and Magnitude against a grounded target,
  that rule was missing, it is transcribed from the engine and unit-tested, and
  it is correct whatever the harness does.
- **A rule worth remembering.** A filter that reports dropping nothing is a
  filter that is not running. The count was printed, it said zero, and zero was
  impossible.
