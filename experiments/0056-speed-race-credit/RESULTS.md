# 0056 — No speed credit helps; the smallest is merely harmless

Run 2026-09-13 against the pre-registration in this directory, which was
committed and pushed (`3c755e9`) while all four arms were still running.

## What was built

| commit | what |
| --- | --- |
| `6ca7eb0` | `race_credit` in `order_edge` and `speed_race_credit` in `matchup()`: 0 is the one-hit rule, 1 is 0055's; out-of-range refused |
| `5aa9aba` | the agent passes `speed_race_credit` from Team Preview and switch scoring; shipped agent unchanged |

## The sweep

Every arm is `speed_beyond_knockouts` on at one credit against the shipped agent,
800 battles on seed 1 — fresh against 0055's seed 0.

| arm | credit | median edge | above a neutral hit | above the damage trade | verdicts flipped | picks differ | decisions differ | record | 95% Wilson | 98.75% Wilson | decided |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 0.25 | 0.040 | 6% | 18% | 8% | 42% | 2.1% | **403 / 397 — 50.4%** | [46.9%, 53.8%] | [46.0%, 54.8%] | 89 |
| B | 0.50 | 0.080 | 18% | 27% | 10% | 61% | 2.4% | 388 / 412 — 48.5% | [45.1%, 52.0%] | [44.1%, 52.9%] | 122 |
| C | 0.75 | 0.117 | 37% | 32% | 10% | 72% | 4.2% | 385 / 415 — 48.1% | [44.7%, 51.6%] | [43.7%, 52.5%] | 145 |
| D | 1.00 | 0.152 | 43% | 35% | 10% | 81% | 6.8% | 389 / 411 — 48.6% | [45.2%, 52.1%] | [44.2%, 53.0%] | 143 |

## The decision

**No arm clears the Bonferroni-adjusted 98.75% bar, and none clears even 95%.**
By the rule written before the runs, `speed_beyond_knockouts` stays off, every
number is recorded, and **speed pricing is not revisited before Frankfurt**.

## Against the predictions

| prediction | result |
| --- | --- |
| D replicates 0055's negative, within ±3 points of 48.1% | ✓ 48.6% |
| picks differ rise with the credit, all above 40% | ✓ 42 → 61 → 72 → 81% |
| A, B, C neutral; none clears | ✓ |
| magnitude shrinks in proportion: above the damage trade near 10 / 20 / 28% | ✗ 18 / 27 / 32% |

The last miss is informative. Scaling the credit shrinks the typical edge in
proportion (median 0.040, 0.080, 0.117, 0.152), but the share of pairings where
speed outweighs the damage trade shrinks far more slowly — because in many
pairings the damage trade itself is small, so even a quarter of a denied hit
outweighs it. Speed dominance is a property of close matchups, not only of the
size of the credit.

## Reading the pattern

The smallest credit is the only arm near even; every credit from 0.5 up leans
negative, much like the full rule. That is consistent with the magnitude table:
any credit large enough to change most picks makes the agent slightly worse.

**These arms are not independent.** All four were measured against the same
baseline on the same seed, so the battles are shared. Pooling them into one
larger sample would overstate the evidence, and it was not done.

## What this closes

Across 0055 and 0056, valuing speed beyond a one-hit knockout has now been
measured at five settings on two seeds, and no setting has helped. The one-hit
rule stays. What remains open under bug 5 is different in kind — support effects
and status moves at Team Preview — and is not a speed question.

## Hygiene

Pool teams and synthetic fixtures only.
