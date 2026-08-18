# Experiment 0003 — Does pricing Protect by incoming threat help?

**Date:** 2026-08-18
**Git commit:** see `git log` for the `feat(agents): price Protect by what it blocks` commit
**Result: Split.** Human agreement improved significantly (p<0.01). **Play strength did not move at all.** Both are reported, because only one of them is the flattering half.

## Hypothesis

Experiment 0002 found the heuristic protected almost never — 90 of 643
disagreements with rated humans were a human protecting where it attacked.

The cause looked structural rather than a badly chosen constant. Protect
carried a flat 18 points plus a bonus when below 35% HP, which cannot express
either case that actually matters: a **healthy** Pokémon facing a knockout
should protect, and a **weakened** one facing nothing should not. Pricing it by
what it blocks should fix that.

## Change

Protect is worth the damage it avoids, in the same currency as damage dealt, so
the two compete directly.

| Part | Detail |
|---|---|
| **Threat drives value** | Revealed moves where they exist; otherwise a standard STAB attack assumed from the opponent's typing |
| **Streak discounts it** | Each consecutive use succeeds ⅓ as often — the engine's own stall rule, not a tuned constant |
| **Whole family counts** | The old code matched the literal id `protect` and silently missed Detect, Spiky Shield, King's Shield and the rest |

The "assume a STAB attack" part is the deliberate one. Experiment 0001 found
one-turn search was inert precisely *because* an opponent with no revealed
moves read as harmless. An unrevealed attacker must not score as safe.

## Result 1 — agreement with humans (improved)

Both versions were run over the same 50-game, 1,061-label set, so this is a
**paired** comparison. Confidence intervals overlap, but comparing them is the
wrong test for paired data — McNemar's looks only at the labels where the two
versions disagree with each other, which is where all the information is.

```
old  418/1061 = 39.4%  (CI 36.5%-42.4%)
new  439/1061 = 41.4%  (CI 38.4%-44.4%)

both agreed : 408      only OLD agreed : 10
neither     : 612      only NEW agreed : 31

McNemar chi2 = 9.76 on 41 discordant labels    significant at p<0.01
Protect misses: 90 -> 70
```

**It is calibrated, not merely more eager**, which was the obvious risk:

| | Protect rate |
|---|---|
| Humans | 150/1061 = **14.1%** |
| heuristic (new) | 151/1061 = **14.2%** |

Frequency now matches almost exactly; the residual disagreement is about *when*
to protect, not *whether*.

## Result 2 — play strength (unchanged)

Agreement is not strength, so this was checked separately.

```
protect-aware vs flat-protect, 200 battles: 55.5%  (CI 48.6%-62.2%, not significant)
protect-aware vs flat-protect, 800 battles: 51.6%  (CI 48.2%-55.1%, not significant)

protect-aware vs random, 200 battles: 96.0%  (CI 92.3%-98.0%)
flat-protect  vs random, 200 battles: 96.5%  (CI 93.0%-98.3%)
```

The 200-battle run suggested 55.5%; at 800 it regressed to 51.6%. **The first
number was noise**, and is recorded here because stopping at 200 would have
produced a false claim.

### Why strength did not move

Two reasons, and the first is the same one Experiment 0001 ran into:

1. **The two versions mostly agree with each other.** They differ only on
   Protect decisions — about 14% of slots, and they agree on half of those. Two
   policies that agree on the large majority of turns will split a head-to-head
   near 50% whatever the merits of the difference.
2. **Self-play cannot see a shared blind spot.** Both agents price everything
   else in immediate damage. A change that fixes one shared weakness is tested
   against an opponent with the same weakness, on a pool of generated teams
   that may not be built around Protect the way ladder teams are.

## Conclusion

**Kept.** Not because it wins more — that is unproven — but because it is
better-motivated, fixes a real coverage bug (the entire Protect family was
invisible), replaces a magic constant with the game's own stall rule, and is
measurably closer to human judgement at p<0.01 with no measurable cost.

The wider lesson is about the metrics themselves. Human agreement detected a
real, significant behavioural change on 1,061 labels that **800 self-play
battles could not distinguish from noise.** For changes of this size,
agreement is the more sensitive instrument — which is exactly what an external
benchmark is for.

## Next actions

- **Switching next**, now the largest single gap: humans switch on 11.0% of
  decisions, the heuristic on 1.7%, and it agrees on only 8 of 117 switch
  labels. Unlike Protect this needs a notion of matchup value the heuristic
  does not yet have.
- **Targeting after that** — 17% of remaining disagreements are the right move
  aimed at the wrong Pokémon.
- **Stop using self-play head-to-head as the primary signal for scoring
  tweaks.** It is underpowered against a near-identical opponent. Use it to
  confirm no regression, and agreement to detect improvement.
- Replace the assumed-STAB prior with something inferred from usage data when
  opponent modelling (Milestone 10) lands.
