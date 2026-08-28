# Experiment 0022 — The search lookahead was inert, and waking it up made things worse

**Date:** 2026-08-25
**Result: two findings, one good and one uncomfortable.** The search's retaliation term had a **median of exactly zero** — more than half of all decisions were the heuristic wearing a hat. Fixing that made the search **significantly worse**: 41.0% against the heuristic over 1,600 battles (95% CI 38.6–43.4%, p < 0.0001), down from the ~49.3% experiment 0001 measured. Reverted.

## What 0001 got right, and where its fix went

Experiment 0001 found one-turn search inert and diagnosed the cause: unrevealed opponents were being treated as harmless. The prescription was written down and applied — to `HeuristicAgent._threat_from`, whose docstring still says so:

> *"When there are none the opponent is **not** treated as harmless — experiment 0001 found that assumption is exactly why one-turn search was inert. A standard STAB attack is assumed instead."*

**It was never applied to the search.** `SearchAgent._threats` counted only revealed damaging moves, so in a five-turn format where most opponents have revealed nothing, the threat was zero:

```
404 decisions over 60 battles

|immediate|  (heuristic currency)     median  163.4
|lookahead|  (position-value units)   median    0.0
decisions the lookahead changed:      9.4%
```

That also explains why 0001's *recorded* explanation — "opponent knowledge is the bottleneck" — misled three later experiments (0005, 0018, 0019 all went looking for value in opponent knowledge and found little). The diagnosis was nearly right; the actionable form of it was a one-line fallback that landed in the wrong module.

## Waking it up

```
                              before    after
median |lookahead|              0.0      27.6   (15% of the term it corrects)
decisions it changed            9.4%     18.2%
```

The lookahead genuinely operated. And the agent got worse:

```
seed 1   336/800  = 42.0%   (95% CI 38.6%-45.5%)
seed 7   320/800  = 40.0%   (95% CI 36.7%-43.4%)
pooled   656/1600 = 41.0%   (95% CI 38.6%-43.4%)   z = -7.20, p < 0.0001
```

Both seeds agree. This is not noise, and it is a larger effect than most of the improvements measured in this project.

## Why, most likely

The score is `immediate - threat * exposure`, and the two halves are **in different currencies**. `immediate` is the heuristic's fitted action score; the threat term is built from `POKEMON_WEIGHT` and `HP_WEIGHT`, the position-value units. Subtracting one from the other is not a comparison.

While the threat term was zero the mismatch was harmless. Making it live made a mis-scaled penalty real, and a penalty that is too large makes an agent too cautious — it over-buys Protect and switching against a threat it is assuming rather than seeing.

That is the same direction as experiment 0005's odd finding that perfect knowledge of the opponent's move *this turn* made the agent **worse**. Threat information that is not correctly priced appears to be actively harmful here, twice now.

## Reverted, and what is left standing

The change is reverted: a baseline nine points worse for a reason not yet fixed is not a useful baseline. What survives is knowledge:

- **The lookahead was inert**, measured, not guessed — median zero across 404 decisions.
- **0001's fix went to the wrong module**, and its recorded explanation sent three experiments looking in the wrong place.
- **Correct information, wrongly priced, made the agent worse** by nine points. The information was not the missing piece.

## What would have to be true to try again

Both terms in the same currency. The position-value one is the candidate, because 0021 measured it at 79.7% for naming the winner while the heuristic's constants were fitted for agreement — but that swap has a real obstacle: **`evaluate_position` scores only HP and fainting**, so Protect, Tailwind, Swords Dance and every other status move price at exactly zero. A search that maximises it would stop using them entirely.

So "give search the evaluator" is not the one-line change it looked like. It needs an evaluator that can price a stat stage and a field effect — which is Milestone 7's job, and is now the better-motivated item.
