# 0049 — The fix is live, fires often, and almost never changes the choice

Run 2026-09-12 against the pre-registration in this directory.

## The instrument check

| | | pre-registered |
| --- | --- | --- |
| decisions compared | 564 | |
| taken with a field up | 212 — **38%** | 30–70% ✓ |
| **a switch score moved** | 103 — **18%** | |
| decisions that **differed** | **2 — 0.4%** | 5–25% ✗ |
| differed on bare ground | **0** | must be 0 ✓ |

## My prediction was wrong by an order of magnitude, and the extra counter is why I know how

I predicted 5–25% of decisions would differ. The answer is **0.4%**.

The first run produced only the `differed` row, and 2 of 564 is unreadable on
its own — indistinguishable from a fix that never fires, which is precisely the
0047 failure this whole discipline exists to catch. So the check gained a
second counter before anything was written up: **does the field change what a
switch is worth**, whether or not it changes the action chosen.

| | |
| --- | --- |
| a field is up | 212 |
| ...and a switch score moves | **103 — 49% of those** |
| ...and the chosen action changes | 2 — 1.9% of those |

**The fix fires constantly and decides almost nothing.** Those are different
facts and the single number hid both.

It is worth being exact about the miss rather than soft: the 18% is inside the
5–25% band I wrote down, but 18% is the *score* moving, and what I predicted was
the *choice* changing. I predicted the wrong quantity. The band being right for
the other one is not a defence.

## Why the choice so rarely changes, which the pre-registration half-knew

Two multipliers, and the pre-registration only wrote down the first:

1. **The score is a difference.** `_score_switch_on_matchup` prices
   `coming_in − staying`, both on the same field. A modifier that moves both
   alike cancels before it reaches the number — the fix bites where the two
   candidates differ in type, not merely where a field is up. That halving is
   visible: 103 of 212.
2. **Switching is rarely the marginal decision.** The switch score competes
   against the attack scores, and attacking usually wins by more than the field
   moves the switch differential. That second factor is the one that turns 103
   into 2, and it is not in the pre-registration at all.

## The A/B, which is uninformative and known to be

| | |
| --- | --- |
| aware vs blind, 400 battles | 198 / 202 — **49.5%** |
| 95% Wilson | [44.6%, 54.4%] |

With 2 of 564 decisions differing, 400 battles measure almost nothing: this is
noise around a change that hardly ever fires, not evidence about its quality.
The honest label is **uninformative**, not "neutral" — and the only reason that
can be said with confidence is that the check ran first. Read alone, 49.5%
would have looked like a fair test that came back flat.

## It ships, as pre-registered

`field_aware_switching` defaults to **on**.

The pre-registration committed to this in advance and the reasoning holds:
passing the real field to a damage calculation is an engine fact, not a
judgement. `BACKLOG.md`'s two-instrument rule settles it — *"The engine settles
anything with a right answer."* The A/B was there to size the change, not to
decide it, and the one outcome that would have stopped the ship — negative and
clearing its interval — did not happen.

Writing that down beforehand is what makes this a decision rather than a
rationalisation. 0048 came back at 51.0% and stayed off because it was a guess;
this comes back at 49.5% and ships because it is a fact. Without the
pre-registration those two would be indistinguishable.

## What was actually bought

Not win rate. **Consistency.**

The move scorer already knew the field; eleven call sites take
`observation.weather` and six take `observation.terrain`. The switch scorer did
not. So the agent could price an attack in rain correctly and, in the same
turn, evaluate switching away from that rain as though it were not raining.
Those two now agree.

That matters most for the things this project has not measured yet — the
position evaluator, and any search that expands a switch and then scores the
resulting position. A one-line inconsistency at the root of a tree is not a
0.4% problem.

## Third lap of one bug, and the trail is in the comments

| where | what | when |
| --- | --- | --- |
| `tracker._on_minor_fieldstart` | `terrain` declared, read into every Observation, **never assigned** | earlier |
| `matchup()` | no `terrain` parameter to pass | 0048 |
| `estimate_damage` | static base power, so a threaded terrain could not apply | 0048 |
| `_matchup_against_field` | had the Observation, passed neither | **0049** |

Each fix made the next one reachable and none of them made it *happen*. The
tracker comment — *"declared, read into every Observation and never once
assigned"* — has been sitting in the file the whole time, describing the shape
of a bug three layers above it.

## Still open

`_matchup_against_field` scores the field that is up **now**. A Pokemon coming
in may set its own — that is what 59% of Rillabooms do — so the switch that
creates Grassy Terrain is still priced on whatever preceded it. That is a
harder change and a judgement rather than a fact, so it is not folded in here.
