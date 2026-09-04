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

## What the setup work found

Three things were checked rather than assumed, and two of them were wrong.

**The warm start did not work at first.** A per-slot policy with all weight on
`heuristic_score` plays the heuristic to **42.3%** over 2,100 battles across
three seeds (CI 37.9%-46.8%), which excludes parity. An earlier single-seed
reading of 48.4% over 400 battles was underpowered and had been over-read.

The cause was exact, and measured over 120 real decisions:

```
  argmax of summed slot scores       matches the heuristic    84.2%
  ...plus the combined-targets term  matches the heuristic   100.0%
```

`ml/policy.py` scores each slot and sums them, which is the right shape for
0006's imitation task where each slot carried one human label. The heuristic
*also* adds `_combined_targets` -- the focus-fire correction from 0011, which
stops both slots piling damage onto one target because a Pokemon can only faint
once. That term is joint by nature and cannot be expressed per slot. One
missing term, one decision in six, eight points of win rate.

With it as a 27th joint-level feature the warm start ties **189 of 189**
matchups against the heuristic and `changed_nothing` is True: an exact clone.
Training now starts at the bar rather than eight points under it.

**The gradient was normalised per episode squared**, so the effective learning
rate shrank quadratically with batch size. It now divides by the number of
decisions in the batch.

**And the training reward was mostly about teams.** Episodes paired two
different teams, and 0031 measured team assignment at 93% of outcome variance.
Training is on mirror matchups now, where the same team on both sides leaves a
reward about play. Evaluation is untouched and still exchanges teams.

## Running it

```bash
python experiments/0043-policy-gradient/train.py policy.json 60 30 1.0
```

Arguments are the output file, batches, episodes per batch, and the learning
rate -- which is swept rather than sampled, because 0032 is what happens when
three experiments each try one setting and call the result a null.

## What would count as a result

Pre-registered before the full run: **the trained policy beats the shipped
heuristic on held-out teams, paired, at the standing bar of ≥1,500 battles
across ≥2 seeds, p < 0.05.**

Anything short of that is a null, and a null is the expected outcome given that
five of the last six things measured here were. The warm start's own level
against the heuristic is measured separately and reported as the starting line,
because "did training move it" and "does it beat the heuristic" are different
questions and both are worth an answer.
