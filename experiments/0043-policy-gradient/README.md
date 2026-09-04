# 0043 — Milestone 8, at the smallest size that answers the question

Can a policy trained on *winning* beat the hand-written heuristic?

## Why this shape

0006 built a policy on these same 26 features and trained it to imitate rated
humans. It gained 4.2 points of agreement and lost 520-1080, because it learned
to decline a guaranteed knockout one time in four. Its closing line was that any
future learned policy needs a signal tied to winning. This is that signal.

**Linear, and no new dependency.** If a policy warm-started at the heuristic and
handed a winning signal cannot improve on it, a deeper one probably cannot
either — and this costs an afternoon rather than a month. The project's rule is
baselines before deep learning, so torch is a decision to take on evidence.

## The three things that make it worth running

**The warm start.** `heuristic_score` is one of the features, so a weight vector
concentrated on it reproduces the heuristic's ranking. Training therefore starts
at the bar rather than at 0006's 32.5%, and any gain is a gain over an agent
that took forty experiments to tune.

**The headroom is measured.** 0038 found the agent picks the best of four
candidates 57% of the time, with 11.3 points between it and a ranker given
twelve rollouts to choose with. That is the largest headroom anything in this
project has measured, and a better action-ranker is exactly what a policy is.

**Runtime is not the blocker the plan feared.** Measured: 21.4 battles/sec
random, 12.4 heuristic self-play, ~25 agent decisions per battle, 16 cores
available.

## Design decisions, and the lesson behind each

| Decision | Why |
|---|---|
| Mirror matchups for training | 0031 put team assignment at 93% of outcome variance. Two different teams give a reward about which team was luckier. |
| Held out by team | 50 of the 200 pool teams are never trained on. Overfitting a fixed pool is the obvious way to produce a meaningless number. |
| Opponent is the frozen heuristic | The question is "does this beat the heuristic". 0026 also warns that self-play cannot surface what an agent under-uses. |
| Greedy at evaluation, sampling in training | Argmax is scale-invariant, so the warm start is the same policy however the exploration weight is set. |
| Normalise the gradient per decision | Not per episode, and not per episode squared, which the first draft did. |

## Running it

```bash
python experiments/0043-policy-gradient/train.py policy.json 200 40
```

Arguments are the output file, the number of batches, and episodes per batch.

## What would count as a result

Pre-registered before the full run: **the trained policy beats the shipped
heuristic on held-out teams, paired, at the standing bar of ≥1,500 battles
across ≥2 seeds, p < 0.05.**

Anything short of that is a null, and a null is the expected outcome given that
five of the last six things measured here were. The warm start's own level
against the heuristic is measured separately and reported as the starting line,
because "did training move it" and "does it beat the heuristic" are different
questions and both are worth an answer.
