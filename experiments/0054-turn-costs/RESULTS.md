# 0054 — Moves that cost a turn: both ship, one A/B measured nothing

Run 2026-09-13 against the pre-registration in this directory.

## What was built

| commit | what |
| --- | --- |
| `e5a9c89` | `recharge_multiplier`: 1 / (1 + accuracy), derived from when the engine applies `mustrecharge` |
| `ea53668` | **E**, `recharge_turns` (on): the in-battle move scorer prices recharge moves |
| `56b9804` | `matchup()` can price charge and recharge moves (`price_turn_costs`, off by default) |
| `8e37cc5` | **F**, `matchup_turn_costs` (on): Team Preview and switch scoring opt in |

The recharge rule was read off the engine, not assumed. `self: { volatileStatus:
'mustrecharge' }` is applied by `BattleActions.selfDrops`, which skips every
target the move did not hit — so a miss costs no recharge, while a hit does,
knockout and substitute included.

## E — recharge moves in the move scorer

| | | pre-registered |
| --- | --- | --- |
| battle decisions compared, 20 random matchups | 452 | |
| a recharge move was legal | 3 — **0.7%** | 1–6% ✗ |
| its score moved | 3 | |
| decisions that differed | 2 — 0.4% | 0.3–3% ✓ |
| differed with no recharge move legal | **0**, of 449 able to test it | must be 0 ✓ |
| recharge-priced vs free, 400 battles | **200 / 200** | neutral |

## F — `matchup()` prices charge and recharge moves

| | | pre-registered |
| --- | --- | --- |
| previews, 40 random teams | 1,560 | |
| our team carries such a move | 312 — 20% | 15–35% ✓ |
| Team Preview picks differed | 91 — 6% | 5–25% ✓ |
| differed without such a move | **0**, of 1,248 able to test it | must be 0 ✓ |
| battle decisions differed | 2 of 452 — 0.4% | 0.2–3% ✓ |
| matchup-costs vs free, 400 battles | **200 / 200** | neutral |

## Two 200/200s, checked before either was believed

200/200 is exactly what two identical agents produce — the signature 0047's no-op
left. Both instrument checks showed the arms differ, so neither is a no-op by
construction; what remained was whether the A/B had measured anything. Re-run
with per-matchup scores kept:

| | matchups decided | total turns | reading |
| --- | --- | --- | --- |
| E | **0 of 200** | 3,753 | **uninformative**: no battle's outcome changed |
| F | 2 of 200, one each way | 3,748 | neutral, on very little signal |

E is not "neutral". A recharge move is legal on 0.7% of decisions, and across
400 battles not one outcome turned on it. The A/B says nothing about E's value
either way.

**Both ship**, on the rule both were registered under: they are what the engine
does, and neither cleared its interval downward.

## A script bug, fixed before any result was read

The first launch of both comparisons crashed in the battle check: it seeded the
engine with `"check0"`, and the engine accepts only a numeric seed or
`"sodium,<hex>"`. The seed became `str(index)` and both were re-run; the Team
Preview check, which had completed before the crash, reproduced exactly.

## Still not modelled

- The semi-invulnerable turn of Fly, Dig, Dive, Bounce and Phantom Force.
- The second turn's own risks for a charge or recharge move — a switch, a
  Protect, fainting first — which would push both prices lower and are
  judgements.

## Hygiene

Pool teams and synthetic fixtures only.
