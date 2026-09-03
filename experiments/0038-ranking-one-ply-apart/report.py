"""The pre-registered confirmation: choose on one half, score on the other.

The first run put one-ply search at +2.9 points, but selected the action with
an evaluation computed from the very rollouts that then graded it. Here the
rollouts are split. Odd-numbered ones choose; even-numbered ones score. The
split is then done the other way round and the two averaged, because each
direction is unbiased on its own and averaging halves the variance.

Pre-registered claim, fixed before the run:

    on held-out rollouts, the action chosen by successor evaluation beats the
    action the agent actually picked -- paired sign test over decision points,
    p < 0.05
"""

import json
import math
import statistics
import sys
from itertools import combinations
from pathlib import Path

DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("ranking2.json")
rows = json.loads(DATA.read_text(encoding="utf-8"))

print(f"{len(rows)} decision points from {len({r['battle'] for r in rows})} battles")
print(f"  {sum(len(r['candidates']) for r in rows)} candidates, "
      f"{sum(len(c['won']) for r in rows for c in r['candidates'])} rollouts\n")


def half(candidate, parity):
    """Rollouts whose index has this parity: outcomes, and the mean evaluation."""
    won = [w for i, w in enumerate(candidate["won"]) if i % 2 == parity]
    evals = [
        e for i, e in enumerate(candidate["evals"]) if i % 2 == parity and e is not None
    ]
    return (
        sum(won) / len(won) if won else 0.0,
        statistics.fmean(evals) if evals else 0.0,
    )


CHOOSERS = {
    "successor eval (one-ply search)": lambda cs, sel: max(
        range(len(cs)), key=lambda i: sel[i][1]
    ),
    "the agent's own pick (shipped)": lambda cs, sel: 0,
    "best on the selection half": lambda cs, sel: max(
        range(len(cs)), key=lambda i: sel[i][0]
    ),
    "worst on the selection half": lambda cs, sel: min(
        range(len(cs)), key=lambda i: sel[i][0]
    ),
}


def evaluate(chooser):
    """Mean held-out win rate of this chooser's pick, both splits averaged."""
    total = []
    for row in rows:
        for select, score in ((1, 0), (0, 1)):
            sel = [half(c, select) for c in row["candidates"]]
            pick = chooser(row["candidates"], sel)
            total.append(half(row["candidates"][pick], score)[0])
    return statistics.fmean(total)


print("  held out: the half of the rollouts that did not choose the action\n")
print(f"    {'chooser':<38} {'win rate':>9}   {'vs shipped':>11}")
shipped = evaluate(CHOOSERS["the agent's own pick (shipped)"])
for name, chooser in CHOOSERS.items():
    value = evaluate(chooser)
    mark = "" if name.startswith("the agent") else f"{(value - shipped) * 100:+.1f}pp"
    print(f"    {name:<38} {value:>8.1%}   {mark:>11}")

# The pre-registered test. One point contributes once per split direction, so
# the two directions are pooled and that is stated rather than hidden.
ahead = behind = tied = 0
for row in rows:
    for select, score in ((1, 0), (0, 1)):
        sel = [half(c, select) for c in row["candidates"]]
        pick = max(range(len(row["candidates"])), key=lambda i: sel[i][1])
        ours = half(row["candidates"][pick], score)[0]
        theirs = half(row["candidates"][0], score)[0]
        if ours > theirs:
            ahead += 1
        elif ours < theirs:
            behind += 1
        else:
            tied += 1

n = ahead + behind
z = (ahead - n / 2) / math.sqrt(n * 0.25) if n else 0.0
p = math.erfc(abs(z) / math.sqrt(2)) if n else float("nan")
print("\n  pre-registered: search's pick beats the agent's on held-out rollouts")
print(f"    ahead {ahead}   behind {behind}   tied {tied}"
      f"   ({len(rows)} points x 2 split directions)")
print(f"    paired sign test  p = {p:.4f}")
print(f"\n    {'CONFIRMED' if ahead > behind and p < 0.05 else 'NOT CONFIRMED'}")

# Pairwise ranking accuracy, also split so the ordering is judged on rollouts
# that did not produce it.
print("\n  pairwise ranking accuracy, judged on the held-out half\n")
print(f"    {'ranker':<34} {'all pairs':>13} {'gap >= 15pp':>15}")
RANKERS = {
    "successor eval": lambda cs, sel, i: sel[i][1],
    "shipped action score": lambda cs, sel, i: cs[i]["action_score"],
}
for label, ranker in RANKERS.items():
    line = f"    {label:<34}"
    for threshold in (0.0, 0.15):
        right = judged = 0
        for row in rows:
            for select, score in ((1, 0), (0, 1)):
                sel = [half(c, select) for c in row["candidates"]]
                out = [half(c, score)[0] for c in row["candidates"]]
                for i, j in combinations(range(len(row["candidates"])), 2):
                    if abs(out[i] - out[j]) < max(threshold, 1e-9):
                        continue
                    predicted = ranker(row["candidates"], sel, i) - ranker(
                        row["candidates"], sel, j
                    )
                    if predicted == 0:
                        continue
                    judged += 1
                    right += (predicted > 0) == (out[i] > out[j])
        rate = right / judged if judged else float("nan")
        line += f"   {rate:>6.1%} (n={judged:>5})"
    print(line)
