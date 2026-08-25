# Experiment 0016 — The field-effect hypothesis was wrong

**Date:** 2026-08-25
**Result: refuted.** Experiment 0015 measured that enabling Mega costs ~7 points of damage accuracy and that most of the loss falls on hits where neither side has Mega Evolved, then explained it by field effects — weather setters, auras, Intimidate. Tested directly, **bystander hits are marginally *better* with a Mega on the field**, in both seeds. The explanation was wrong.

What the test found instead is sharper and more useful: the two arms are **identical through turn 3**, then the Mega arm loses ~11 points and never recovers. Following that residual found **Parental Bond**, now implemented and verified.

## The hypothesis, and its refutation

If a Mega's field effects were degrading bystanders, then a bystander hit taken while a Mega stands on the field should be worse than one taken while none does. It is not:

```
                                 seed 1              seed 7
bystander, a Mega IS on field   88.8% (n=1157)    84.9% (n= 784)
bystander, no Mega on field     86.7% (n=6809)    83.9% (n=7675)
```

Both seeds put the "Mega present" bucket *ahead*, by 2.1 and 1.0 points. Subdividing by whether the Mega's ability sets weather, sets terrain, carries an aura or is Intimidate found nothing that survived a floor of 20 samples in both seeds.

The candidates named in 0015 are not exonerated as mechanics — Drought and Fairy Aura are still unmodelled and still real. They are exonerated as the *explanation for this gap*.

## What is actually going on

Bucketing every hit by turn, both arms, same seeded pool:

```
              always Mega        never Mega        gap
turns 1-3     89.0% (n=2526)    89.2% (n=2529)    -0.2
turns 4-7     80.5% (n=3217)    91.4% (n=3237)   -10.9
turns 8-14    81.1% (n=3606)    92.0% (n=3690)   -10.9
turns 15+     84.4% (n= 693)    92.9% (n= 700)    -8.5
```

Two things this settles:

- **It is not a mix effect.** The hit counts per band are near-identical between arms (2526/2529, 3217/3237, 3606/3690, 693/700), so the Mega arm is not simply spending more of its time in a harder part of the game.
- **The arms agree exactly until turn 3.** Whatever costs the 11 points is something a Mega *leaves behind*, not something about the moment it evolves.

## Following the residual

Grouping the Mega arm's turn-3-onward mismatches:

```
by attacker                          by move
  Kangaskhan-Mega  n=92  1.200         crunch       n=27  1.233
  Ampharos         n=14  1.650         suckerpunch  n=51  1.143
  Ditto            n=12  1.591
```

Kangaskhan-Mega is **Parental Bond**, and Crunch and Sucker Punch are moves it learns — the move axis was showing the same effect from the other side.

The engine does not treat Parental Bond as a damage modifier. It sets `move.multihit = 2` and scales the *second* hit in `modifyDamage`:

```js
const bondModifier = this.battle.gen > 6 ? 0.25 : 0.5;
```

So in this generation the pair comes to **1.25×**, not the 1.5× the older games gave and not the 1.5× the backlog had written down. The measured 1.200 across 92 hits is that, and finding the constant before reading the source is what made it easy to trust.

Implemented, and re-measured on the identical 2,298 samples:

```
mismatches from turn 3 on:   449  ->  391     (-13%)
Kangaskhan-Mega, crunch and sucker punch all leave the worst-offenders list
```

## Still open

The broad residual is a **~3–4% over-prediction spread across many attackers** (medians clustering at 0.95–0.97), not one ability. Parental Bond was the largest single contributor and it does not account for the 11 points. Two smaller leads with real magnitude but thin samples:

- **Ampharos** n=14, median 1.650 — Mega Ampharos has Mold Breaker, which ignores the defender's ability. Unmodelled.
- **Ditto** n=12, median 1.591 — Imposter copies the target, and we model Ditto's own base stats.

Neither is measured well enough to act on. The next pass should widen the sample rather than implement on n=14 — a weak signal implemented as a strong one has already cost this project once (0013).

## The methodological note

0015's numbers were right and its explanation was wrong, which is a specific failure worth naming: an attribution was inferred from *where* the loss was not (Mega hits) rather than tested *where* it was. The bucket that carried the loss was described as "hits that do not involve a Mega", and that phrase quietly became "hits affected by a Mega's field presence" without a measurement in between.
