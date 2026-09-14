"""0059 — keep near-universal moves on the sets that carry them.

    python experiments/0059-universal-moves/run.py          # measure
    python experiments/0059-universal-moves/run.py --write  # and adopt if the rule is met

See PRE-REGISTRATION.md. Needs 0057's usage file (its fetch.py). Both arms are
built now from the same M-C train split and seed; only how move slots are
picked differs.
"""

import sys
from collections import Counter
from pathlib import Path

from champions_ai.agents import HeuristicAgent
from champions_ai.cli.play import POOL_SEPARATOR, dex_path, pool_path_for
from champions_ai.data import BattleTeam, TeamPool, load_all, parse_showdown_team
from champions_ai.data.harvest import harvest_teams
from champions_ai.data.split import split_replays
from champions_ai.data.usage import (
    carry_rates,
    combine,
    load_smogon_chaos,
    open_sheet_distributions,
)
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_C
from champions_ai.env import BattleEnv
from champions_ai.evaluation.team_strength import scout_team
from champions_ai.simulator import ShowdownBridge
from champions_ai.simulator.tracker import to_id

USAGE_FILE = Path("data/usage/2026-08-gen9championsvgc2026regmb-1500.json.gz")
SEED = 0
OPPONENTS = 120
ARMS = ("corrected", "inclusion")
UNIVERSAL = 0.95
MID_RANGE = (0.40, 0.80)
WRITE = "--write" in sys.argv


def validate(bridge, texts):
    teams, kept = [], []
    for text in texts:
        try:
            packed = bridge.validate_team(REGULATION_M_C.format_id, text)
        except Exception:
            continue
        teams.append(
            BattleTeam(team=parse_showdown_team(text), packed=packed, name=f"pool-{len(teams)}")
        )
        kept.append(text)
    return teams, kept


def pool_moves(texts):
    """species id -> (sets, Counter of moves carried)."""
    sets: Counter = Counter()
    moves: dict[str, Counter] = {}
    for text in texts:
        for block in text.strip().split("\n\n"):
            lines = block.strip().splitlines()
            if not lines:
                continue
            species = to_id(lines[0].partition("@")[0])
            sets[species] += 1
            carried = {to_id(line[2:]) for line in lines if line.startswith("- ")}
            moves.setdefault(species, Counter()).update(carried)
    return sets, moves


def move_distance(pool_rates: dict[str, float], truth_rates: dict[str, float]) -> float:
    keys = set(pool_rates) | set(truth_rates)
    return 0.5 * sum(abs(pool_rates.get(k, 0.0) - truth_rates.get(k, 0.0)) for k in keys) / 4


def main() -> None:
    if not USAGE_FILE.exists():
        raise SystemExit(f"no usage file at {USAGE_FILE}; run 0057's fetch.py first")

    with ShowdownBridge() as bridge:
        dex = Dex.cached(bridge, dex_path(REGULATION_M_C), mod=REGULATION_M_C.mod)
        replays = list(load_all(Path("data/replays"), REGULATION_M_C.format_id, None).replays)
        train = split_replays(replays).train
        usage = combine(load_smogon_chaos(USAGE_FILE, dex), open_sheet_distributions(train, dex))
        print(f"\n  0059 — {len(train)} train replays of {len(replays)}\n")

        built = {}
        print("  assembly and engine validation")
        for arm in ARMS:
            texts = harvest_teams(train, dex=dex, seed=SEED, usage=usage, move_fill=arm)
            teams, kept = validate(bridge, texts)
            survival = len(kept) / max(1, len(texts))
            built[arm] = (teams, kept, survival)
            print(f"    {arm:<10} {len(texts)} assembled, {len(kept)} validated ({survival:.1%})")

        distance, universal, mid, rows = {}, {}, {}, {}
        for arm in ARMS:
            sets, moves = pool_moves(built[arm][1])
            d_total = weight = 0.0
            u_total = u_weight = m_total = m_weight = 0.0
            for species, count in sets.items():
                if species not in usage or not usage[species].moves:
                    continue
                truth = carry_rates(usage[species])
                rates = {m: n / count for m, n in moves.get(species, Counter()).items()}
                d = move_distance(rates, truth)
                rows.setdefault(species, {})[arm] = (count, d, rates)
                d_total += d * count
                weight += count
                for move, rate in truth.items():
                    if rate >= UNIVERSAL:
                        u_total += rates.get(move, 0.0) * count
                        u_weight += count
                    elif MID_RANGE[0] <= rate <= MID_RANGE[1]:
                        m_total += (rates.get(move, 0.0) - rate) * count
                        m_weight += count
            distance[arm] = d_total / weight
            universal[arm] = u_total / u_weight
            mid[arm] = m_total / m_weight

        print("\n  weighted move distance (0 = identical)")
        print("    " + "   ".join(f"{arm} {distance[arm]:.3f}" for arm in ARMS))
        print(f"\n  near-universal carry (truth {UNIVERSAL:.0%}+), "
              "pool carry weighted by appearances")
        print("    " + "   ".join(f"{arm} {universal[arm]:.1%}" for arm in ARMS))
        print(f"\n  mid-rate moves (truth {MID_RANGE[0]:.0%}-{MID_RANGE[1]:.0%}), "
              "mean pool minus truth")
        print("    " + "   ".join(f"{arm} {mid[arm]:+.1%}" for arm in ARMS))

        print("\n  top truth moves, carry rate: truth / corrected / inclusion")
        ranked = sorted(rows.items(), key=lambda kv: -kv[1][ARMS[0]][0])
        for species, per_arm in ranked[:12]:
            if len(per_arm) < len(ARMS):
                continue
            truth = carry_rates(usage[species])
            dists = " -> ".join(f"{per_arm[arm][1]:.3f}" for arm in ARMS)
            print(f"    {species:<16} {usage[species].source:<12} "
                  f"n={per_arm[ARMS[0]][0]:<5} distance {dists}")
            for move, rate in sorted(truth.items(), key=lambda kv: -kv[1])[:4]:
                arms = " / ".join(f"{per_arm[arm][2].get(move, 0.0):.0%}" for arm in ARMS)
                print(f"      {move:<18} {rate:.0%} / {arms}")

        env = BattleEnv(REGULATION_M_C, bridge=bridge)
        agent = HeuristicAgent(dex, name="scout")
        reference = built["corrected"][0][0]
        print(f"\n  reference team: {', '.join(m.species for m in reference.team.pokemon)}")
        for arm in ARMS:
            report = scout_team(env, agent, reference, TeamPool(built[arm][0]),
                                opponents=OPPONENTS, seed=SEED)
            print(f"    scouted vs {arm:<10} {report.wins}/{report.battles} "
                  f"({report.win_rate:.1%})")

        base_survival = built["corrected"][2]
        survival = built["inclusion"][2]
        adopt = (
            survival >= 0.90
            and abs(survival - base_survival) <= 0.05
            and distance["inclusion"] < distance["corrected"]
        )
        print(f"\n  adoption rule: {'MET' if adopt else 'NOT met'}")
        if WRITE and adopt:
            target = pool_path_for(REGULATION_M_C)
            backup = target.with_name(target.stem + "-pre0059.txt")
            if target.exists() and not backup.exists():
                target.replace(backup)
                print(f"    0058 pool kept at {backup}")
            target.write_text(POOL_SEPARATOR.join(built["inclusion"][1]), encoding="utf-8")
            print(f"    inclusion pool written to {target} ({len(built['inclusion'][1])} teams)")
        elif WRITE:
            print("    --write given, but the rule is not met: nothing written")
        print()


if __name__ == "__main__":
    main()
