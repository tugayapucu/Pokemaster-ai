"""0047 — the same agent, but for a corpus-derived guess at an opponent's ability.

See PRE-REGISTRATION.md. `evaluate` swaps the agents between the two passes of
every matchup on a shared seed, so the teams and the seats are identical and the
only difference is the flag.

    python experiments/0047-ability-priors/run.py [battles]
"""

import sys
from pathlib import Path

from champions_ai.agents import HeuristicAgent
from champions_ai.cli.play import dex_path, load_pool, pool_path_for
from champions_ai.data.priors import load_priors
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_C
from champions_ai.env import BattleEnv
from champions_ai.evaluation.runner import evaluate, wilson_interval
from champions_ai.simulator import ShowdownBridge

BATTLES = int(sys.argv[1]) if len(sys.argv) > 1 else 400


def main() -> None:
    priors = load_priors(Path(f"data/priors-{REGULATION_M_C.mod}.json"))
    if not priors:
        raise SystemExit("no priors file; build it before measuring against it")

    with ShowdownBridge() as bridge:
        dex = Dex.cached(bridge, dex_path(REGULATION_M_C), mod=REGULATION_M_C.mod)
        pool = load_pool(bridge, REGULATION_M_C, pool_path_for(REGULATION_M_C))
        env = BattleEnv(REGULATION_M_C, bridge=bridge)

        with_prior = HeuristicAgent(dex, name="prior", ability_priors=priors)
        without = HeuristicAgent(dex, name="blind")

        print(f"\n  0047 — {BATTLES} battles, {len(pool.teams)} teams in the pool")
        print(f"  prior covers {len(priors)} species\n")

        result = evaluate(env, with_prior, without, pool, battles=BATTLES, seed=0)
        low, high = wilson_interval(result.wins_a, result.battles)
        print(
            f"    prior {result.wins_a} / blind {result.wins_b} of {result.battles}"
            f"   ({result.win_rate_a:.1%})"
        )
        print(f"    95% Wilson [{low:.1%}, {high:.1%}]")
        verdict = (
            "above 50%: the prior earns its place"
            if low > 0.5
            else "below 50%: a wrong guess is worse than silence"
            if high < 0.5
            else "neutral: real information that does not convert"
        )
        print(f"\n    {verdict}")


if __name__ == "__main__":
    main()
