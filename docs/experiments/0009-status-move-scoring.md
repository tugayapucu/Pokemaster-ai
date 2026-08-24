# Experiment 0009 — Pricing status moves

**Date:** 2026-08-24
**Result: the largest agreement gain the project has measured.** Agreement on the slots where a human played a status move went **32.2% → 37.1%**, and overall agreement **43.2% → 43.8%** (McNemar χ² = 16.54, **p = 4.8×10⁻⁵**). Play strength is unchanged, which was the expectation before the work rather than after.

## The gap

An audit of every engine field on the 500 moves in this dex against what `MoveInfo` carried turned this up:

> **175 of 500 moves are Status moves, and every one except Protect scored a flat 12.0.**

Swords Dance, Thunder Wave, Recover, Tailwind and Trick Room were literally the same number to the agent. The fields that separate them — `boosts`, `status`, `heal`, `volatileStatus`, `sideCondition`, `weather`, `terrain`, `pseudoWeather` — had never been dumped from the engine at all.

The sharper half of the problem was **redundancy**. A flat value cannot express "this does nothing right now", so:

- Recover at full HP scored exactly as much as Recover at 5%.
- Swords Dance at +6 scored exactly as much as the first one.
- A second Tailwind, with Tailwind already up, scored exactly as much as the first.
- Thunder Wave into an Electric type scored exactly as much as into anything else.

## What it is priced in

The important design constraint: **three of the four prices are not new judgements.**

| Effect | Priced with | Which is |
|---|---|---|
| Stat stages | `STAT_STAGE_VALUE` | what a +2 rider on an attack is already worth |
| Status | `STATUS_VALUE` | what a burn rider is already worth |
| Healing | `SUSTAIN_WEIGHT` | what a drain of the same size is already worth |
| Screens | the incoming threat | how Protect is already priced |

So a Swords Dance is worth what a Swords Dance rider is worth, and a Recover is worth what an equivalent drain is worth. Nothing about a move being "a status move" changes what it buys. That framing meant almost no new constants had to be invented, and the ones that were — the side-condition, weather and volatile tables — are judgements in exactly the sense `STATUS_VALUE` is, and are labelled that way in the code.

**Fifty-six of the 175 keep the flat value**, because their effects live in an `onHit` callback the engine cannot dump: Belly Drum, Haze, Heal Bell, Defog, Baton Pass. Those are *unknown* rather than worthless, and a flat value says so honestly.

## Results

Human agreement is the right instrument here and self-play is not: a self-play opponent shares exactly the blind spot being fixed, while the corpus is 500 rated games of people who do not.

```
                             overall      on status-move slots
flat value (before)           43.2%            32.2%   (1082/3356)
priced (after)                43.8%            37.1%   (1245/3356)

McNemar   203 newly agree, 128 newly disagree
          chi2 = 16.54, p = 4.8e-05
```

Per move, where the two versions differ:

```
  tailwind      223    25% -> 57%        taunt         27    11% -> 37%
  trickroom     175    32% -> 42%        auroraveil    20    40% -> 70%
  shellsmash     23    13% -> 74%        recover       12     8% -> 50%
  lightscreen    48    38% -> 56%        sleeppowder   50    16% -> 34%
  helpinghand    71    25% -> 39%        coil          22    64% -> 100%
```

**Not everything improved.** Protect slipped **45% → 44% on 1,430 labels**, which is the largest absolute cost — other status moves now outbid it sometimes. Perish Song (17% → 12%), Follow Me (45% → 43%) and Will-O-Wisp (10% → 8%) each lost a little. Those are real and are not smoothed over.

## Two mistakes worth recording

**The first McNemar was wrong.** I paired the two runs' comparisons by `(turn, player, slot)` — which is not unique across 500 replays, so thousands of comparisons collapsed onto each other and it reported χ² = 20.95 on 2,830 vs 2,495 "flipped" decisions. The tell was that the net (+335) did not match the actual change in matches (+69). Both runs walk the same decisions in the same order, so the fix is to pair positionally, with an assertion that the human labels line up. The corrected figures are the ones above.

**`BOOST_FIELDS` omitted accuracy and evasion.** They are stat stages like any other, so the tracker was dropping `|-boost|...|accuracy|1` on the floor and the scorer was ignoring half of Coil — which goes **64% → 100%** agreement once counted. The table also existed in *two* copies, one in `domain` and one in `simulator`, which is the same drift that had `estimate_damage` reading the type chart directly while a move-aware `Dex.effectiveness` sat unused beside it. There is now one.

## Strength

1,600 paired battles across two seeds against a copy carrying the flat value, on the same teams:

```
seed 4242   51.6%   (95% CI 48.2-55.1, not significant)   margin +0.01
seed   99   48.4%   (95% CI 44.9-51.8, not significant)   margin -0.11
```

**Strength-neutral**, seeds disagreeing in direction — the same result as every correctness fix in this project, and expected: both agents share the blind spot in self-play, so neither can punish the other for it. The measurement that moved is agreement with humans, which is the one that says whether a *recommendation* is any good.

## What this leaves open

- The 56 `onHit` moves still score flat. Some are important — **Belly Drum**, **Haze** and **Defog** especially — and each would need its own rule rather than a dumped field.
- The side-condition, weather and volatile tables are unvalidated judgements. The per-move agreement breakdown above is the instrument for tuning them, and Tailwind at 57% suggests there is more left in it.
- **Protect's regression** is unexplained beyond "it gets outbid now". Whether the new prices are too generous or Protect's was always too generous is a real question the same instrument can answer.
