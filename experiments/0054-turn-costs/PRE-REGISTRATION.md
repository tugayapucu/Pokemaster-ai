# 0054 — Moves that cost a turn, priced as the turn they cost

**Written before the measurement was run.** Registered 2026-09-13.

## The defects

Found while reviewing why Team Preview ratings moved after 0053.

1. **Recharge moves were free.** Six moves carry the engine's `recharge` flag
   (Hyper Beam on 6.2% of pool teams); it was loaded and never read, so the
   move scorer priced each as a full hit with no lost turn.
2. **`matchup()` never learned about either kind.** Bug 1 (0050) taught the
   in-battle move scorer about charge turns, but `matchup()` — Team Preview and
   every switch — still priced a charging Solar Beam or Electro Shot, and every
   recharge move, as a free instant hit.

## The rule, read off the engine

A recharge move's `self: { volatileStatus: 'mustrecharge' }` is applied by
`selfDrops`, which skips targets the move did not hit. A miss costs no
recharge; a hit does, knockout included. Hence

    recharge_multiplier = 1 / (1 + accuracy)

— derived, not tuned: half for a move that cannot miss, slightly more for one
that can. Charge moves keep 0050's 0.5, and in `matchup()` a charging move also
cannot win this turn's knockout race.

## Two changes, measured separately

| | change | flag |
| --- | --- | --- |
| **E** | the in-battle move scorer prices recharge moves | `recharge_turns`, on |
| **F** | `matchup()` prices charge and recharge moves, for Team Preview and switching | `matchup_turn_costs`, on |

Both are engine facts: they ship unless they clear their interval **downward**.

## Instrument checks — teams drawn at random

Following 0053's method note, every check draws from the pool at random rather
than taking the first teams in file order.

| | E | F |
| --- | --- | --- |
| battles driven by the new agent, the old one asked at each decision | 20 random matchups | 20 random matchups |
| precondition | a recharge move is legal | — |
| score of such a move moved / choice differed | reported | choice differed reported |
| differed without the precondition | **must be 0** | — |
| Team Preview previews over 40 random teams | — | picks differ, reported |
| precondition | — | our team carries a charge or recharge move |
| picks differ without it | — | **must be 0** |

## Predictions

Wide, as since 0049.

| | E | F |
| --- | --- | --- |
| precondition holds | 1–6% of decisions | 15–35% of teams |
| choice / picks differ | 0.3–3% of decisions | 5–25% of previews; 0.2–3% of battle decisions |
| A/B, 400 battles | neutral | neutral |

## Hygiene

Pool teams and synthetic fixtures only.
