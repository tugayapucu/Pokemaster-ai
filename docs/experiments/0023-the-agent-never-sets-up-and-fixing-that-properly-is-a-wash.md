# Experiment 0023 — The agent never sets up, and fixing that properly is a wash

**Date:** 2026-08-30
**Result: a real hole, a correct diagnosis, one genuine bug found, and no win.** The agent picked a status move on **2.5%** of the turns one was available. Pricing stat boosts by how long the Pokémon expects to live raised that to 16.2% and lost **4.6 points of win rate**. The cause was a flaw in the pricing, not in the tenure model: the agent was **declining guaranteed knockouts in order to set up**, on 14.5% of the turns one was offered. Fixing that took the change to **+0.9 points, 95% CI 48.4–53.3%, p = 0.48** — neutral. Shipped switched off.

## Why this, and not the backlog

Everything since Mega that fed the agent more *information* has failed or backfired: spread inference (null, 0019), opponent knowledge (+0.8, 0018), damage accuracy (converts at 0.23 points per point, 0020), the search threat model (−9, 0022). The one large win, +10.1, was different in kind — a whole **class of action the agent never took**, invisible until someone counted it.

So the cheap question first: are there other Mega-shaped holes? A census of every action class the agent chooses, against the corpus.

```
the agent, 120 battles, 1244 slot choices
  move            1047 (84.2%)      switch     82 (6.6%)
  move + mega       48 ( 3.9%)      pass       67 (5.4%)

  of its move choices:  damaging 1071    status 24    (2.2%)
```

Status moves were **23.8% of what was on its sheet**, available on 970 turns, and picked on 2.5% of them. Humans make **34.0%** of their move choices status moves; Protect alone is 14.5% of *all* human move choices, and the agent picked Protect twice in 120 battles.

Both controls matter. Human usage is not proof — the corpus is 1500–1850 Elo, and this project has twice been misled by agreement (0010, 0013). But a class of action sitting at 2.5% when it is available on a quarter of slots is the Mega question again, and it deserves the same answer: correctly worthless, or unpriced?

## The rule was asking the wrong question

With `STAT_STAGE_VALUE = 0.12`, Swords Dance scores `2 × 0.12 × 100 = 24`, so it is taken only when the best attack available does under 24% of a health bar. But the trade is

```
attack every turn ->  f * T          set up first ->  m * f * (T - 1)
```

and setting up wins when `T > m / (m - 1)`. **The `f` cancels.** The agent asks *"is my attack weak?"*; the game asks *"will I still be here in three turns?"* Those are unrelated quantities.

And the flat price is not simply too small. At the measured mean tenure of 2.81 and a typical `f ≈ 0.35`, the true value is ≈28 against a priced 24 — **about right on average and wrong nearly every individual time.** That is why a larger constant would have set up more often and still at the wrong moments.

Measured over 200 self-play battles: median tenure 2.0, mean 2.81, and `T > 2` on **44.6%** of turns. A live fraction of the game, not an edge case.

## Tenure is predictable, once the instrument is not broken

`hp_fraction / _incoming_threat` needs no new machinery. The first measurement said it does not work:

```
                        broken instrument     fixed
Pearson r                    -0.151          +0.570
predicts <1.5  -> actual      2.29             2.38
predicts 1.5-2.5              3.87             4.60
predicts 2.5-4                3.88             4.66
predicts 4+                   2.49             4.95
```

Both flaws were in the instrument, not the predictor. It recorded "nothing can threaten me" as a tenure of 99, conflating *no threat* with *no information* and packing the safest-looking bucket with cases carrying none; and it ended a tenure on a **switch** as well as a faint, when being withdrawn is a different event, and one the agent chooses itself. That is the third and fourth instance in this project of an instrument blind to the effect it was measuring.

