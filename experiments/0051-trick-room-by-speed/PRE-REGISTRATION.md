# 0051 — Trick Room priced by whether the speed flip helps us

**Written before the measurement was run.** Registered 2026-09-12.

## The defect

`_field_value` priced Trick Room at a flat `PSEUDO_WEATHER_VALUE["trickroom"]`
(55) whenever it was not up, and at **zero** whenever it was:

| situation | flat price | what the engine does |
| --- | --- | --- |
| not up, our side slower | +55 | sets it — good for us |
| not up, our side faster | +55 | sets it — hands them the speed order |
| up, they set it, we are faster | **0** | `onFieldRestart` → `removePseudoWeather('trickroom')`: **ends it** |
| up, we set it | 0 | ends our own |

The third row is the one the flat price could not see at all. Verified in
`data/moves.ts` at the pinned build.

## Why it matters in this format

In the harvested pool **56.4% of teams carry Trick Room**, and it is not an
artefact of the pool's move filling: 86% of fully revealed Indeedee-F sets
carry it (0050's write-up). Most battles contain a Trick Room user.

## The change

Behind `trick_room_by_speed`, **off by default**. Trick Room is priced as

    55 × speed_control_scale × (share after the flip − share now)

where the share is how often our active Pokemon move before theirs, pairing by
pairing, with priority held equal. It runs from −55 to +55, and a flip from
losing every pairing to winning every one is worth exactly the old flat price.

Not modelled, and stated so a result is not over-read:

- **turns left**: the tracker's `field_conditions` counter never increments, so
  an active Trick Room is treated as fresh
- **benches**: only Pokemon on the field are compared
- **the turn it is used**: Trick Room moves at −7, so the flip prices the turns
  after it — which is what it is for

## Why it is measured rather than shipped on correctness

Unlike 0049 and 0050, the *pricing* is a judgement. That using Trick Room ends
an active one is a fact; what flipping the order is worth, and whether a share
of pairings is the right measure of it, is not. 0036 is the warning: it swept
`speed_control_scale` from 0 to 8 and nothing beat the shipped 1.0, with
"never use speed control" at 53.4%, p = 0.56. A flat, sign-blind price that is
indistinguishable from not using the move at all is consistent with a price
that is right on average and wrong in sign half the time — which is this
hypothesis — but it is equally consistent with speed control simply not
mattering to this agent.

## The instrument check

Over 20 battles driven by the new agent with the old one asked at every
decision:

| | |
| --- | --- |
| decisions compared | |
| a Trick Room move was legal | the ceiling |
| its score moved | does the change fire |
| the choice differed | does it decide anything |
| differed with no Trick Room legal | **must be 0** |

## Predictions

Wide, after 0049's order-of-magnitude miss.

| | prediction |
| --- | --- |
| Trick Room legal | 5–25% of decisions |
| score moved | 50–95% of those (a flip that exactly reproduces +55, or a tie, does not move) |
| choice differed | 1–10% of all decisions |
| win rate, 800 battles | positive, and more likely than 0050 to clear, because the old price was wrong in *sign* rather than magnitude |

## Stopping rule

**800 battles, seed 0**, one run — twice 0050, because Trick Room is on most
teams and the effect is expected to be larger but a judgement needs the power.

| result | decision |
| --- | --- |
| interval clears 50% upward | turn the flag **on** by default |
| neutral | keep off, record the number, as 0048 |
| interval clears 50% downward | keep off, and investigate the pricing |

## Hygiene

Pool teams only. No scouted candidate is used in this experiment, its fixtures
or its write-up.
