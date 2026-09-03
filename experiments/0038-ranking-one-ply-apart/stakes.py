"""Can we tell in advance which decisions are worth thinking about?

The rollouts say the stakes at a decision point vary enormously: at 100 of 358
points the best and worst of four candidates finish within 10 points of each
other, and at 140 they differ by more than 60. A search that ran only on the
second kind would cost a fraction of one that runs everywhere.

That is only useful if the distinction is visible *before* the rollouts, since
the rollouts are the expensive thing. So: which cheaply observable features of
a position predict how much is at stake?

Candidates, all free at decision time:

  turn                    early boards are less resolved
  legal actions           a cramped position may have less to choose between
  action-score spread     the heuristic's own scores across the four candidates
  position evaluation     how lopsided the board already is
  decidedness             |eval| large means the game may be past saving

The measure of stakes is the observed best-minus-worst win rate, which is
inflated by rollout noise -- the first run put that at a 9.0 point standard
deviation for a repeated identical action. The inflation is roughly constant
across points, so it shifts every bucket up together and leaves the *ordering*
between buckets intact. Ordering is all that is claimed here.
"""

import json
import statistics
import sys
from pathlib import Path

DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("ranking.json")
rows = json.loads(DATA.read_text(encoding="utf-8"))


def stakes(row):
    rates = [c["win_rate"] for c in row["candidates"]]
    return max(rates) - min(rates)


def features(row):
    scores = [c["action_score"] for c in row["candidates"]]
    evals = [c["eval_mean"] for c in row["candidates"]]
    return {
        "turn": row["turn"],
        "legal actions": row["legal"],
        "action-score spread": max(scores) - min(scores),
        "board evaluation": statistics.fmean(evals),
        "how lopsided the board is": abs(statistics.fmean(evals)),
    }


print(f"{len(rows)} decision points\n")
print(f"  stakes overall: mean {statistics.fmean(stakes(r) for r in rows):.1%}, "
      f"median {statistics.median(stakes(r) for r in rows):.1%}\n")

names = list(features(rows[0]))
for name in names:
    values = sorted((features(r)[name], stakes(r)) for r in rows)
    quartile = max(1, len(values) // 4)
    print(f"  {name}")
    print(f"    {'range':<22} {'points':>7} {'mean stakes':>12} {'nothing at stake':>18}")
    for start, label in (
        (0, "lowest quarter"),
        (quartile, "second"),
        (2 * quartile, "third"),
        (3 * quartile, "highest quarter"),
    ):
        chunk = values[start : start + quartile] if start < 3 * quartile else values[start:]
        if not chunk:
            continue
        flat = sum(1 for _, s in chunk if s < 0.10) / len(chunk)
        span = f"{chunk[0][0]:.0f} to {chunk[-1][0]:.0f}"
        print(f"    {span:<22} {len(chunk):>7} "
              f"{statistics.fmean(s for _, s in chunk):>11.1%} {flat:>17.0%}")
    print()

# A gate is worth having only if the quarter it skips holds little headroom.
# Which end to skip is whichever the quartile table above says is quiet, so
# both are tried rather than assuming the feature points the helpful way.
def headroom(subset):
    return statistics.fmean(
        max(c["win_rate"] for c in r["candidates"]) - r["candidates"][0]["win_rate"]
        for r in subset
    )


overall = headroom(rows)
print(f"  headroom over the whole set: {overall:.1%}\n")
print("  what a gate would cost: skip a quarter of decisions without searching")
print("  them, and take the agent's own pick there instead\n")
print(f"    {'gate':<44} {'skipped':>8} {'kept':>7} {'lost':>7}")
for name in names:
    values = sorted(((features(r)[name], r) for r in rows), key=lambda pair: pair[0])
    quartile = max(1, len(values) // 4)
    for end, label in (("low", "lowest"), ("high", "highest")):
        skipped = (
            [r for _, r in values[:quartile]]
            if end == "low"
            else [r for _, r in values[-quartile:]]
        )
        kept = (
            [r for _, r in values[quartile:]]
            if end == "low"
            else [r for _, r in values[:-quartile]]
        )
        # What the gate throws away: the headroom sitting in the skipped
        # quarter, as a share of the headroom available everywhere.
        lost = headroom(skipped) * len(skipped) / (overall * len(rows))
        print(f"    {label + ' quarter of ' + name:<44} {headroom(skipped):>7.1%} "
              f"{headroom(kept):>7.1%} {lost:>6.0%}")
