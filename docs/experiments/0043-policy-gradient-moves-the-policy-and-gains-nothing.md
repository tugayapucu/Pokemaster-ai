# Experiment 0043 — Policy gradient moves the policy and gains nothing, twice

**Date:** 2026-09-05
**Result: a linear policy warm-started as an exact clone of the heuristic, trained by REINFORCE on a winning signal, plays it to 52.6% over 2,400 battles across three seeds (CI 45.6%–59.4%, p = 0.475).** Not worse, not better. It is not a no-op either: the trained policy differs from the heuristic on **18% of matchups**, so training changed real decisions and those changes came out roughly neutral. **Most of the value in this experiment came from the setup, which found three defects that would each have produced a confident wrong answer.**

## Why Milestone 8 was worth opening at all

0006 built a policy on these same features and trained it to imitate rated humans: +4.2 points of agreement, 520–1080 in battles, because it learned to decline a guaranteed knockout one time in four. Its closing line was that a learned policy needs a signal tied to winning. This is that signal.

The prize is measured rather than hoped for. 0038 found the agent picks the best of four candidates 57% of the time, with **11.3 points** between it and a ranker allowed twelve rollouts per candidate — the largest headroom anything in this project has measured, and a policy is exactly a better action-ranker.

And Milestone 8's own precondition list ends with "runtime is acceptable", which had never been checked. Measured: 21.4 battles/sec random, 12.4 heuristic self-play, ~25 agent decisions per battle, 16 cores. Not the blocker the plan feared.

## The setup, which is where the findings are

**The warm start did not work, and that was the whole premise.** A per-slot policy with all weight on `heuristic_score` plays the heuristic to **42.3%** over 2,100 battles across three seeds (CI 37.9%–46.8%) — parity excluded. An earlier single-seed reading of 48.4% over 400 battles had a CI of 38.6%–58.3%, and had been over-read.

The cause was exact, measured over 120 real decisions:

```
  argmax of summed slot scores       matches the heuristic    84.2%
  ...plus the combined-targets term  matches the heuristic   100.0%
```

`ml/policy.py` scores each slot and sums, which is right for 0006's imitation task where every slot carried one human label. The heuristic *also* adds `_combined_targets` — 0011's focus-fire correction, which stops both slots piling damage onto one target because a Pokemon can only faint once. **That term is joint by nature and cannot be expressed per slot.** One missing term, one decision in six, eight points of win rate.

Added as a 27th joint-level feature, the warm start ties **189 of 189** matchups and `changed_nothing` is True. Training then starts at the bar instead of eight points under it.

**Two more, found the same way.** The gradient was normalised per episode *squared*, so the effective learning rate shrank quadratically with batch size. And episodes paired two different teams, where 0031 puts team assignment at 93% of outcome variance — so most of the reward was a report on which team was luckier. Training moved to mirror matchups, which removes that term entirely.

## The run

Three learning rates rather than one, because 0032 is what happens when three experiments each sample a single setting and call the result a null. 60 batches of 30 episodes each, mirror matchups, 50 of the 200 pool teams never trained on.

```
  feature            lr 0.2    lr 1.0    lr 4.0
  is_status_move     -0.062    -0.193    -0.408
  damage_fraction    +0.035    +0.118    +0.383
  super_effective    +0.052    +0.221    +0.156
  is_protect         -0.024    -0.098    -0.143
```

**The direction is consistent and scales cleanly with the learning rate**, which is what a real gradient looks like rather than noise. It says: attack more, use status less, prefer spread and super-effective, protect less.

That is worth noting on its own. It is the opposite of what human agreement suggested — `review --all` found eleven non-damaging moves at 3–8% agreement — and it agrees with 0040, which swept the price of the whole status category and found that raising it costs games. **Three instruments now point the same way: a winning signal, a category sweep, and a rollout ceiling.**

## And it gains nothing

```
    seed 11   36/66 = 54.5%      seed 29   35/68 = 51.5%      seed 53   32/62 = 51.6%

  pooled  103/196 = 52.6%   95% CI 45.6%-59.4%   p = 0.4751
  raw win rate 50.2% over 2,400 battles, 904 matchups tied
  differed from the heuristic on 18% of matchups
```

The 18% matters. A trained policy that had learned nothing would tie everything and report 50% by construction; this one changed a fifth of its games and came out level.

## A second attempt, with the highest-variance part fixed

