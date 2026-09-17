# 0060 — Break Mega ties toward the Mega

**Written before any battle was played with the setting on.** Registered 2026-09-17.

## The defect

The heuristic prices a Mega Evolution only through the move thrown that turn.
On a Protect turn, or with a move the forme does not strengthen, `X` and
`X + Mega` score exactly the same. `select_action` keeps the first of equal
totals, and legal actions list the non-Mega first, so every such tie goes
against the Mega. `test_mega_scoring` pinned the score tie as a known limit of
a one-turn scorer; which way it breaks was never decided, only enumerated.

The recommender does the same deliberately: ties go to the simpler action, and
the duplicate is dropped, so `position` never shows a Mega on such a turn.

What players do, from every Mega Evolution in the Reg M-C corpus (3,750
replays, 6,231 Megas):

| when | share |
| --- | --- |
| on the Pokemon's first turn out | 88.9% |
| one turn later | 9.5% |
| two or more turns later | 1.6% |
| leads, on turn 1 | 87.1% of 3,414 |

## The change

`HeuristicAgent(mega_on_ties=True)` (the commit before this one) takes the Mega
when its joint total **equals** the best joint total without one. A non-Mega
action scored strictly higher still wins. The recommender's ranking follows the
same setting. Team Preview is untouched.

This is a **judgement** — that Mega Evolving now beats later when this turn
cannot tell them apart — so it is measured against the shipped agent and ships
only if it clears upward.

## Measurement

| | what |
| --- | --- |
| battle decisions differ | on vs off, same observations, 20 pool matchups |
| **must be 0** | differing decisions that are not "on takes a Mega where off did not, at an equal joint total" |
| Mega timing | share of the agent's Mega Evolutions on the Pokemon's first turn out, self-play with the setting on and with it off, 20 pool matchups each, measured the same way as the corpus figure |
| A/B | `evaluate`, on against off, 800 battles, pool `data/pool-champions.txt`, seed 60 |
| reported | record, 95% Wilson, decided matchups |

## Predictions

| | prediction |
| --- | --- |
| battle decisions differ | 1–5% |
| must-be-0 row | 0 |
| first-turn-out Megas, setting off | 40–70% |
| first-turn-out Megas, setting on | 85% or higher |
| A/B | 50–54%, most likely not clearing |

## Adoption rule

`mega_on_ties` defaults on only if the A/B's **95% Wilson lower bound is above
50%**. Otherwise it stays off and the result is recorded as it comes out; the
setting remains available to scouts and to `position`.

If the must-be-0 row is not 0, the change is not what it claims and the A/B is
not run.

## Hygiene

Pool teams only.
