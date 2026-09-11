# 0047 — The prior is correct, and where it was wired it can never fire

Run 2026-09-12 against the pre-registration in this directory.

## The measurement

| | |
| --- | --- |
| with prior vs without, 400 battles | **200 / 200 — 50.0%** |
| 95% Wilson | [45.1%, 54.9%] |

And the number that matters more:

| | |
| --- | --- |
| decisions compared over 20 battles | 221 |
| decisions that **differed** | **0** |
| positions with an unrevealed, prior-covered species on their side | **0** |

**It is not a neutral result. It is a no-op**, and 200/200 is exactly what
`evaluate` produces for two identical agents by construction — the same shape
as a measurement of nothing. Reporting 50.0% and stopping would have been the
"0 samples dropped" mistake for the third time.

## Why it can never fire there

`_known_ability` is asked about an `ObservedPokemon`, and a species only enters
`opponent_side.revealed` **once it has been on the field**. Every ability the
prior covers is loud — that is what got it past the reveal gate — so it
announces on the switch-in that puts the Pokemon there in the first place.

The reveal and the appearance are simultaneous. There is no turn on which we
are looking at a Rillaboom whose Grassy Surge has not already fired.

The pre-registration half-saw this: *"the loud abilities are loud precisely
because they announce themselves immediately, so the prior only buys the turns
before the first switch-in."* The correction is that there are no such turns.
**The gate that made the prior trustworthy is the same property that makes it
useless in that position.**

## Where the information is actually worth something

**Team Preview**, which is the one place we see their six and none has been on
the field. `matchup_table` says so itself:

```python
    assumed_points=self.assumed_opponent_points,
    # No weather at Team Preview: the battle has not
    # started, so none is set yet.
```

True, and beside the point: no weather is set *yet*. A team with Pelipper is
going to be in rain, and `matchup()` already takes a `weather` argument that
Team Preview passes nothing to.

The prior covers **every weather and terrain setter in the format** — Pelipper
(Drizzle, 16.3% of teams), Torkoal (Drought), Tyranitar (Sand Stream),
Ninetales-Alola (Snow Warning), Rillaboom (Grassy Surge, 39.2%), Indeedee-F
(Psychic Surge, 22.1%). Seeing one at Team Preview is a strong prediction about
the field a battle will be fought on, and a Fire attacker picked into a Pelipper
team is worse than the grid currently says.

That is a different change from this one, with a different and much better
argument, and it is now the item.

## What was kept, and why

The prior machinery stays: off by default, tested, and correct. It is the
substrate the Team Preview version needs, and re-deriving it later would repeat
work that is already done and already gated.

What it is **not** is evidence of anything about play. This measured a change
that made no decisions differently, so it says nothing about whether guessing
an opponent's ability helps — only that it cannot help where it was asked.

## The lesson, which is the same one again

An A/B result is only worth reading once the two arms are known to differ. This
project has now been caught three times by a number that looked reasonable
while being computed from nothing: "0 samples dropped" in 0046, a lift table
built on eleven observations in `meta`, and 200/200 here. The check is cheap
every time and was skipped every time until the answer looked strange.
