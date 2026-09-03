"""Read the fork rollouts and answer the two questions, in order.

  1. How much does one decision actually matter?
  2. Given it matters, does evaluating the successor rank better than the
     action score we already ship?

The first has to come first, and it has to be corrected for noise. A win rate
over 24 rollouts carries about 10 points of standard error, so four identical
actions still show a spread of a few tens of points. The control -- the agent's
own chosen action, rolled out a second time against disjoint seeds -- measures
that directly, and variances subtract:

    var(observed differences) = var(real differences) + var(noise)

so the real spread is the square root of the difference. Reporting the raw
spread instead would be reporting the sample size.
"""

import json
import math
import statistics
import sys
from itertools import combinations
from pathlib import Path

DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("ranking.json")
GAP = float(sys.argv[2]) if len(sys.argv) > 2 else 0.15

rows = json.loads(DATA.read_text(encoding="utf-8"))
print(f"{len(rows)} decision points from {len({r['battle'] for r in rows})} battles")
print(f"  {sum(len(r['candidates']) for r in rows)} candidate actions rolled out")
print(f"  median legal joint actions at a decision point: "
      f"{statistics.median(r['legal'] for r in rows):.0f}\n")


# ------------------------------------------------ 1. does the decision matter?

# Every within-point pair of *different* actions, and the control pair, which
# is the same action twice and so differs by luck alone.
real = [
    abs(a["win_rate"] - b["win_rate"])
    for r in rows
    for a, b in combinations(r["candidates"], 2)
]
noise = [abs(r["control"]["win_rate"] - r["candidates"][0]["win_rate"]) for r in rows]

var_real = statistics.pvariance([
    a["win_rate"] - b["win_rate"]
    for r in rows
    for a, b in combinations(r["candidates"], 2)
])
var_noise = statistics.pvariance(
    [r["control"]["win_rate"] - r["candidates"][0]["win_rate"] for r in rows]
)
true_sd = math.sqrt(max(0.0, var_real - var_noise))

print("  1. how much does one decision matter?\n")
print(f"    {'':<34} {'mean':>8} {'median':>8} {'90th pct':>9}")
for label, values in (("two different actions", real), ("the same action twice", noise)):
    ordered = sorted(values)
    print(f"    {label:<34} {statistics.fmean(values):>7.1%} "
          f"{statistics.median(values):>8.1%} "
          f"{ordered[int(0.9 * (len(ordered) - 1))]:>9.1%}")

print(f"\n    observed sd of a pair difference   {math.sqrt(var_real):>6.1%}")
print(f"    noise sd, same action twice        {math.sqrt(var_noise):>6.1%}")
print(f"    real sd, after subtracting noise   {true_sd:>6.1%}")

# The spread over four candidates, which is what a chooser stands to win or
# lose, biased upward by the same noise -- so quote both.
spreads = [
    max(c["win_rate"] for c in r["candidates"]) - min(c["win_rate"] for c in r["candidates"])
    for r in rows
]
print(f"\n    raw best-minus-worst over 4 candidates, mean  {statistics.fmean(spreads):.1%}"
      f"   (inflated by noise)")

decided = sum(1 for r in rows if max(c["win_rate"] for c in r["candidates"]) == 0.0
              or min(c["win_rate"] for c in r["candidates"]) == 1.0)
print(f"    decision points where every action won or lost every rollout: "
      f"{decided} of {len(rows)} ({decided / len(rows):.0%})")


# --------------------------------------------------------- 2. who ranks better

RANKERS = {
    "successor eval, averaged": lambda c: c["eval_mean"],
    "successor eval, one sample": lambda c: c["eval_one"],
    "shipped action score": lambda c: c["action_score"],
}


def pairs(threshold, *, drop_picked=False):
    """Candidate pairs, optionally excluding the agent's own choice.

    Candidate 0 is the action the heuristic actually picked, so it is the
    argmax of the action score over every legal action by construction, while
    the other three are drawn uniformly. `drop_picked` removes that asymmetry
    by comparing only the uniformly drawn ones.
    """
    for r in rows:
        candidates = r["candidates"][1:] if drop_picked else r["candidates"]
        for a, b in combinations(candidates, 2):
            if abs(a["win_rate"] - b["win_rate"]) >= threshold:
                yield a, b


def correct(ranker, a, b):
    """Did this ranker order the pair the way the rollouts did?"""
    predicted = ranker(a) - ranker(b)
    actual = a["win_rate"] - b["win_rate"]
    if predicted == 0:
        return None
    return (predicted > 0) == (actual > 0)


print("\n  2. does evaluating the successor rank better than the action score?\n")
print(f"    {'ranker':<30} {'all pairs':>12} {'gap >= 15pp':>14}")
for label, ranker in RANKERS.items():
    line = f"    {label:<30}"
    for threshold in (0.0, GAP):
        judged = [correct(ranker, a, b) for a, b in pairs(max(threshold, 1e-9))]
        judged = [j for j in judged if j is not None]
        rate = sum(judged) / len(judged) if judged else float("nan")
        line += f"   {rate:>6.1%} (n={len(judged):>4})"
    print(line)

# The pre-registered comparison: paired, over pairs both rankers judged.
print()
for challenger in ("successor eval, averaged", "successor eval, one sample"):
    ahead = behind = 0
    for a, b in pairs(GAP):
        new = correct(RANKERS[challenger], a, b)
        old = correct(RANKERS["shipped action score"], a, b)
        if new is None or old is None or new == old:
            continue
        if new:
            ahead += 1
        else:
            behind += 1
    n = ahead + behind
    if n:
        z = (ahead - n / 2) / math.sqrt(n * 0.25)
        p = math.erfc(abs(z) / math.sqrt(2))
    else:
        p = float("nan")
    print(f"    {challenger} vs the action score, where they disagree:")
    print(f"      {ahead} right / {behind} wrong of {n}   p = {p:.4f}")

print("\n  the same, on uniformly drawn candidates only (the agent's own pick removed,")
print("  since the action score ranks it first by construction):\n")
print(f"    {'ranker':<30} {'all pairs':>12} {'gap >= 15pp':>14}")
for label, ranker in RANKERS.items():
    line = f"    {label:<30}"
    for threshold in (0.0, GAP):
        judged = [
            correct(ranker, a, b)
            for a, b in pairs(max(threshold, 1e-9), drop_picked=True)
        ]
        judged = [j for j in judged if j is not None]
        rate = sum(judged) / len(judged) if judged else float("nan")
        line += f"   {rate:>6.1%} (n={len(judged):>4})"
    print(line)

print("\n  how often does the agent already pick the best of its four candidates?")
best_picked = sum(
    1 for r in rows
    if r["candidates"][0]["win_rate"] == max(c["win_rate"] for c in r["candidates"])
)
print(f"    {best_picked} of {len(rows)} ({best_picked / len(rows):.0%}), "
      f"against 25% for picking at random")
