"""Regret by when a move pays off.

For each candidate: `true win rate` minus `true win rate of the agent's pick`,
where both come from rollouts and the candidate was chosen by our scorer, which
never saw them. A positive mean for a class means the scorer is passing up
value there.

**The control is `damage (now)`.** Those moves have no delayed payoff to miss,
so whatever regret they carry is the floor -- the part that comes from the
agent simply not being a perfect ranker, which 0038 already measured. A delayed
class only counts as evidence if it sits clearly above that floor.

The noise floor matters as much. With fourteen rollouts a win rate carries
about thirteen points of standard error, so a difference of two win rates
carries about nineteen, and a class mean over n candidates about 19/sqrt(n).
That is printed next to every row rather than left for the reader to work out.
"""

import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("delayed.json")
rows = [r for r in __import__("json").loads(DATA.read_text(encoding="utf-8"))]

print(f"{len(rows)} decision points from {len({r['battle'] for r in rows})} battles")
print(f"  {sum(len(r['candidates']) for r in rows)} candidates rolled out")
print(f"  median legal variants of the varied slot: "
      f"{statistics.median(r['variants'] for r in rows):.0f}\n")

by_class: dict[str, list[float]] = defaultdict(list)
picked_class: dict[str, list[float]] = defaultdict(list)
score_gap: dict[str, list[float]] = defaultdict(list)

for row in rows:
    pick = next((c for c in row["candidates"] if c["is_pick"]), None)
    if pick is None:
        continue
    picked_class[pick["payoff"]].append(pick["win_rate"])
    for candidate in row["candidates"]:
        if candidate["is_pick"]:
            continue
        by_class[candidate["payoff"]].append(candidate["win_rate"] - pick["win_rate"])
        score_gap[candidate["payoff"]].append(candidate["score"] - pick["score"])

print("  Regret by when the alternative pays off")
print("  (positive = the alternative actually did better than what we chose)\n")
print(f"    {'payoff class':<24} {'n':>5} {'mean regret':>12} {'+- 1 se':>9} {'we scored it':>13}")
order = sorted(by_class, key=lambda c: -statistics.fmean(by_class[c]))
for name in order:
    values = by_class[name]
    if len(values) < 15:
        continue
    mean = statistics.fmean(values)
    se = statistics.pstdev(values) / math.sqrt(len(values)) if len(values) > 1 else 0.0
    flag = "  <-- control" if name.startswith("damage") else ""
    # How far below the pick our scorer put these, because the classes are not
    # score-matched: a damage alternative is usually the near-tied second-best
    # attack, while a status alternative is often ranked far lower. An
    # alternative we scored well below the pick that still performs as well is
    # a stronger signal than one we nearly chose anyway.
    gap = statistics.fmean(score_gap[name]) if score_gap.get(name) else 0.0
    print(f"    {name:<24} {len(values):>5} {mean:>11.1%} {se:>9.1%} {-gap:>12.0f}{flag}")

control = by_class.get("damage (now)", [])
if control:
    base = statistics.fmean(control)
    print(f"\n  Above the damage floor of {base:+.1%}:")
    for name in order:
        values = by_class[name]
        if len(values) < 15 or name.startswith("damage"):
            continue
        gap = statistics.fmean(values) - base
        se = math.sqrt(
            statistics.pvariance(values) / len(values)
            + statistics.pvariance(control) / len(control)
        )
        z = gap / se if se else 0.0
        p = math.erfc(abs(z) / math.sqrt(2))
        print(f"    {name:<24} {gap:>+11.1%}   p = {p:.3f}")

print("\n  What the agent actually picks, and how it does")
print(f"    {'payoff class':<24} {'picked':>7} {'win rate':>10}")
for name in sorted(picked_class, key=lambda c: -len(picked_class[c])):
    values = picked_class[name]
    print(f"    {name:<24} {len(values):>7} {statistics.fmean(values):>9.1%}")

print("\n  Individual moves we passed up, by mean regret  (>= 12 sightings)")
per_move: dict[str, list[float]] = defaultdict(list)
for row in rows:
    pick = next((c for c in row["candidates"] if c["is_pick"]), None)
    if pick is None:
        continue
    for candidate in row["candidates"]:
        if candidate["is_pick"] or not candidate["move"]:
            continue
        per_move[candidate["move"]].append(candidate["win_rate"] - pick["win_rate"])
ranked = [
    (statistics.fmean(v), len(v), name) for name, v in per_move.items() if len(v) >= 12
]
print(f"    {'move':<22} {'n':>5} {'mean regret':>12}")
for mean, count, name in sorted(ranked, reverse=True)[:10]:
    print(f"    {name:<22} {count:>5} {mean:>11.1%}")
