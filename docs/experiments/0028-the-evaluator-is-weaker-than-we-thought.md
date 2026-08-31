# Experiment 0028 — The evaluator is weaker on real teams, and blind early

**Date:** 2026-08-31
**Result: `evaluate_position` drops from 79.7% to 74.6% at naming the eventual winner, and from 71.0% to 57.6% on the first two turns.** Experiment 0021 measured it on the singles-generated pool that 0024 later found unrepresentative. Re-measured on the frozen pool of harvested teams, it is worse everywhere except the late game — and on turns 1–2 it is barely better than a coin flip. Both remaining backlog items rest on this number, which is why it was re-checked before anything was built on it.

## The re-measurement

Same method as 0021 — sign of `advantage` against who actually won, teams exchanged on alternate battles, positions scoring exactly zero abstained rather than counted. Run on the frozen 200-team pool so it is reproducible.

```
                       n     frozen pool    0021, old pool
  turns 1-2          512        57.6%           71.0%
  turns 3-5          883        71.8%           81.0%
  turns 6-9         1135        79.1%           85.7%
  turns 10+         1286        79.3%           74.5%
  overall           3816        74.6%           79.7%

  slim   (<50)      1256        65.2%           66.1%
  clear  (50-150)   1259        72.6%           82.7%
  large  (>150)     1301        85.6%           86.2%
```

Median battle length 13 turns against 8.5, so the turn bands cover a different fraction of the game — turns 10+ is now a large and well-populated band rather than a tail, which is most of why that one improved.

## What survived and what did not

**Still monotone in its own confidence**: 65.2% slim, 72.6% clear, 85.6% large. That is the property a search actually needs — the evaluator knows when it is guessing — and it is intact.

**The early game collapsed.** 57.6% on turns 1–2 is close to nothing. `evaluate_position` scores only HP and fainting, and on turn one nobody has taken damage, so its whole signal is which side happens to have revealed less. On the generated pool that correlated with something; on real teams it does not.

**The clear band lost ten points**, from 82.7% to 72.6%. A 50–150 advantage is roughly one Pokémon's worth of HP, and on real teams that is much less decisive than it was — battles run half again as long, every team carries Protect, and speed control can undo a health lead outright.

## Why this matters more than the headline number

Experiment 0022 found the search's lookahead inert and, when woken, nine points worse, and diagnosed a currency mismatch: `evaluate_position` is the natural currency for both halves, but it prices only HP, so a search maximising it would stop using Protect, Tailwind and every status move.

That argument stands, and this sharpens it. **A search compares positions a turn or two ahead, and one to two turns ahead is exactly where the evaluator is now weakest.** Improving it is not a refinement of Milestone 7; it is the precondition for search being worth trying at all.

## Targets

Anything replacing this should be graded the same way, against the same frozen pool, and should beat:

```
  turns 1-2         57.6%      <- the one that matters most for lookahead
  clear (50-150)    72.6%
  overall           74.6%
```

and must keep monotonicity across the confidence bands, which is the property that makes an evaluator usable rather than merely accurate.

## Not established

- Whether a better evaluator makes search pay. 0022 is a standing reminder that it may not, and the honest order is to improve the evaluator to a measured target first and re-test search second, with the option to stop if the first step does not move.
- Whether the drop is the pool or the longer battles. Both changed together and this does not separate them, though the early-game collapse points at composition rather than length.
