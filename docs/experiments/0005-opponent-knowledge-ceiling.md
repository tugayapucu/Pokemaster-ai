# Experiment 0005 — How much headroom does opponent knowledge actually have?

**Date:** 2026-08-20
**Result: almost none.** Perfect knowledge of the opponent's moveset buys **+0.09 points** of agreement. Perfect knowledge of the move they use *this turn* makes the agent **worse**. This refutes the direction the project was about to commit several sessions to.

## Why this was run before the work, not after

Three failures had been attributed to missing opponent knowledge:

| Failure | Stated cause | Actually measured? |
|---|---|---|
| One-turn search inert (0001) | Unrevealed opponents read as harmless | **Yes** — mean ~3.0 revealed moves, 10% of decisions with none |
| Matchup switching reverted (0004) | Agent cannot see why humans switch | **No.** Asserted. |
| Team Preview leads null | Depends on predicting the opposing lead | **No.** Asserted. |

One data point and two stories told around it — the same shape of reasoning that
produced the mistake in 0004. Opponent modelling is a large piece of work
(corpus split, usage priors, integration into three scoring paths), so the
hypothesis was worth testing before paying for it.

## Method

The reconstruction machinery already limits the opponent's side to what was
revealed by that turn. Lifting that restriction gives an **oracle** — an agent
handed information the masking rules exist to withhold. It is a ceiling
measurement, never a proposed agent, and it lives in the scratchpad rather than
`src/` precisely so it cannot be used by accident.

- **Oracle A — moveset.** The opponent's full moveset, recovered from the whole
  replay. Roughly the best a usage-based prior could ever achieve.
- **Oracle B — action.** Only the move the opponent actually uses this turn. No
  model could reach this; it bounds the entire "predict the opponent" direction.

Both are delivered through `revealed_moves`, so they flow into the threat model
and everything downstream of it without touching the agent.

## Result

```
baseline            4792/11133 = 43.04%   (CI 42.1-44.0%)
oracle-A moveset    4802/11133 = 43.13%   (CI 42.2-44.1%)   +0.09%  chi2 = 0.4
oracle-B action     4738/11133 = 42.56%   (CI 41.6-43.5%)   -0.49%  chi2 = 8.8
```

Oracle A is indistinguishable from the baseline. **Oracle B is significantly
worse**, which is the more interesting half.

### Why perfect information makes it worse

Protect is the clearest case:

```
baseline          689/1512 agreed (45.6%)
oracle-A moveset  713/1512 agreed (47.2%)
oracle-B action   616/1512 agreed (40.7%)
```

Under Oracle B the threat model sees exactly one incoming move. When that move
is weak or not an attack at all, the estimated threat collapses to near zero,
Protect scores badly, and the agent stops protecting — while the human protected
anyway.

The assumed-STAB prior *overestimates* the threat, which accidentally makes
Protect more attractive, which happens to match humans more often. **The
heuristic has been getting the right answer for the wrong reason, and correcting
the reason makes the answer worse.**

## Conclusion

**The binding constraint is the policy, not the features.** The agent cannot
convert better information into better decisions, because its decision rule —
damage dealt now, minus damage taken now — is not the rule a human is using.
Protect still accounts for 853 misses under the strongest possible oracle.

Opponent modelling (Milestone 10) therefore drops off the critical path. It may
still be worth building eventually, but not as the next thing and not on the
evidence claimed for it.

**One limitation, stated honestly:** this measures whether *this heuristic* can
use richer opponent information. A different policy might use it well, and a
learned model could plausibly extract signal a hand-written rule cannot. What
the experiment rules out is the specific claim that was driving the roadmap —
that our agent is held back mainly by not knowing the opponent's set.

## Next actions

- **Learn the policy rather than write it.** The features are evidently
  adequate; the mapping from features to actions is what is missing, and there
  are 11,133 labelled human decisions to learn it from. That is Milestone 6, now
  indicated by evidence rather than by roadmap order.
- **Do not build usage priors yet.** Revisit only if a learned policy shows it
  can use opponent information the heuristic could not.
- Keep the oracle script. It is the cheapest available test of "would more
  information help", and it should be run before any future feature work of
  this size.
