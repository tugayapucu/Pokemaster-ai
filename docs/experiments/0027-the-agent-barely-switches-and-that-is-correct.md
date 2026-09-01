# Experiment 0027 — The agent barely switches (conclusion withdrawn)

*(The original title said "and that turns out to be right". 0031 withdrew it: the result was a false positive from a harness that never exchanged teams.)*

**Date:** 2026-08-31
> **Withdrawn by 0031.** The finding below rests on `evaluate` measurements
> taken before the harness was fixed. It swapped agents *and* teams, which
> cancels, so each agent kept its team and 93% of outcome variance went
> uncontrolled — making the binomial confidence intervals too narrow. Re-run
> on the fixed harness, matchup switching is **49.9% with p = 0.92**, not
> 47.1% with p = 0.001. It is neutral, not harmful.
>
> What survives: the 0.3%-against-11.8% switch-rate gap is real and measured,
> and `_score_switch` really does give no credit for the matchup. What does
> **not** survive is the conclusion that closing that gap costs games. It is
> now simply unexplained.
>
> **Resolved by 0032.** Swept rather than sampled, the curve is monotone and
> crosses even between horizons 2 and 4. Horizon 8 -- the setting this document
> tested, chosen to reproduce the human switch rate -- really is harmful, so
> the observation here was of something real. What it missed is that a *small*
> amount of switching wins: horizon 2 at 57.8% over three seed sets, now
> shipped. The optimum rate is 4.4%, between this agent's 0.27% and the human
> 11.8%.
**Result (withdrawn): the widest behavioural gap left in the agent appeared not to be a defect.** It switches on **0.3%** of free decisions where rated humans switch on **11.8%**, and the cause is visible in the code — a switch is priced at a flat −25 with no credit for the matchup it buys. Restoring the matchup-based scorer experiment 0004 reverted, and re-measuring it on harvested teams, makes the agent **worse**: 47.1% over 3,200 battles at the horizon that reproduces the human switch rate, 48.5% at half of it, monotone in how much it switches and replicated on two different pools. 0004's revert stands, now on a pool that resembles the game.

## The gap

The census on harvested teams, counting only decisions where staying in was an option:

```
free in-battle decisions   3713
  switch      10  ( 0.3%)
  move      3703  (99.7%)

humans, 32,095 free choices     switch 11.8%
```

Switches were **offered on 628 turns and taken twice**, so this is not availability. The best switch scores a median **159 points below** the best move, because `_score_switch` is a flat `SWITCH_COST = -25` plus `+55` when weakened, and gives nothing at all for the matchup a switch buys.

That is the same shape as 0023's setup finding — a flat constant standing in for a trade about what the action converts into — and on a much larger class of decision.

*(A first count put the rate at 26.7%, by lumping `PassAction` and forced post-faint replacements in with voluntary switching. Neither is a choice to give up momentum. The clean figure is 0.3%.)*

## It had already been tried, and the docstring said so

`_score_switch` carries a warning:

> *"The matchup-based version this replaced is recoverable from git history and documented in experiment 0004; it was reverted on evidence, not abandoned for lack of one."*

0004 built exactly this, and reverted it on three signals: human agreement 43.1% → 39.7% (McNemar chi2 = 172 over 11,133 labels), a head-to-head of 52.9% over 1,600 battles with one seed null, and a *loss* against Random. It is also unusually honest — it records that its own first version published a false positive from an underpowered 600-battle run.

**Every one of those measurements ran on the singles-generated pool 0024 later found unrepresentative**, where battles lasted 8.5 turns. Two things since changed that bear directly on switching: battles now run **13 turns**, and the reverted code's own comment calibrated its horizon *"in a format where battles last five or six turns"*. A constant that encodes a battle length is worth re-checking when the battle length doubles.

So the code was restored verbatim from `0692cc1` behind a `matchup_switching` flag, default off.

## The warning sign, recorded before the result

`SWITCH_HORIZON` was calibrated the way 0004 calibrated it: to the human switch *rate*, not to win rate, so the constant is not fitted to the thing being tested.

```
                          free-switch rate
  flat cost (shipped)          0.14%
  matchup, horizon 1.0         2.45%      <- 0004 reached 11.0% here
  matchup, horizon 4.0         8.02%
  matchup, horizon 6.0        10.90%
  matchup, horizon 8.0        12.21%      <- human 11.8%
```

