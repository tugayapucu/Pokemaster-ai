# 0048 — Does predicting the field at Team Preview change the pick?

**Written before the measurement was run.** Registered 2026-09-12.

## The change

`matchup_table` scores our six against theirs on a **bare field**, with a
comment saying so: *"No weather at Team Preview: the battle has not started, so
none is set yet."* True, and beside the point — a team with Pelipper is going
to be in rain, and the grid is scoring a battle that will not happen.

Each predicted effect now contributes its marginal change to every cell,
weighted by how likely it is.

## What the prediction is worth, measured rather than asserted

`P(effect is up | species was previewed)`, end to end from the corpus. It folds
in the two things an ability table cannot know: they bring four of six, and a
setter can be beaten to it or faint first.

| species | effect | previewed | P |
| --- | --- | --- | --- |
| Rillaboom | grassy terrain | 2,941 | 59% |
| Indeedee-F | psychic terrain | 1,657 | **73%** |
| Pelipper | rain | 1,221 | 68% |
| Ninetales-Alola | snow | 376 | 64% |
| Charizard | sun | 502 | 45% |

Twelve species in all. **Charizard is the one worth noting**: it does not set
sun, Charizard-Mega-Y does, so 45% is how often it Megas that way. Nothing was
told that; it fell out of measuring the chain end to end.

## Why weighting matters here

Asserting rain on sight of Pelipper is wrong in **three games out of ten**. The
whole design rests on the prior being a weight rather than a switch, which is
also what makes a 45% predictor usable instead of discardable.

## The instrument check, which comes first this time

0047 measured a change that never fired and returned 200/200 — the exact number
two identical agents produce. **Before reading any win rate, this run counts how
many Team Preview picks actually differ between the two arms.** If that count is
zero the result is reported as a no-op and nothing else is claimed.

Three times now a number has looked reasonable while being computed from
nothing: `0 samples dropped` in 0046, an eleven-observation lift table in
`meta`, and 200/200 in 0047. The check is cheap.

## Design

`evaluate` over the harvested M-C pool, the same agent on both sides but for
this flag, agents swapped between the two passes of every matchup on a shared
seed. **400 battles, seed 0.** One run.

## Prediction

**Picks will differ — somewhere between 10% and 40% of previews**, since 12
species covers a large share of the field and the shift is 0.3 of an HP bar in
the cells that move.

**Win rate: neutral to slightly positive, and I expect it not to clear its
interval.** Team Preview is one decision per battle against roughly twenty
in-battle ones, so even a strictly better pick is a small share of what decides
a game. 0031 also put 93% of outcome variance on the matchup itself, and
choosing four of six moves that only at the margin.

## Stopping rule

One run at 400 battles. Ships only if the interval excludes 50%. Neutral means
off by default with the number recorded, as `tenure_boosts` and the ability
prior already are.

## What each outcome means

| result | conclusion |
| --- | --- |
| picks identical | a no-op; report it as one and find out why, as in 0047 |
| picks differ, win rate up | the first judgement change to pay in this project since Mega and switching |
| picks differ, neutral | better-informed picks that do not convert. Keep off, record it, and note that Team Preview may simply be too small a lever |
| picks differ, win rate down | the prediction is worse than ignorance — most likely because a 45% predictor applied as a weight still misleads more than it helps |
