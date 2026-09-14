"""0057 — build the team pool from what sets actually carry.

    python experiments/0057-pool-from-usage/fetch.py      # once
    python experiments/0057-pool-from-usage/run.py        # measure
    python experiments/0057-pool-from-usage/run.py --write

See PRE-REGISTRATION.md. Both pools are built now from the same M-C train split
and seed; only items, natures and spreads can differ.
"""

import sys
from collections import Counter
from pathlib import Path

from champions_ai.agents import HeuristicAgent
from champions_ai.cli.play import POOL_SEPARATOR, dex_path, pool_path_for
from champions_ai.data import BattleTeam, TeamPool, load_all, parse_showdown_team
from champions_ai.data.harvest import harvest_teams
from champions_ai.data.split import split_replays
from champions_ai.data.usage import combine, load_smogon_chaos, open_sheet_distributions
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_C
from champions_ai.env import BattleEnv
from champions_ai.evaluation.team_strength import scout_team
from champions_ai.simulator import ShowdownBridge
from champions_ai.simulator.tracker import to_id

USAGE_FILE = Path("data/usage/2026-08-gen9championsvgc2026regmb-1500.json.gz")
SEED = 0
OPPONENTS = 120
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


def pool_items(texts):
    by_species: dict[str, Counter] = {}
    for text in texts:
        for block in text.strip().split("\n\n"):
            first = block.strip().splitlines()[0] if block.strip() else ""
            if not first:
                continue
            species, _, item = first.partition("@")
            by_species.setdefault(to_id(species), Counter())[to_id(item)] += 1
    return by_species


def total_variation(observed: Counter, truth: Counter) -> float:
    o_total, t_total = sum(observed.values()), sum(truth.values())
    if not o_total or not t_total:
        return float("nan")
    keys = set(observed) | set(truth)
    return 0.5 * sum(abs(observed[k] / o_total - truth[k] / t_total) for k in keys)


def main() -> None:
    if not USAGE_FILE.exists():
        raise SystemExit(f"no usage file at {USAGE_FILE}; run fetch.py first")

    with ShowdownBridge() as bridge:
        dex = Dex.cached(bridge, dex_path(REGULATION_M_C), mod=REGULATION_M_C.mod)
        replays = list(load_all(Path("data/replays"), REGULATION_M_C.format_id, None).replays)
        train = split_replays(replays).train

        smogon = load_smogon_chaos(USAGE_FILE, dex)
        sheets = open_sheet_distributions(train, dex)
        usage = combine(smogon, sheets)

        print(f"\n  0057 — {len(train)} train replays of {len(replays)}")
        print(f"  usage: {len(smogon)} species from Smogon, {len(sheets)} from open sheets\n")

        old_texts = harvest_teams(train, dex=dex, seed=SEED)
        new_texts = harvest_teams(train, dex=dex, seed=SEED, usage=usage)
        old_teams, old_kept = validate(bridge, old_texts)
        new_teams, new_kept = validate(bridge, new_texts)

        print("  assembly and engine validation")
        for label, texts, kept in (("old", old_texts, old_kept), ("new", new_texts, new_kept)):
            print(f"    {label}: {len(texts)} assembled, {len(kept)} validated "
                  f"({len(kept) / max(1, len(texts)):.1%})")

        items_new = pool_items(new_kept)
        items_old = pool_items(old_kept)
        appearances = Counter({s: sum(c.values()) for s, c in items_new.items()})
        total = sum(appearances.values())
        by_source = Counter()
        for species, count in appearances.items():
            source = usage[species].source if species in usage else "fallback"
            by_source[source] += count
        print("\n  coverage of pool Pokemon")
        for source in ("smogon", "open-sheets", "fallback"):
            print(f"    {source:<12} {by_source[source]:6}  ({by_source[source] / total:.1%})")

        weighted_old = weighted_new = weight = 0.0
        rows = []
        for species, count in appearances.most_common():
            if species not in usage:
                continue
            truth = usage[species].items
            tv_old = total_variation(items_old.get(species, Counter()), truth)
            tv_new = total_variation(items_new.get(species, Counter()), truth)
            if tv_old != tv_old or tv_new != tv_new:
                continue
            weighted_old += tv_old * count
            weighted_new += tv_new * count
            weight += count
            rows.append((species, usage[species].source, count, tv_old, tv_new))
        print("\n  item distance to the truth source (total variation; 0 = identical)")
        print(f"    weighted: old {weighted_old / weight:.3f}   new {weighted_new / weight:.3f}")
        for species, source, count, tv_old, tv_new in rows[:12]:
            print(f"    {species:<18} {source:<12} n={count:<5} old {tv_old:.2f}  new {tv_new:.2f}")

        env = BattleEnv(REGULATION_M_C, bridge=bridge)
        agent = HeuristicAgent(dex, name="scout")
        reference = old_teams[0]
        print(f"\n  reference team: {', '.join(m.species for m in reference.team.pokemon)}")
        for label, teams in (("old pool", old_teams), ("new pool", new_teams)):
            report = scout_team(env, agent, reference, TeamPool(teams),
                                opponents=OPPONENTS, seed=SEED)
            print(f"    scouted vs {label}: {report.wins}/{report.battles} "
                  f"({report.win_rate:.1%})")

        survival_old = len(old_kept) / max(1, len(old_texts))
        survival_new = len(new_kept) / max(1, len(new_texts))
        adopt = (
            survival_new >= 0.90
            and abs(survival_new - survival_old) <= 0.05
            and weighted_new < weighted_old
        )
        print(f"\n  adoption rule: {'MET' if adopt else 'NOT met'}")
        if WRITE and adopt:
            target = pool_path_for(REGULATION_M_C)
            backup = target.with_name(target.stem + "-pre0057.txt")
            if target.exists() and not backup.exists():
                target.replace(backup)
                print(f"    old pool kept at {backup}")
            target.write_text(POOL_SEPARATOR.join(new_kept), encoding="utf-8")
            print(f"    new pool written to {target} ({len(new_kept)} teams)")
        elif WRITE:
            print("    --write given, but the rule is not met: nothing written")
        print()


if __name__ == "__main__":
    main()
