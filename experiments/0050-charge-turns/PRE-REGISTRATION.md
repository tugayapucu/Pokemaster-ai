# 0050 — Charge moves were priced as a hit on the turn they charge

**Written before the measurement was run.** Registered 2026-09-12.

## The defect

Ten moves carry the engine's `charge` flag. `MoveInfo.flags` has loaded it
since the dex loader was written, and nothing read it — so the move scorer
priced Solar Beam and Electro Shot as a full hit on the turn they were chosen,
when outside their weather the engine spends that turn charging.

In the harvested Reg M-C pool, **Electro Shot is on 11.1% of teams and Solar
Beam on 6.8%**. Phantom Force (0.6%) and Fly (0.3%) are the only others that
appear at all; Power Herb appears on none.

## Two changes, and only one of them is measured here

| | change | how it ships |
| --- | --- | --- |
| B | on a Mega turn, score the move in the weather the Mega's own ability will have set | **unflagged**: an engine fact, like the base-power fix in `1c2ff79`. Lands in both arms |
| C | a move that charges this turn deals nothing now: price it at `CHARGE_TURN_MULTIPLIER` (0.5) of its hit, and drop it from the focus-fire combination | behind `charge_turns`, **on by default**; this experiment sizes it |

B is needed for C to be right — whether a Solar Beam charges on the Mega turn
depends on the weather the Mega sets — which is why it is fixed first rather
than left out.

## Why it ships regardless of the win rate

Like 0049 and unlike 0047/0048: this is what the engine does, not a guess about
the opponent. `BACKLOG.md`: *"The engine settles anything with a right
answer."* The A/B sizes it; it does not decide it.

The one thing that is a modelling choice is the 0.5. It is derived (two turns
committed to one hit) rather than tuned, it leaves out every second-turn risk,
and it is not swept here. The one outcome that stops the ship is **negative and
clearing its interval**, which would mean something was compensating for the
old overpricing.

## The instrument check, with 0049's two counters

0049's first run reported only whether choices differed, and `2 of 564` could
not be told apart from a change that never fires. So this counts, over 20
battles driven by the new agent with the old one asked at every decision:

| | |
| --- | --- |
| decisions compared | |
| decisions where a legal move **would charge this turn** | the ceiling on any effect |
| decisions where a move's **score moved** | whether it fires |
| decisions where the **choice differed** | whether it decides anything |
| choice differed with **no charging move legal** | **must be 0** |

## Predictions

Written wide on purpose. 0049 predicted 5–25% of choices changing and got 0.4%,
an order of magnitude off.

| | prediction |
| --- | --- |
| decisions with a charging option | 3–15% |
| score moved | essentially all of those |
| choice differed | 0.5–5% of all decisions |
| win rate, 400 battles | neutral; not expected to clear its interval |

The reason for expecting any choices to change, unlike 0049: the old scorer
over-valued the charging move by a factor of two, not by a weather modifier
that cancels across a difference, so where it was the top move it may now
lose to the second.

## Stopping rule

One run at 400 battles, seed 0. Ships on correctness either way; a negative
result that clears its interval stops the ship and opens an investigation.

## Hygiene

Pool teams only. No scouted candidate is used in this experiment, its fixtures
or its write-up.
