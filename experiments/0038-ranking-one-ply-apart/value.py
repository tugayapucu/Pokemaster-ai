"""Turn the ranking accuracy into the number that decides whether to build it.

Pairwise accuracy answers "does it order better". It does not say what ordering
better is worth, and this project has been wrong before by stopping at the
first of those -- 0013 called target selection the largest gap on an accuracy
figure and it turned out to be a ceiling.

So: at each decision point, what does each chooser actually get? Every
candidate's win rate was measured by rollout, so a chooser can simply be
applied and its pick's win rate read off.

  best of the four        a perfect ranker, and the ceiling for any of this
  the agent's own pick    what ships today
  successor evaluation    what a one-ply search would choose
  average of the four     picking at random among them
  worst of the four       the floor

**One bias, stated rather than corrected.** The agent's pick is chosen with no
reference to the rollouts, so its measured win rate is unbiased. "Best of four"
is the maximum of four noisy estimates and is inflated; with a per-measurement
noise sd of about 6 points the inflation is roughly 6 points. Successor
evaluation is read off the same rollouts that produced the win rates, so a
rollout that went well lifts both -- a smaller bias in the same direction. The
paired pairwise test is the clean comparison; this is the interpretable one.
"""

import json
import math
import statistics
import sys
from pathlib import Path

DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("ranking.json")
rows = json.loads(DATA.read_text(encoding="utf-8"))

# Points where at least one action did something different from another.
live = [
    r for r in rows
    if len({c["win_rate"] for c in r["candidates"]}) > 1
]

CHOOSERS = {
    "best of the four (a perfect ranker)": lambda cs: max(cs, key=lambda c: c["win_rate"]),
    "successor eval, averaged": lambda cs: max(cs, key=lambda c: c["eval_mean"]),
    "successor eval, one sample": lambda cs: max(cs, key=lambda c: c["eval_one"]),
    "the agent's own pick (shipped)": lambda cs: cs[0],
    "picking at random among the four": None,
    "worst of the four": lambda cs: min(cs, key=lambda c: c["win_rate"]),
}


def report(label, subset):
    print(f"\n  {label} -- {len(subset)} decision points\n")
    print(f"    {'chooser':<38} {'win rate':>9}   {'vs shipped':>10}")
    shipped = statistics.fmean(r["candidates"][0]["win_rate"] for r in subset)
    for name, chooser in CHOOSERS.items():
        if chooser is None:
            value = statistics.fmean(
                statistics.fmean(c["win_rate"] for c in r["candidates"]) for r in subset
            )
        else:
            value = statistics.fmean(chooser(r["candidates"])["win_rate"] for r in subset)
        delta = value - shipped
        mark = "" if name.startswith("the agent") else f"{delta * 100:+.1f}pp"
        print(f"    {name:<38} {value:>8.1%}   {mark:>10}")


print(f"{len(rows)} decision points, {len(live)} where the four candidates "
      f"did not all score the same")

report("every decision point", rows)
report("only where the choice changed something", live)

# How much of the perfect ranker's edge does the search actually capture?
shipped = statistics.fmean(r["candidates"][0]["win_rate"] for r in live)
perfect = statistics.fmean(
    max(r["candidates"], key=lambda c: c["win_rate"])["win_rate"] for r in live
)
search = statistics.fmean(
    max(r["candidates"], key=lambda c: c["eval_mean"])["win_rate"] for r in live
)
print(f"\n  headroom between what ships and a perfect ranker: {perfect - shipped:.1%}")
print(f"  of which successor evaluation captures:           {search - shipped:.1%}"
      f"  ({(search - shipped) / (perfect - shipped):.0%})")

# Paired significance on the win-rate difference, decision point by decision
# point: how often does search's pick beat the agent's, and by how much.
ahead = behind = 0
for r in live:
    theirs = r["candidates"][0]["win_rate"]
    ours = max(r["candidates"], key=lambda c: c["eval_mean"])["win_rate"]
    if ours > theirs:
        ahead += 1
    elif ours < theirs:
        behind += 1
n = ahead + behind
z = (ahead - n / 2) / math.sqrt(n * 0.25) if n else 0.0
print(f"\n  points where search's pick beat the agent's: {ahead}"
      f"   lost: {behind}   tied: {len(live) - n}")
print(f"  paired sign test  p = {math.erfc(abs(z) / math.sqrt(2)):.4f}")

# Where the value is: is the decision point predictable in advance?
print("\n  by how much the four candidates actually differed:")
print(f"    {'spread between best and worst':<38} {'points':>7} {'headroom':>9}")
for lo, hi, label in ((0.0, 0.10, "under 10pp"), (0.10, 0.30, "10-30pp"),
                      (0.30, 0.60, "30-60pp"), (0.60, 1.01, "over 60pp")):
    bucket = [
        r for r in rows
        if lo <= (max(c["win_rate"] for c in r["candidates"])
                  - min(c["win_rate"] for c in r["candidates"])) < hi
    ]
    if not bucket:
        continue
    s = statistics.fmean(r["candidates"][0]["win_rate"] for r in bucket)
    p = statistics.fmean(
        max(r["candidates"], key=lambda c: c["win_rate"])["win_rate"] for r in bucket
    )
    print(f"    {label:<38} {len(bucket):>7} {p - s:>8.1%}")
