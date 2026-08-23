# Experiment 0008 — What is a held item actually worth?

**Date:** 2026-08-24
**Result: measured, not assumed.** Life Orb came out at **1.304** across 144 real hits — the exact 1.3 the plan had hypothesised for two sessions without evidence. It is also the **only** item in this dex that multiplies damage. Modelling items took damage prediction on item-holding teams from **87.5% to 94.8%**, level with the no-item control, and turn order on fully random teams from **91.0% to 97.7%**.

Following the residual afterwards found two further classes of bug that had nothing to do with items.

## Why this could be measured at all

The control team was built two sessions ago for exactly this. With the arithmetic verified to 94.8% on a no-item team and the abilities already filtered to inert ones, the residual on an *item-holding* team is the item effect and nothing else. That is the whole return on having built the control first: a question that was previously a guess became a reading.

```
held by the ATTACKER            n     median actual/predicted
  lifeorb                      144    1.304   <-- the engine's [5324, 4096]
  everything else (21 items)          ~1.00
```

Choice Scarf 0.976, Focus Sash 0.985, Leftovers 0.982 — all doing something, none of it damage. After modelling, Life Orb reads 0.979, which is the check that the table is consulted rather than merely present.

## The format is smaller than the game

Champions carries a restricted item list: **148 items**, with **Choice Band, Choice Specs, Assault Vest, Eviolite and the Arceus plates all absent**. So the table is far smaller than the full game would need — 44 items touch damage or Speed, in five families:

| Family | Count | Effect |
|---|---|---|
| Life Orb | 1 | ×1.3 final damage |
| Expert Belt | 1 | ×1.2, super-effective hits only |
| Type-boosting items | 18 | ×1.2 base power, one per type |
| Muscle Band / Wise Glasses | 2 | ×1.1 base power, by category |
| Resist berries | 18 | ×0.5 on a super-effective hit of their type |

Plus Light Ball, Choice Scarf and Iron Ball. The two eighteen-item tables were **extracted from the engine source programmatically**, not typed from memory, and a test checks every id against the item table the bridge dumps — because a typo makes an entry silently never match rather than fail.

The bridge did not dump items at all before this. `revealed_item` and `PokemonSet.item` were bare strings with no reference data behind them.

Two format rules surfaced on the way, both real and both previously unrecorded: **Item Clause** (one of each item per team, so an opponent cannot hold two Life Orbs — a genuine constraint on opponent modelling) and the restricted list itself.

## What following the residual then found

**Knock Off.** The largest single term left after items, at a steady ×1.5 across 27 hits. It scales through `onBasePower`, *not* `basePowerCallback` — so the `dynamicPower` flag added for the eleven zero-power moves does not catch it. Seventeen moves here use that hook. Knock Off, Facade, Venoshock, Barb Barrage, the solar moves, the terrain bonuses and Expanding Force are modelled now; Fickle Beam (a 30% coin flip), Lash Out, Helping Hand, Charge and Grav Apple are named in a test as deliberate omissions.

**The damage roll is applied in the wrong place.** The engine runs `randomizer(baseDamage)` *between* the base term and the modifiers, and every modifier is `trunc((trunc(value * modifier) + 2047) / 4096)` rather than a float multiply. The type chart is applied as doublings and truncated halvings, so ×0.25 is two separate `trunc(damage / 2)` steps. We rolled last and multiplied in float, which put our predicted minimum a point above the engine's real damage — visible as a run of mismatches like `predicted 85-100, engine dealt 84`. Reproducing `modify()` gives back the engine's own constants exactly: 1.3 → 5324, 1.2 → 4915, 1.1 → 4505.

**Nine moves bypass the damage formula and all nine read as status moves.** Seismic Toss, Night Shade, Super Fang, Endeavor, Final Gambit, Counter, Mirror Coat, Metal Burst, Comeuppance. Every one carries a zero base power *and* no `basePowerCallback`, so neither flag catches them. Super Fang surfaced it: `predicted 0-0, engine dealt 76`. **This is the same silent failure as the eleven dynamic-power moves, through a third mechanism** — and it means the heuristic has been pricing Seismic Toss as a support move.

## Numbers

```
DAMAGE
  no-item control      94.8%  ->  94.7%     (unchanged, as it should be)
  item-holding teams   87.5%  ->  94.8%
                         via items 89.1%, then rounding, then fixed damage

TURN ORDER
  random teams         85.0%  ->  91.0%  (abilities)  ->  97.7%  (Choice Scarf)
```

Item-holding teams now predict as well as the no-item control, which is exactly what modelling items was for.

## What is still open

- **Speed Boost** and the weather Speed abilities (Chlorophyll, Swift Swim, Sand Rush, Slush Rush) remain in the turn-order residual.
- **Focus Sash** does not change damage — it changes *survival*, leaving the holder on 1 HP. That is a knockout-prediction mechanic, not a damage one, and it is the likeliest cause of the 17% of "guaranteed" knockouts that do not happen. Unmodelled.
- **The four reflecting moves** need the damage taken this turn, which nothing tracks.
- A mild **over-prediction lean** remains in both runs (49 over against 15 under on the control). Smaller than what preceded it, and unattributed.

## Strength

Not measured in a paired, controlled way for this batch. Against Random the agent reads 98.5% and 96.8% over two seeds of 400 with a margin of +2.16 and +2.13, consistent with the numbers before the work — but that comparison regenerates its team pool each run and so is not a controlled one, which is the mistake experiment 0007 caught and discarded. Fixed damage is the change most likely to move play, since Seismic Toss and Super Fang were being scored as support moves; a paired run is owed.
