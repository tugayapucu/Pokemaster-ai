# Experiment 0029 — Self-play cannot see the evaluator's missing features

*(The original title claimed the features "do matter". 0030 refuted that; what survives is why self-play could not have told us either way.)*

**Date:** 2026-08-31
> **Corrected by 0030.** The headline gain below (+3.0 held out, +4.4 against
> the shipped evaluator) came from a **single split** of 307 replays.
> Cross-validated over 19,035 positions it is **+0.2pp, sd 1.4, positive in
> four of eight splits** -- a null. The feature-presence finding in this
> document stands and is the reason 0030 could be run at all; the conclusion
> drawn from it does not.
**Result: self-play cannot measure whether status, screens and field terms belong in the evaluator, for the reason 0026 identified.** Those features are non-zero in 4.2%, **0.0%** and 3.8% of self-play positions, because the agent never uses them. Measured on reconstructed human positions where they actually occur, one split put them at +3.0 points — **which 0030 then showed was noise**, the cross-validated figure being +0.2 with an sd of 1.4. The lasting finding is the instrument, not the number: the tool everything else in this project is measured on is blind to this whole class of question.

## The plan, and the first answer

0028 left item 2 as: add terms for status, boosts and field effects, graded against who won. Before inventing weights — this project's record on invented constants is poor — the question was whether those features carry signal at all. A logistic regression on 5,624 self-play positions, split by battle so positions sharing an outcome cannot straddle the split:

```
                                     held out   on train
  HP only (what it scores now)          68.1%      68.6%
  HP + status                           68.1%      68.7%
  HP + boosts                           68.3%      69.1%
  HP + field (tailwind/screens/TR)      67.9%      68.5%
  everything                            69.5%      70.7%
```

Train and held-out agree throughout, so it is neither overfitting nor undertrained. It reads as a clean null: nothing beyond HP is worth adding.

## Why that answer was worthless

```
feature presence in self-play positions
  status         4.2%      tailwind     4.2%
  speed_stage    6.0%      trickroom    3.8%
  screens        0.0%      offence     46.5%
```

**Screens never occurred. Not once in 5,624 positions.** The agent does not use Reflect or Light Screen, and in self-play the opponent is the agent, so the feature is a column of zeros and the fit correctly reports that a column of zeros predicts nothing. Status, Tailwind and Trick Room are barely better.

This is exactly 0026's blind spot, reaching the evaluator work rather than a mechanic: *self-play cannot measure the value of anything the agent does not do.* The honest reading of the table above is not "these are worthless" but "this instrument cannot see them".

## Measuring where they occur

Human replays do not have the problem. `reconstruct_decisions` rebuilds what each player saw at each decision, with the opponent masked to what had been revealed — the same masking the agent plays under — and every replay carries a `|win|` line. Run on the corpus **test** split, which the harvested teams were not built from.

```
feature presence          real     self-play
  status                 14.9%        4.2%
  screens                 7.8%        0.0%
  trickroom              13.8%        3.8%
  tailwind                8.0%        4.2%
```

```
                                     held out   same subset   on train
  HP only (what it scores now)          59.6%        60.3%       59.7%
  HP + status                           59.0%        59.6%       59.9%
  HP + boosts                           60.6%        61.8%       63.3%
  HP + field (tailwind/screens/TR)      60.9%        61.8%       59.9%
  everything                            62.6%        64.1%       63.8%

  shipped evaluate_position             59.7% (n=924, where it has an opinion)
```

**+3.0 points held out on this split, +4.4 against the shipped evaluator.** This is the number 0030 refutes: it is one split of 307 replays, and eight splits of 1,610 put the gain at +0.2 ± 1.4. What does survive is the row above it — the features are present in real positions and absent in self-play.

## Two bugs in this measurement, both mine

**Every model scored a perfect 100%** on the first corpus run, with every weight at exactly zero. `Replay.winner` returns a player *name*; comparing it to `decision.player` made every label 0, so predicting one class was flawless. The accuracy did not give it away — the all-zero weights did.

**Then both winners and losers showed a negative mean HP difference**, which cannot be true by symmetry. `_recover_own_knowledge` can only recover Pokemon that were actually sent out, so `own_side.team` held two or three against the opponent's always-four in 14.6% of positions, biasing every count feature against whoever was observing. Restricting to complete rosters brings the mean to −0.037 and the label balance to 47%.

Both were caught by checking a property that had to hold, not by reading the accuracy.

## What this settles

- ~~**Item 2 is real work, not a refinement.**~~ **Withdrawn by 0030**: cross-validated, the features are worth +0.2pp and item 2 is a null. This bullet is left visible rather than deleted, because the claim was published and the correction is the point.
- **Self-play is the wrong instrument for evaluator features**, for the same reason it was the wrong instrument for redirection. Anything the agent under-uses is invisible to it. Human positions are the instrument for this class of question.
- **The evaluator is far weaker on human games than on self-play**: 59.7% against 74.6%. Some of that is that evenly-matched humans produce genuinely less predictable positions; how much is not established here.

## Not established

- Whether a 62.6% evaluator is good enough for search to pay. It is better than 59.7% and both are a long way below the 79.7% that 0021 reported, which was measured on the wrong pool.
- Whether the weights fitted on human positions transfer to self-play, which is where the agent's win rate is measured. They are fitted on positions from a policy that is not ours.
- How much of the self-play/human gap is skill variance rather than evaluator quality.
