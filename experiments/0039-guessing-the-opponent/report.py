"""Did the search survive losing the opponent's move?

The pre-registered claim is a paired sign test over the decision points where
the guessed-opponent search chose something different from the agent. Points
where it chose the same action carry no information about whether searching
helps -- they are the same action graded on the same seeds -- so they are
counted and reported, not tested.
"""

import json
import math
import statistics
import sys
from pathlib import Path

DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("ranking3.json")
rows = json.loads(DATA.read_text(encoding="utf-8"))

same = [r for r in rows if r["search_picked_the_same_action"]]
differ = [r for r in rows if not r["search_picked_the_same_action"]]

print(f"{len(rows)} decision points from {len({r['battle'] for r in rows})} battles\n")
print(f"  search chose the agent's own action : {len(same):>4} ({len(same) / len(rows):.0%})")
print(f"  search chose something different    : {len(differ):>4} ({len(differ) / len(rows):.0%})")

# The control is the agent's own action re-rolled on disjoint seeds, so the
# gap between it and agent_rate is pure noise at this sample size.
noise = [r["control_rate"] - r["agent_rate"] for r in rows]
print("\n  noise floor (same action, disjoint seeds)")
print(f"    mean |difference|  {statistics.fmean(abs(x) for x in noise):>6.1%}")
print(f"    sd                 {statistics.pstdev(noise):>6.1%}")

print("\n  win rate on the true continuation\n")
print(f"    {'chooser':<44} {'all points':>11} {'where they differ':>19}")
for label, key in (
    ("the agent's own pick (shipped)", "agent_rate"),
    ("guessed-opponent search", "search_rate"),
):
    everywhere = statistics.fmean(r[key] for r in rows)
    differing = statistics.fmean(r[key] for r in differ) if differ else float("nan")
    print(f"    {label:<44} {everywhere:>10.1%} {differing:>18.1%}")

gap_all = statistics.fmean(r["search_rate"] - r["agent_rate"] for r in rows)
gap_differ = (
    statistics.fmean(r["search_rate"] - r["agent_rate"] for r in differ)
    if differ
    else float("nan")
)
print(f"\n    difference{'':<34} {gap_all:>+10.1%} {gap_differ:>+18.1%}")

# The pre-registered test.
ahead = sum(1 for r in differ if r["search_rate"] > r["agent_rate"])
behind = sum(1 for r in differ if r["search_rate"] < r["agent_rate"])
n = ahead + behind
z = (ahead - n / 2) / math.sqrt(n * 0.25) if n else 0.0
p = math.erfc(abs(z) / math.sqrt(2)) if n else float("nan")

print("\n  pre-registered: search beats the agent where the two choices differ")
print(f"    ahead {ahead}   behind {behind}   tied {len(differ) - n}   of {len(differ)}")
print(f"    paired sign test  p = {p:.4f}")
print(f"\n    {'CONFIRMED' if ahead > behind and p < 0.05 else 'NOT CONFIRMED'}")

print("\n  for comparison, 0038 with the opponent's move handed over:")
print("    one-ply search 57.5%, agent 56.1%, +1.4pp, p = 0.0201  CONFIRMED")
