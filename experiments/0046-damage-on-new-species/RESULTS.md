# 0046 — There is no damage gap on M-C's new species. The first answer was wrong.

Run 2026-09-10. **This file has been rewritten**: the first version reported a
−9.2 point gap and that result was an artifact of the harness, not a property
of the model. The retraction is the finding worth keeping.

## The answer

| arm | inside the predicted range | n | 95% Wilson |
| --- | --- | --- | --- |
| **old** (neither side new) | 80.8% | 265 | [75.6%, 85.0%] |
| **new** (attacker or defender new) | 83.2% | 101 | [74.7%, 89.2%] |

**Gap: +2.4% in favour of the new species, intervals heavily overlapping.**

The damage model handles Reg M-C's 35 new species as well as it handles
anything else. The pre-registered prediction — "no meaningful difference" — was
right after all. Nothing about Rillaboom, Baxcalibur, Golisopod or Salamence
needs fixing before Frankfurt.

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

## What is still open, and is now a different question

Both arms now read ~81–83%, against the 93.9% this project publishes. **So the
"93.9% confirmed on the pinned build" claim from the first version is also
withdrawn** — it was the same contaminated run.

Slot resolution has the opposite failure to species resolution: `active_slots`
is read before the turn is submitted and is stale the moment anything switches
or faints mid-turn. The surviving mismatches look like exactly that —

```
  Rillaboom woodhammer -> Kingambit:  predicted 45-54,  engine dealt 147
  Rillaboom woodhammer -> Primarina:  predicted 116-140, engine dealt 48
```

— errors in both directions on the same move, which is what mis-attributing
the defender looks like rather than what a wrong multiplier looks like.

**Neither lookup is right.** Species matching loses Mega; slot matching loses
mid-turn movement. The harness needs the state as of each protocol *line*,
which is what the tracker already maintains, rather than a snapshot taken once
per turn. That is the real fix and it is a separate piece of work.

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
