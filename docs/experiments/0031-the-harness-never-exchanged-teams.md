# Experiment 0031 — The harness never exchanged teams, and one published result was a false positive

**Date:** 2026-09-01
**Result: `evaluate` controlled the seat but never the team, leaving 93% of outcome variance uncontrolled.** Re-run on the fixed harness, the two large results replicate — Mega **57.6%** and search **42.4%**, both p < 0.0001 — the nulls stay null, and experiment 0027's *significant* −2.9 becomes **49.9%, p = 0.92**. So the confound was not hiding wins. It was inflating confidence, and it cost one published conclusion.

## The bug

`evaluate` plays every matchup twice, and its docstring claimed the passes exchange the teams "so neither the seat nor the team a given agent happened to receive can be credited to it". The code swapped the agents *and* the teams, which cancels:

```
swapped=False:  player0 = A holding T0   ->  A holds T0
swapped=True:   player0 = B holding T1   ->  A holds T0
```

Agent A kept the team it started with. Only the seat was ever controlled.

Unbiased — over many matchups the draw evens out — but the noise is the point. Measured on the frozen pool with the *same* agent on both sides:

```
85% of matchups are one-sided (one team wins 17 or more of 20)
93% of the variance in outcomes is the matchup, not play
```

All of that went into the error bars, and the binomial confidence intervals — which assume independent battles — were therefore too **narrow**, not too wide. That makes a false positive the expected failure, which is exactly what turned up.

**The invariant that proves it:** identical agents must tie every matchup. Before the fix, 240 of 299 did not.

## The fix, in two parts

Teams now stay in place and only the agents swap, so across a pair each agent has played both teams and sat in both seats. That took mirror ties from 20% to 79%.

The residual was the two passes still drawing different luck. Since the pair is now identical but for the policies, sharing one battle seed is plain common random numbers:

```
common_seed=False   win rate 48.0%   tied  78/100
common_seed=True    win rate 50.0%   tied 100/100
```

Identical agents now tie **every** matchup at exactly 50.0%. All remaining variance in an A/B is the policy difference.

## Re-run

800 battles x 2 seeds per arm, frozen pool, pairing fixed. (This run predates the common-seed change, so it isolates the pairing fix alone.)

```
                                win rate      p        was
  mirror control                  49.1%    0.45        -       unbiased
  heuristic vs no-Mega            57.6%   <0.0001    +10.1     survives
  search vs heuristic             42.4%   <0.0001     41.0%    survives
  matchup switching               49.9%    0.92       47.1%    DOES NOT survive
  tenure-priced setup             49.8%    0.84       ~50%     still null
```

## What this says, and what it does not

**The large effects were real.** Mega and search both replicate with the same sign and nearly the same size. A confound that swamps small effects does not manufacture large ones.

**The one marginal result was a false positive.** 0027 reported matchup switching at 47.1% with p = 0.001 and concluded the agent's 0.3% switch rate is *correct* — that closing the gap to the human 11.8% costs games. On the fixed harness it is 49.9% with p = 0.92. That conclusion is withdrawn: matchup switching is neutral, not harmful, and the switch-rate gap is now simply **unexplained** rather than settled.

**The nulls are genuinely null.** This is the part worth sitting with. The obvious hope was that a 93%-variance confound had been burying real improvements. It had not: tenure-priced setup comes back 49.8% with the noise controlled, the same answer it gave before. Better instruments did not resurrect the ideas.

So "why is nothing working" has two separate answers, and only one of them was a bug:

- the harness was too noisy to trust marginal results, which is fixed;
- the ideas tested really did not work, which is not a measurement problem.

## Why the tests could not catch it

The integration tests use a fixture whose own docstring reads *"two copies of one team: isolates the harness from team-strength effects"*. Every test ran on identical teams, so team assignment could not matter and the bug was invisible.

That is the fourth instance in this project of an instrument blind to the effect it was measuring, and the first inside the test suite itself. The new tests use two different teams and stub `play_battle`, since the question is only who was handed what.

## Not established

- Whether 0026 (redirection) and 0030 (the richer evaluator) change on the fixed harness. Both were nulls, and tenure suggests nulls survive, but neither has actually been re-run.
- How much the common-seed change adds on top of the pairing fix in a real A/B. The mirror control is perfect; the effect on a genuine comparison is unmeasured.
- Whether any earlier experiment reported a marginal significance that would now fall. 0027 was found by re-running it; the others have not been checked one by one.