A least-squares fit gave `T = 1.96 + 1.05 × raw`, residual sd 1.48 turns. **That fit is not used.** Its intercept hands 1.96 turns to a Pokémon with none — something at 10% health facing a hit that takes 60% reads as a fine Swords Dance candidate — and that is the largest bucket in the data (n = 1,051, actual 1.61) and the one place the error cannot be recovered from: the boost is bought and the Pokémon faints holding it. `T = 1 + raw/0.5` is pinned at the bottom instead, trading accuracy in the middle for safety at the end. A unit test holds that line.

## First attempt: −4.6 points

```
seed 1   357/800  = 44.6%
seed 7   370/800  = 46.2%
pooled   727/1600 = 45.4%   (95% CI 43.0%-47.9%)   z = -3.65, p = 0.00026
```

Both seeds agree. Status picks had gone 2.5% → 16.2%, concentrated exactly where intended — Swords Dance 48, Nasty Plot 45, Shell Smash 23, Calm Mind 15 — and the agent was worse.

**The obvious explanation was wrong, and checking it saved the diagnosis.** The calibration was fitted on self-play by an agent that almost never set up, then used to justify setting up: textbook distribution shift. Measured on the new agent's own trajectories:

```
arm                          predicted T   actual T
flat price (calibrated on)      2.69         2.92
tenure price (in use)           2.78         3.13
```

The calibration held, and Pokémon that set up lasted *longer*, not shorter. Distribution shift was not it.

## The real bug: damage does not pay past a knockout

`f * T` prices damage linearly. A hit stops paying at the target's remaining HP, and a boost's entire product is **a bigger number per hit** — so the waste lands precisely where the value was supposed to be. With a healthy Pokémon at T = 6 and f = 0.5, setup scored `1 × 0.5 × 5 × 100 = 250` against a guaranteed knockout's ~220.

```
arm            KO on sheet    took it    set up instead
flat price          631          631       0  ( 0.0%)
tenure price        724          619     105  (14.5%)
```

It had been offered a kill and preferred to make its next kill larger. The gain per turn is now

```
min(m*f, hp) - min(f, hp)
```

— the full `(m-1)*f` while the target survives the hit, and nothing once it does not. Declined knockouts fall to 3.1%, and those remaining are probabilistic rather than guaranteed.

This also killed a claim made earlier in this same experiment. *"The decision does not depend on how hard we hit"* is true only while the boosted hit leaves the target standing; a test asserting it at every `f` was wrong, and has been corrected rather than deleted.

## Second attempt: a wash

```
seed 1   396/800  = 49.5%
seed 7   418/800  = 52.2%
pooled   814/1600 = 50.9%   (95% CI 48.4%-53.3%)   z = +0.70, p = 0.48
```

Neutral. Not harmful, not proven helpful.

## What ships, and what stands

`tenure_boosts` defaults to **False**. The shipped agent does not change on a null result. The module, the flag and the tests stay, because what was learned is solid and worth being able to re-measure.

- **The hole is real and it is not a bug.** Status moves sit at 2.5% because the price is flat, and the flat price is roughly right *on average*. Pricing setup correctly moves it to 7.2% and wins nothing — which is evidence that **setup is close to break-even in this format**, not that the agent was leaving points on the table.
- **The largest errors were mine, twice.** The instrument that said the predictor did not work, and the derivation that had the agent declining knockouts. Both were caught by measuring rather than by reasoning, and the second only because the first attempt was measured instead of assumed.
- **A plausible cause is not a cause.** Distribution shift was the natural explanation for −4.6 and it was wrong. Two experiments running (0022, 0023) have now had their obvious diagnosis refuted by a five-minute measurement.
- **Pricing a stat stage in damage terms now exists**, which is machinery the position evaluator needs next.

## Not established

- Whether the *other* status classes are underpriced. This priced offensive rises on the user only; Protect, Tailwind, screens, redirection and speed control all kept the flat rate — and Protect is by far the largest gap against human play (14.5% of their move choices against roughly 0.2% of the agent's).
- Whether ±1 point is really zero. 1,600 battles resolves about ±2.5 points, so a genuine +1 would not have been detected here.