Every decision in a battle received the same advantage above -- the outcome
minus a running mean. A turn played while comfortably ahead and one played
while nearly dead got identical credit for the same eventual win, so most of
the gradient was reporting the outcome rather than the choice.

`evaluate_position` is a baseline this project already owns, costs nothing, and
is not learned, so it cannot co-adapt with the policy. `critic.py` fits it into
reward units on self-play mirror battles -- the distribution training actually
samples -- and checks it before it is used, because a flat baseline subtracts a
constant and changes nothing:

```
  4,129 positions, 1,376 held out
    accuracy            67.7%      (0035 measured ~63% on human games)
    Brier, fitted      0.1919
    Brier, flat        0.2489      <- what the first run used
    variance explained  22.9%
```

Well calibrated across the range, not merely accurate on average: predicted
against actual, held out, 9.0%/5.2%, 48.9%/45.0%, 84.4%/86.0%.

The rerun changed the baseline and nothing else -- same three learning rates,
same sixty batches -- so the comparison isolates the critic. It did what it was
supposed to mechanically, moving the weights about 15% further at the same
learning rate, and it did not convert:

```
  constant baseline,  lr 4.0, seeds 11/29/53      103/196 = 52.6%   p = 0.4751
  state-dependent,    lr 4.0, seeds 11/29/53      125/226 = 55.3%   p = 0.1104
  state-dependent,    lr 4.0, seeds 101/211/307   109/208 = 52.4%   p = 0.4881
```

**The middle line is the one worth dwelling on.** 55.3% with all three seeds
leaning the same way is exactly the shape that produced 0029, and the response
this project settled on after 0036 is a pre-registered confirmation on fresh
seeds with a stopping rule fixed in advance. The confirmation came back 52.4%.
Regression to the mean, caught by the procedure rather than published.

Pooling both seed sets of the same policy gives **234/434 = 53.9%, p = 0.103,
over 4,800 battles.** Persistently a shade above even, never significant, and
the pre-registered test failed. The stopping rule fires: no third attempt.

## Two diagnostics that said more than the win rates

**Training does not improve the thing it optimises.** Sampled win rate over
sixty batches went 52.0% to 51.7%, 55.0% to 52.3%, and 57.3% to 55.0% --
flat to declining in all three runs.

**The runs disagree on direction.** Between the constant-baseline and
state-dependent runs at the same learning rate, `self_stat_drop` went +0.090
against -0.604, `has_priority` -0.114 against +0.244, `guaranteed_ko` +0.009
against -0.129. Sign flips mean noise. Only `is_status_move` (down) and
`damage_fraction` (up) survive both, which were the consistent pair from the
start.

Two things were checked rather than assumed. Player 0 has no structural edge in
a mirror -- an identical heuristic on both sides wins 51.3% of 300 battles,
0.45 standard deviations from even. And the three runs all opening above 50%
was one correlated sample rather than three: they share an RNG seed, so their
early batches are near-identical games.

## What it does and does not settle

**Does not settle that RL cannot work here.** 1,800 episodes is a small amount of REINFORCE and the weights moved by at most 0.6 against a warm start of 10. What it does settle is narrower than "RL fails" and wider than the first run alone: the two most likely cheap fixes — a real baseline, and a learning-rate sweep rather than a single setting — were both tried, and neither converted.

**Does settle that the obvious cheap version does not pay.** A linear model over these 26 features, warm-started perfectly and given a winning signal, is level with the hand-written rule after an afternoon. Anything further is a real project rather than an afternoon, and now has to be justified against that.

## Not established

- **Whether more training moves it.** The consistent gradient direction is evidence that the signal is real and the step count is the limit, but that is an argument, not a measurement.
- **Whether the features span what matters.** They are 0006's imitation features, and `heuristic_score` already summarises most of them — a linear model over a feature that is itself the answer has little room to disagree usefully.
- **Whether the linear model can express a better ranker at all.** `heuristic_score` already summarises the other twenty-six features, so a linear policy over it can only re-weight inputs the heuristic already considers. 0038 located the headroom in *ranking*, and re-weighting may simply not reach it. This is the best available explanation for the null and it is an argument rather than a measurement.
- Whether any of this holds against an opponent other than the frozen heuristic. Training against one fixed opponent can learn to exploit it rather than to play well; 0026's caution applies and nothing here tests it.
