# 0051 — Trick Room priced by speed: the price moves, the choice almost never does

Run 2026-09-12 against the pre-registration in this directory.

## What was built

| commit | what |
| --- | --- |
| `36efaa6` | `_our_speed` / `_their_speed` pulled out of `_moves_first`, unchanged behaviour |
| `99c754b` | `trick_room_by_speed`: Trick Room priced as `55 × scale × (share after the flip − share now)`, so using it while it is up counts as ending it |

The mechanic was read off the engine: `onFieldRestart` calls
`removePseudoWeather('trickroom')`.

## The instrument check

| | | pre-registered |
| --- | --- | --- |
| decisions compared | 550 | |
| a Trick Room move was legal | 72 — 13.1% | 5–25% ✓ |
| its score moved | 55 — 10.0% (76% of those) | 50–95% of those ✓ |
| the choice differed | **3 — 0.5%** | 1–10% ✗ |
| differed with no Trick Room legal | **0** | must be 0 ✓ |

## The measurement

| | |
| --- | --- |
| by-speed vs flat, 800 battles | 406 / 394 — **50.7%** |
| 95% Wilson | [47.3%, 54.2%] |

**Neutral. By the stopping rule written before the run, `trick_room_by_speed`
stays off** and the number is recorded, as 0048's was.

## Two predictions missed

- **The choice changed on 3 decisions of 550**, below the 1–10% band.
- **The win rate did not clear**, though the pre-registration called it more
  likely to than 0050's because the old price was wrong in sign rather than in
  size.

The shape is 0049's again: the price moved on 55 decisions and decided 3.
Swinging Trick Room between −55 and +55 changes its rank only where it was
already close to the best move, and in this agent it rarely is — a positive
Trick Room was already worth the old +55, and pushing a move the agent was not
choosing further down changes nothing.

What this measures is **the agent**, not the mechanic. A player who uses Trick
Room deliberately — to end an opposing one — is not described by a policy that
almost never reaches for the move in the first place.

## Still not modelled

- how many turns an active Trick Room has left (the tracker's
  `field_conditions` counter never counts)
- the benches: only Pokemon on the field are compared

## Hygiene

Pool teams only.
