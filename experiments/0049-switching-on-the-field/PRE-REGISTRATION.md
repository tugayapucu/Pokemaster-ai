# 0049 — Every switch decision is scored on a bare field

**Written before the measurement was run.** Registered 2026-09-12.

## The defect

`_matchup_against_field` — which is what `_score_switch_on_matchup` asks
"would this Pokemon do better than the one out there" — calls `matchup()` with
the `Observation` in hand and passes **neither `weather` nor `terrain`**.

The same file threads `observation.weather` into eleven call sites and
`observation.terrain` into six. This one gets neither. So while it is raining,
the switch scorer prices their Fire move at full, our Water move at full, and
decides whether to switch on a battle that is not the one being played.

## This is the second lap of the same bug

The tracker carries the first, in a comment nobody has had cause to delete:

> `terrain` was declared, read into every Observation and never once assigned,
> so it was permanently None and anything keyed off it — Rising Voltage's
> doubled power, the terrain damage bonuses — could not fire.

That fix made the field real and put it on the `Observation`. **One consumer
never started reading it.** Data tracked and not read, which is the shape that
has cost this project more than any other.

Two more laps of it were fixed yesterday in 0048: `matchup()` had no `terrain`
parameter to pass, and `estimate_damage` fell back to static base power, so
even a threaded terrain could not have applied. Those are why this is one line
now instead of three.

## Why this is not the same kind of change as 0047 or 0048

| | 0047 / 0048 | 0049 |
| --- | --- | --- |
| what it adds | a **guess** about the opponent | a **fact** already in hand |
| can be wrong | yes — a 45% prior is wrong 55% of the time | no — the weather is up or it is not |
| which instrument decides | the A/B | the engine |

`BACKLOG.md`'s two-instrument rule: *"The engine settles anything with a right
answer... This is ground truth and it is exhausted first."* Passing the actual
field to a damage calculation has a right answer.

**So this ships on correctness, and the A/B sizes it rather than deciding it.**
Recording that here, in advance, is the point — otherwise a neutral result
invites quietly reclassifying a bug fix as an unproven change, which would be
the wrong lesson from 0048's 51.0%.

## The instrument check, which still comes first

Count how many switch decisions differ between the two arms **before** reading
any win rate, exactly as 0048 did.

Here the check has a second job. Fields are not up on turn one — somebody has
to set one — so an effect that exists only under rain or terrain may reach far
fewer decisions than the format's setter usage suggests. The check measures
that directly instead of assuming it.

Reported:

| | |
| --- | --- |
| switch decisions compared | |
| decisions taken **with a field up** | the ceiling on any effect |
| decisions that **differed** | |

## Design

`evaluate` over the harvested M-C pool, the same agent on both sides but for
the flag, agents swapped between the two passes of every matchup on a shared
seed. **400 battles, seed 0.** One run.

The old behaviour stays constructible behind `field_aware_switching`, the way
`matchup_switching` kept the flat switch cost after 0032.

## Predictions

**Decisions with a field up: 30–70%.** Rillaboom is on 39.2% of teams and
Indeedee-F on 22.1%, and a terrain lasts five turns from a switch-in that
usually happens early. Wide because nothing has ever measured how much of a
battle this format spends on bare ground, and I would rather record the
ignorance than a false precision.

**Decisions that differ: 5–25%**, well under the share with a field up. Most
switch decisions are not close, and a modifier that moves both candidates
similarly changes the ordering only near a tie.

**Win rate: positive but probably not clearing its interval at 400 battles.**
The two changes that ever worked here were +10.1 and +7.8, and both were the
agent *choosing a different action*, which this also is. But the effect is
gated on a field being up and on the decision being close, so I expect
something like +1 to +3 points — the size 400 battles cannot resolve.

If it comes back **negative and clears the interval**, that is the interesting
outcome and it does not mean "revert". It means something downstream was
compensating for the bare-field score, and the compensation is now the bug.

## Stopping rule

One run at 400 battles. **The fix ships either way**, because it is a
correctness fix; the flag default goes to on. A negative result that clears its
interval stops the ship and opens an investigation instead.
