# Experiment 0015 — Mega costs seven points, and not where expected

**Date:** 2026-08-25
**Result: enabling Mega Evolution costs the damage model about seven points, and 75–85% of that loss is on hits that do not involve a Mega at all.** The Mega'd Pokémon are predicted roughly as well as anything else. What breaks is everything *around* them — which points the follow-up work at the field effects Mega abilities create, not at the Mega formes' stats or typing.

Replicated across two seeded team pools, 800 battles per arm.

## Two false starts, both worth recording

The first attempt produced a number twice and both were worthless.

**The harness was discarding the evidence.** `active_by_ident` resolved a protocol ident to a Pokémon by matching species names. A Pokémon that Mega Evolves keeps its ident — `p1a: Metagross` — while its set becomes `Metagross-Mega`. The names stop agreeing, the lookup returns `None`, and a failed lookup does not mis-attribute a hit, it **drops** it. So *"Mega has never been measured"* was true even of the runs that switched Mega on. Fixed by resolving on slot.

**The pool was unseeded.** Two runs of the same comparison disagreed in direction, because `TeamPool.generated` drew fresh teams each time and that swing was larger than the effect. Fixed by threading a seed through `Teams.generate`.

Neither is a modelling bug. Both are measurement bugs, and each one silently produced a plausible-looking number.

## The measurement

Same seeded pool through two arms — never Mega, and Mega at the first opportunity.

```
                         seed 1                    seed 7
                    (24 teams, ~30 stones)    (24 teams, ~37 stones)

never Mega            93.9%  (n= 9991)          91.2%  (n=10156)
always Mega           87.3%  (n= 9717)          83.2%  (n=10042)
                     -6.6 points               -8.0 points

  involves a Mega     88.3%  (n= 1751)          78.6%  (n= 1583)
  no Mega on field    87.0%  (n= 7966)          84.0%  (n= 8459)
```

## Where the loss actually is

Attributing the extra wrong predictions against each seed's own baseline:

```
seed 1:  ~641 extra wrong    15% from Mega hits    85% from non-Mega hits
seed 7:  ~803 extra wrong    25% from Mega hits    75% from non-Mega hits
```

The **non-Mega** bucket is the consistent one. It drops 6.9 and 7.2 points across the two seeds, on ~8,000 hits each — a large, stable, replicated effect on hits where neither the attacker nor the defender has Mega Evolved.

The **Mega** bucket is not stable: 88.3% and 78.6%, a 9.7-point spread on ~1,700 hits. Which Mega formes a pool happens to draw evidently matters more than anything general about Mega. No conclusion is drawn from it.

## What that means

Something a Mega brings onto the field is degrading prediction for **everyone**, and it is worth more than three times what the Mega formes' own stats and typing are worth.

The candidates, from the 33 unmodelled abilities on Mega formes, are the ones whose effect is not confined to their holder:

- **Drought, Sand Stream, Snow Warning, Electric Surge** — set weather or terrain, which multiplies damage for every Pokémon on the field.
- **Fairy Aura** (Floette-Mega) — raises *every* Fairy move by 1.33, on both sides.
- **Intimidate** (Manectric-Mega, Scrafty-Mega) — fires on the forme change, not only on entry.

The holder-only abilities that looked like obvious wins before this measurement — **Parental Bond** (×1.5 in effect), **Skill Link**, **Protean**, **Mold Breaker** — can only be worth the smaller share, because they only touch hits the Mega is party to. That is the opposite of the priority order the backlog had, and the reason to measure before building.

## Not established

- Which specific field effect dominates. The weather split from an earlier run was not clean enough to separate them, and it needs its own pass.
- Whether the agent should Mega. Nothing here says that; the agent still does not read `action.special` at all. Deliberately left until the model can price a Mega correctly, because building the judgement before the arithmetic is what went wrong in 0013.

## Two engine bugs found on the way

Neither is about Mega; both were found because 800-battle runs visit states 90-battle runs do not, and both would have crashed the agent in a long real game.

- `legal_slot_actions` offered `PassAction` whenever its filters left nothing, and a pass is legal only for an empty or fainted slot. Reachable by ordinary PP exhaustion.
- The first fix conflated two situations that want opposite answers — a move we could not target, and a move genuinely spent — and offering disabled moves got them rejected as unavailable. Targeting and availability are now relaxed separately, with Struggle as the true last resort.
