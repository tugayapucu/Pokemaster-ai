# Experiment 0043 — Policy gradient moves the policy and gains nothing

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

## What it does and does not settle

**Does not settle that RL cannot work here.** 1,800 episodes is a small amount of REINFORCE, the weights moved by at most 0.4 against a warm start of 10, and every decision in a battle received the same advantage — a constant baseline is the highest-variance credit assignment available.

**Does settle that the obvious cheap version does not pay.** A linear model over these 26 features, warm-started perfectly and given a winning signal, is level with the hand-written rule after an afternoon. Anything further is a real project rather than an afternoon, and now has to be justified against that.

## Not established

- **Whether more training moves it.** The consistent gradient direction is evidence that the signal is real and the step count is the limit, but that is an argument, not a measurement.
- **Whether the features span what matters.** They are 0006's imitation features, and `heuristic_score` already summarises most of them — a linear model over a feature that is itself the answer has little room to disagree usefully.
- **Whether a state-dependent baseline changes it.** Every step in an episode currently shares one advantage. `evaluate_position` predicts the winner at about 63% (0035) and is free, so an actor-critic using it as a critic is the cheapest available variance reduction and is untried.
- Whether any of this holds against an opponent other than the frozen heuristic. Training against one fixed opponent can learn to exploit it rather than to play well; 0026's caution applies and nothing here tests it.
