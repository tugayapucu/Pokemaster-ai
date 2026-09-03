# Experiment 0038 — Ranking is an easier task, and it is worth about a point

**Date:** 2026-09-03
**Result: the first positive search result in this project, and it is small.** 0035 and 0037 measured the evaluator on *prediction* — name the eventual winner — and found it saturates near 63%. A search does not need that. It needs a local ordering, and that turns out to be a different and easier task: applied to the successor position, `evaluate_position` orders candidate actions at **67.2%** against the shipped action score's **63.4%**. Converted into wins on held-out rollouts, a one-ply search is worth **+1.4 points**, pre-registered and confirmed at p = 0.020. The first, biased run said +2.9; **half of it was selection bias.**

## What was built to ask this

Forking the engine, which had been a spike in the plan since 2026-08-15 and was never built. It needed no serialisation: `BattleEnv.replay(..., stop_after=k)` reproduces a position by resubmitting a recording under the same seed, and `reseed` replaces the generator so what follows is a sample rather than the same replay again. Exactness is pinned by a test that forks a battle at turn 5, finishes it with the same deterministic agents and requires all 213 protocol lines back.

Ground truth then comes from the engine rather than from a corpus. At a decision point the battle is forked once per candidate action, the action is applied, and the rest is rolled out 24 times with the heuristic on both sides. The win rate over those rollouts is what the action was worth.

## Question one: how much does a decision matter?

This had to come first. If choosing the worst available action costs three points, no ranker is worth building however well it ranks — the same order 0018 imposed on opponent knowledge and 0035 on the value model.

A win rate over 24 rollouts carries real noise, so the statistic needs a control or it measures the sample size. Every candidate was therefore also measured on two disjoint halves of its own rollouts: the same action, differing by luck alone.

```
  median difference between two different actions    8.3%
  median difference, the same action twice           0.0%

  observed sd of a pair difference                  37.3%
  noise sd                                          12.2%
  real sd, after subtracting noise                  35.3%
```

**Decisions matter enormously**, and the noise is small against the signal. Both runs agree (36.6% and 35.3%).

Two things temper it. **16% of decision points are already settled** — every rollout of every action ends the same way, usually because the matchup itself is lost. And the agent **already picks the best of its four candidates 57% of the time**, against 25% for picking at random. It is not choosing badly; the question is only whether the remaining 43% is reachable.

## Question two: does evaluating the successor rank better?

Two rankers, judged against the same rollouts. The successor evaluator is what a one-ply search would use; the action score is what ships.

```
  ranker                     all pairs        pairs differing by >= 15pp
  successor eval             67.2%  n=2337    68.8%  n=1813
  shipped action score       63.4%  n=2499    64.9%  n=1933
```

About four points better, and it replicated across two independent runs (67.4% / 61.8% in the first). **This is the finding 0035 and 0037 left open**: those two measured 63% on prediction, and ranking one-ply-apart positions comes in above it. Different data and different task, so this is suggestive rather than a like-for-like comparison — but it points the way the hypothesis predicted, which prediction-based measurement had no way to show.

## What it is worth, and the bias that had to be removed first

The first run selected the action with the highest mean successor evaluation, and that evaluation was computed from **the same rollouts** that then graded it. A candidate that got lucky was both more likely to be picked and more likely to look good. That is the shape that produced 0029, published and retracted.

So the confirmation run saved rollouts individually and split them: odd-numbered ones choose the action, even-numbered ones say what it was worth, and then the other way round. One claim, fixed before it ran — *on held-out rollouts, the action chosen by successor evaluation beats the action the agent picked, paired sign test, p < 0.05*:

```
  successor eval (one-ply search)     57.5%     +1.4pp
  the agent's own pick (shipped)      56.1%
  best on the selection half          67.4%    +11.3pp
  worst on the selection half         28.8%    -27.3pp

  ahead 81   behind 54   tied 517     p = 0.0201     CONFIRMED
```

**+1.4 points, not +2.9.** The bias was worth as much as the effect.

The +11.3pp line is the honest headroom: a ranker that gets twelve rollouts to choose with still only reaches 67.4%, and search captures about an eighth of that. **The limit is the evaluator, not the search** — which is exactly what 0035 and 0037 would predict.

## When is a decision worth thinking about?

Stakes vary hugely, so a search could run only where they are high. Of the cheap signals available at decision time, one works:

```
  gate: skip a quarter of decisions      headroom skipped   kept    value lost
  the most lopsided boards                     8.6%        17.3%      14%
  the highest turns                           12.8%        15.9%      21%
  the lowest action-score spread              14.4%        15.4%      24%
```

Skipping the most one-sided quarter of positions costs 14% of the value. Two negatives are worth as much:

- **Turn does not predict stakes** (43.9%, 47.9%, 38.3%, 47.3% across quartiles). "Search early only" would be wrong.
- **The agent's own score spread does not predict stakes.** The obvious cheap gate — think harder when the top actions score close together — does not work. The agent cannot tell when its own decision matters.

## What this does and does not license

**Does:** Milestone 11 is no longer ruled out. 0022 built a lookahead, found it inert, woke it and lost nine points; 0035 explained why a better evaluator would not rescue it. This is the first evidence pointing the other way, and it is pre-registered and confirmed.

**Does not:** justify building it yet, at +1.4 points against Mega's +10.1 and switching's +7.8.

## Not established

- **Whether a real search can find the opponent's move.** Here it is handed the move the opponent actually played. In self-play that is not quite an oracle — the opponent is our own deterministic heuristic — but reproducing its choice requires the hidden information our agent does not have. This is the single largest uncontrolled factor and it inflates the result.
- **What happens with every candidate rather than four.** A median decision offers 106 legal joint actions and four were sampled. A real search would rank all of them: more options raise the ceiling, and more chances to be fooled lower what a noisy ranker captures. This cuts the opposite way to the point above, and neither is measured.
- **Whether +1.4 at one decision compounds across a battle.** Each figure is the win rate of the whole battle after changing one choice. Applying it at every decision is not the same experiment.
- Whether any of this survives an opponent that is not our own heuristic — 0026's blind spot, still open.
