# Experiment 0017 — The Mega formes themselves are not the problem

**Date:** 2026-08-25
**Result: per-forme damage errors account for 6.5% of the misses.** A targeted 19,802-hit measurement across 71 distinct Mega Stone holders found almost every forme predicted within ±3% bias, and fixing the six worst outright would move the overall figure by **+1.36 points** against a gap of roughly thirteen. Two real bugs were found and fixed on the way; neither is large enough to matter globally.

This closes the "identify the Mega formes carrying the eleven points" line. They do not carry it.

## A better instrument

Random 24-team pools gave Ampharos-Mega **fourteen** hits in 250 battles — thinner than anything this project has acted on. Instead of brute-forcing more random battles, the pool is weighted: generate a wide field of legal teams and keep those carrying a Mega Stone. The format turns out to be dense with them — **149 of 150 generated teams carry one, across 71 distinct holders** — so this costs nothing in realism.

Teams still come from Showdown's generator. Hand-building movesets would need learnsets and would risk measuring an illegal set.

## Both standing leads were noise

```
                        thin sample      targeted sample
Ampharos-Mega ATK       1.650 (n=14)     0.990 (n= 61)
Ampharos-Mega DEF            —           0.990 (n=115)
```

Mold Breaker is not a damage error at all. Implementing on n=14, which the backlog was one step from doing, would have added a wrong multiplier and then "confirmed" it against the same thin sample.

Parental Bond, fixed in 0016, verified in passing: Kangaskhan-Mega ATK **1.200 → 0.991** on n=92.

## Ranking by bias was the wrong question

Suspects had been ranked by median ratio. The gap being chased is measured in *inside-range accuracy*, and the two come apart:

```
ATK Pyroar-Mega   n=66   accuracy 65.2%   median 1.003
```

A perfect median with 65% accuracy. Re-ranked by accuracy the list changed completely, and the new top shared an obvious family:

```
ATK Glalie-Mega      n=136   accuracy 50.7%   Refrigerate
ATK Altaria-Mega     n= 52   accuracy 51.9%   Pixilate
ATK Meganium-Mega    n=215   accuracy 55.3%   Mega Sol      (unmodelled)
DEF Staraptor-Mega   n=108   accuracy 61.1%   Contrary      (unmodelled)
DEF Blaziken-Mega    n= 55   accuracy 69.1%   Speed Boost
ATK Feraligatr-Mega  n= 82   accuracy 72.0%   Dragonize
ALL HITS             n=19802 accuracy 78.9%
```

**A conditional-in-the-model, unconditional-in-the-game effect has exactly this signature** — unbiased on average, badly wrong case by case — and a median-based hunt is structurally blind to it.

## Two fixes

**Fire Mane** was filed in `PINCH_ABILITIES` beside Blaze, firing only below a third of health, on the strength of its name. The engine has no HP condition:

```js
onModifyAtk(atk, attacker, defender, move) {
    if (move.type === 'Fire') return this.chainModify(1.5);
}
```

Unconditional ×1.5 on both attacking stats. Verified: **Pyroar-Mega 65.2% → 86.4%** on the identical 66 hits.

**Skill Link** forces the maximum hit count, so a 2–5 move goes to a flat 5 — ×1.58 on the average *and* it deletes the hit-count uncertainty that dominates our predicted range for those moves. Engine-correct and unit-tested, but honestly: Heracross-Mega never appeared among the worst formes by accuracy, so its measured contribution here is **not demonstrated**. It was found through the bias ranking, which this experiment just argued is the wrong lens.

## The number that closes the line

```
total misses in the 19,802-hit sample:   ~4158
misses inside the six worst formes:       ~270   (6.5%)
fixing all six to perfect would give:    +1.36 points
```

Ninety-three percent of the misses are spread across formes that look individually fine. Whatever costs the ~13 points is **not** a set of per-forme damage multipliers, and no amount of further ability transcription will find it.

## Where that leaves the investigation

Three explanations have now been tested and eliminated: field effects from Mega abilities (0016), a broad systematic bias (the control arm shows the same ±3–5% background), and per-forme damage errors (here).

What survives is that the gap is in the *range* rather than the centre — our predicted interval is wrong in a way that a median cannot see, and Skill Link is an example of the shape even if not of the size. The next pass should measure the **width** of our predictions against the engine's actual spread, rather than looking for another multiplier.

Still genuinely unmodelled and worth doing on their own merits, independent of this gap: **Mega Sol** (n=215), **Contrary** (n=108), and the `-ate` cluster's 50–52% accuracy, which is the worst thing in the measurement and involves abilities we *do* model — so it is a bug rather than an omission.
