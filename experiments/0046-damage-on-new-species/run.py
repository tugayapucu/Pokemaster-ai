"""0046 — damage accuracy on M-C's new species against everything else.

Paired by construction: both arms come out of the same battles with the same
seeds, so anything wrong with the harness is wrong for both equally. See
PRE-REGISTRATION.md for the arms, the exclusions and the prediction.

    python experiments/0046-damage-on-new-species/run.py [battles]
"""

import sys
from collections import Counter
from pathlib import Path

from champions_ai.agents import HeuristicAgent
from champions_ai.cli.play import dex_path
from champions_ai.data import TeamPool
from champions_ai.dex import Dex
from champions_ai.dex.reference import to_id
from champions_ai.domain import REGULATION_M_B, REGULATION_M_C
from champions_ai.env import BattleEnv
from champions_ai.evaluation.differential import DamageCollector, active_by_ident, compare
from champions_ai.evaluation.runner import wilson_interval
from champions_ai.simulator import ShowdownBridge

BATTLES = int(sys.argv[1]) if len(sys.argv) > 1 else 60
POOL = Path("data/pool-eval-m-c.txt")
SEPARATOR = "\n\n===\n\n"


def new_species(bridge) -> set[str]:
    """M-C's additions, minus alternate formes.

    Formes are dropped because twelve of the 35 are Megas, Mega already costs
    seven points of accuracy on its own, and mixing it in would confound "new
    species" with "Mega".
    """
    mc = Dex.load(bridge, mod=REGULATION_M_C.mod)
    mb = Dex.load(bridge, mod=REGULATION_M_B.mod)
    added = set(mc.species) - set(mb.species)
    return {
        species
        for species in added
        if to_id(mc.species[species].base_species) == species
    }


def main() -> None:
    with ShowdownBridge() as bridge:
        added = new_species(bridge)
        dex = Dex.cached(bridge, dex_path(REGULATION_M_C), mod=REGULATION_M_C.mod)
        texts = [t for t in POOL.read_text(encoding="utf-8").split(SEPARATOR) if t.strip()]
        pool = TeamPool.from_texts(bridge, REGULATION_M_C.format_id, texts[:120])
        env = BattleEnv(REGULATION_M_C, bridge=bridge)

        arms: dict[str, list] = {"new": [], "old": []}
        drivers: Counter = Counter()
        skipped_mega = 0

        for n in range(BATTLES):
            teams = (pool.teams[n % len(pool.teams)], pool.teams[(n + 7) % len(pool.teams)])
            agents = (HeuristicAgent(dex, name="a"), HeuristicAgent(dex, name="b"))
            for agent in agents:
                agent.on_battle_start()
            result = env.reset(teams, seed=f"sodium,{n:032x}")
            collector = DamageCollector()
            seen = 0

            while not result.terminal:
                waiting = env.awaiting()
                if not waiting:
                    break
                choices = {}
                for player in waiting:
                    if env.decision(player).name == "TEAM_PREVIEW":
                        choices[player] = agents[player].select_team_preview(
                            env.team_preview(player), REGULATION_C_SIZE
                        )
                    else:
                        choices[player] = agents[player].select_action(
                            env.observation(player), env.legal_actions(player)
                        )
                # Whole teams rather than a pre-turn `Side` snapshot. A Side
                # resolves by slot, which is stale the moment anything switches
                # mid-turn; whole teams resolve by species, whose only blind
                # spot is a Mega changing its own name -- and Mega is excluded
                # from this measurement anyway.
                lookup = active_by_ident({
                    "p1": list(env.observation(0).own_side.team),
                    "p2": list(env.observation(1).own_side.team),
                })
                result = env.step(choices)
                chunk = result.protocol[seen:]
                seen = len(result.protocol)
                for sample in collector.feed(chunk, lookup):
                    attacker = to_id(sample.attacker.pokemon_set.species)
                    defender = to_id(sample.defender.pokemon_set.species)
                    if "mega" in attacker or "mega" in defender:
                        skipped_mega += 1
                        continue
                    involved = [s for s in (attacker, defender) if s in added]
                    arms["new" if involved else "old"].append(sample)
                    for species in involved:
                        drivers[species] += 1

        print(f"\n  0046 — {BATTLES} battles of Reg M-C self-play on harvested teams")
        print(f"  {skipped_mega} samples dropped for involving a Mega forme\n")
        print(f"    {'arm':<6}{'inside':>9}{'n':>8}   95% Wilson")
        results = {}
        for arm in ("old", "new"):
            report = compare(arms[arm], dex, level=REGULATION_M_C.level, doubles=True)
            results[arm] = report
            if not report.samples:
                print(f"    {arm:<6}  no samples")
                continue
            low, high = wilson_interval(report.inside_range, report.samples)
            print(
                f"    {arm:<6}{report.accuracy:>9.1%}{report.samples:>8}"
                f"   [{low:.1%}, {high:.1%}]"
            )
        if results["old"].samples and results["new"].samples:
            gap = results["new"].accuracy - results["old"].accuracy
            print(f"\n    new - old: {gap:+.1%}")
        # Guessing at a cause twice was enough. The mismatches say which hits
        # actually miss, and neither guess was in the species list.
        print("\n  what the 'new' arm gets wrong:")
        for line in results["new"].mismatches[:18]:
            print(f"    {line}")

        print("\n  species driving the 'new' arm:")
        for species, count in drivers.most_common(10):
            print(f"    {count:>5}  {species}")


REGULATION_C_SIZE = REGULATION_M_C.picked_team_size

if __name__ == "__main__":
    main()