**0004 needed horizon 1.0 to reach the human rate; this needs 8.0.** An eightfold change in the constant for a 2.2-fold change in battle length means the horizon is absorbing something other than horizon — harvested teams have smaller matchup differentials than generated ones. That is closer to curve-fitting than to recalibration, and it was written down before the A/B was run rather than after.

## The result

```
matchup switching's win rate against the shipped flat cost
two independent runs of 1,600 battles per horizon, two seeds each,
paired, teams exchanged

  horizon 8.0   run 1  742/1600 = 46.4%     run 2  765/1600 = 47.8%
                pooled 1507/3200 = 47.1%   z = -3.29, p = 0.001
  horizon 4.0   run 1  775/1600 = 48.4%     run 2  777/1600 = 48.6%
                pooled 1552/3200 = 48.5%   z = -1.70, p = 0.090

0004 on the old pool:  847/1600 = 52.9%, one seed null
```

The two runs of horizon 8.0 differ by 1.4 points on identical seeds and code,
and the reason is worth recording: `harvested_pool` rebuilt from the corpus,
which was still being collected, so the train split moved from 923 to 1,391
replays between them and each run drew a different 120 teams. Within a run both
arms share the pool and the comparison holds; across runs it does not. Pools can
now be frozen to a file, and comparisons across runs need it.

Both below even in all four measurements, and **monotone**: the more the agent switches, the worse it does. That is the useful part. A single null could be a mis-set constant; a monotone trend across the parameter that controls the behaviour, replicated on two different pools, says the behaviour itself does not pay here.

## What this settles

- ~~**The 0.3% switch rate is not a bug.**~~ **Withdrawn by 0031.** On the fixed harness switching is neutral (49.9%, p = 0.92), so nothing here shows that closing the gap costs games. Left visible rather than deleted, because the claim was published.
- **Human agreement is not a target, again.** This is the third time following the corpus would have been wrong (0010's Trick Room, 0013's targets, now switching), and the first time it has been checked directly against win rate on a representative pool.
- **0004's conclusion survives its own evidence being invalidated.** Its measurements were taken on a pool now known to be wrong, and the verdict held anyway — worth holding alongside 0025, where the same thing happened to 0023. Finding that an instrument was broken does not mean the answer it gave was.

## Found on the way

`legal_switch_actions`. Replacing a fainted Pokemon crashed with

```
KeyError: no MoveData for move 'dazzlinggleam' on 'Hatterene'
```

because `_forced_switch_actions` asked `legal_slot_actions` for every action and kept only the switches — building every move action, discarding them, and raising on data it never needed. Move target types are learned from requests carrying an `active` block, and a forced-switch request carries none. Matchup switching reaches replacement turns far more often, which is why it surfaced here.

## The rejection that turned out not to be a legality bug

`Can't move: <X>'s Protect is disabled` had been refused three times across
three different scripted agents and survived two fixes aimed at legality. It
was diagnosed after this experiment, and it was never a legality bug at all.

An invariant check over **425,008 joint actions** across four agent types found
`legal_actions` had never once offered a disabled move, which ruled out
enumeration. What was left was the wording, ignored six times:

```
[Unavailable choice]  ... Protect is disabled          x3
[Invalid choice]      ... needs a target / bad target  x3
```

Showdown separates them in `Side.emitChoiceError`: **Invalid** means the choice
was never legal, **Unavailable** means it was legal for the request we held and
the engine has since corrected and re-emitted that request. Showdown's own
reference agent ignores Unavailable errors. `updateDisabledRequest` is one of
the two things that triggers the correction, which is exactly why every
instance mentioned a disabled move and why it read as a legality problem.

`_absorb` raised on any error at all; it now tolerates Unavailable, counts it,
and still fails loudly on Invalid.

## Not established

- Whether the pool drift between the two runs changed anything beyond the 1.4 points seen. Both runs agree in direction and the pooled figure is significant, but neither was measured on a frozen pool.
- Whether a *better* switch model would pay. This tests one particular matchup formulation at two horizons; it does not show that no switching policy could help.
- Whether the same holds against an opponent that switches well. Both sides here share a policy, and 0026 is a standing reminder that self-play cannot price behaviour the agent does not exhibit.
