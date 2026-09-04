"""Judge trained weights at the standing bar, not at the training loop's bar.

The evaluation inside `train.py` runs 400 battles so it can run often. That is
a progress signal and nothing more: because a warm-started policy still agrees
with the heuristic on most turns, most matchups **tie**, and 400 battles yield
only twenty to thirty *decided* ones. A 60% on twenty-five decided matchups is
noise wearing a percentage.

This is the real test: `>=1,500 battles across >=2 seeds, paired, teams
exchanged`, which is the bar this project has required of every strength claim
since 0018, and which 0029 was retracted for missing.

Two things are reported that a single win rate would hide.

**How often the policy and the heuristic actually differ.** If training moved
the weights but the greedy policy still picks the same action everywhere, the
win rate is 50% by construction and says nothing about learning. `tied` and
`changed_nothing` carry that.

**The weights themselves.** 0006 found its own mechanism by reading them --
`guaranteed_ko` at -1.63 explained a 32.5% win rate in one line, faster than
three experiments of disagreement analysis had managed.
"""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from policy import JOINT_FEATURE_NAMES, JointFeatures, JointPolicyAgent, warm_start_weights

from champions_ai.agents import HeuristicAgent
from champions_ai.data import TeamPool, load_all
from champions_ai.data.harvest import harvested_pool
from champions_ai.data.reconstruct import move_data_from_dex
from champions_ai.data.split import split_replays
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_B
from champions_ai.env import BattleEnv
from champions_ai.evaluation.runner import evaluate, wilson_interval
from champions_ai.simulator import ShowdownBridge

BATTLES = int(sys.argv[2]) if len(sys.argv) > 2 else 800
SEEDS = (11, 29, 53)
HOLDOUT = 50


def main() -> None:
    trained = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    weights = [trained["weights"][name] for name in JOINT_FEATURE_NAMES]

    corpus = load_all(Path("data/replays"))
    train_replays = list(split_replays(list(corpus.replays)).train)

    with ShowdownBridge() as bridge:
        dex = Dex.cached(bridge, Path("data/dex.json"))
        features = JointFeatures(dex, move_data_from_dex(dex))
        env = BattleEnv(REGULATION_M_B, bridge=bridge)
        pool = harvested_pool(
            bridge, REGULATION_M_B.format_id, train_replays, dex=dex, seed=1,
            cache=Path("data/pool-eval.txt"),
        )
        holdout = TeamPool(pool.teams[-HOLDOUT:])

        print(f"  {len(holdout)} held-out teams, {BATTLES} battles x {len(SEEDS)} seeds")
        print("  bar: >=1,500 battles across >=2 seeds, paired\n")

        ahead = behind = tied = played = wins = 0
        for seed in SEEDS:
            agent = JointPolicyAgent(weights, features, name="trained")
            result = evaluate(
                env, agent, HeuristicAgent(dex, name="shipped"), holdout,
                battles=BATTLES, seed=seed,
            )
            ahead += result.matchups_won
            behind += result.matchups_lost
            tied += result.matchups_tied
            wins += result.wins_a
            played += result.wins_a + result.wins_b
            print(
                f"    seed {seed:<4} {result.matchups_won:>4}/"
                f"{result.decided_matchups:<4} = {result.paired_win_rate:>6.1%}"
                f"   ({result.matchups_tied} tied of {result.matchups_played})",
                flush=True,
            )

        decided = ahead + behind
        if not decided:
            print("\n  every matchup tied: the trained policy plays the heuristic exactly.")
            return
        lo, hi = wilson_interval(ahead, decided)
        z = (ahead - decided / 2) / math.sqrt(decided * 0.25)
        p = math.erfc(abs(z) / math.sqrt(2))
        print(f"\n  pooled   {ahead}/{decided} = {ahead / decided:.1%}"
              f"   95% CI {lo:.1%}-{hi:.1%}   p = {p:.4f}")
        print(f"  raw win rate {wins / played:.1%} over {played} battles,"
              f" {tied} matchups tied")
        print(f"  the policy differed from the heuristic on"
              f" {decided / (decided + tied):.0%} of matchups")
        print()
        if ahead / decided > 0.5 and p < 0.05:
            print("  CONFIRMED: the trained policy beats the heuristic.")
        else:
            print("  NOT CONFIRMED.")

        print("\n  weights, largest movement from the warm start first")
        start = warm_start_weights()
        moved = sorted(
            (
                (abs(w - s), name, w, s)
                for name, w, s in zip(JOINT_FEATURE_NAMES, weights, start, strict=True)
            ),
            reverse=True,
        )
        print(f"    {'feature':<26} {'trained':>9} {'warm start':>11}")
        for _, name, value, origin in moved[:10]:
            print(f"    {name:<26} {value:>+9.3f} {origin:>+11.3f}")


if __name__ == "__main__":
    main()
