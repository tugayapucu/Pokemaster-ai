"""Is the whole status-move category underpriced, or do humans overuse it?

`review --all` found the disagreement with rated players is a category rather
than a move: Charm 3%, Disable 4%, Hypnosis 4%, Will-O-Wisp 4%, Reflect 5%,
Substitute 6%, Roost 8%, Calm Mind 8%, Swords Dance 8%, Yawn 8%, Parting Shot
8% agreement, on 44 to 449 plays each. Humans reach for non-damaging moves far
more than this agent ranks them.

Two readings, and this project has been caught by the first one twice:

  - 1500-1850 Elo players overuse setup and status, which agreement would
    report in exactly this shape. 0010 and 0013 are both precedents.
  - the category really is underpriced, and the earlier measurement missed it.

The earlier measurement is `tenure_boosts`, which 0023 and 0025 put at +0.9
points, p = 0.48, and left off by default. **It is a boolean**, so it was
tested at two settings -- which is the exact shape 0032 warned about. Switching
was called a null three times by sampling one horizon per attempt, and the
answer changed sign the moment somebody swept it.

So `status_scale` is a scalar on the whole non-damaging branch, and this sweeps
it. Both of 0033's preconditions are met before anything is read: the knob is
**per-agent**, so a sweep does not silently compare an agent with itself, and
the range **bites** -- measured before this ran, non-damaging moves go from
0.0% of choices at scale 0 to 29.6% at the shipped 1.0 and 54.1% at scale 8.

**Nothing here is pre-registered, and no result from it should ship.** A sweep
across five settings sharing one baseline is exploratory: it says where to
point a confirmation, and 0029 is what happens when a lead from one is
published directly. If a scale leads, the confirmation runs separately on fresh
seeds with the claim fixed in advance.
"""

import math
import sys
from pathlib import Path

from champions_ai.agents import HeuristicAgent
from champions_ai.data import load_all
from champions_ai.data.harvest import harvested_pool
from champions_ai.data.split import split_replays
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_B
from champions_ai.env import BattleEnv
from champions_ai.evaluation import check_mirror
from champions_ai.evaluation.runner import evaluate, wilson_interval
from champions_ai.simulator import ShowdownBridge

BATTLES = int(sys.argv[1]) if len(sys.argv) > 1 else 800
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 4040
SCALES = (0.0, 0.5, 2.0, 4.0, 8.0)
POOL = Path("data/pool-eval.txt")


def main() -> None:
    corpus = load_all(Path("data/replays"))
    train = list(split_replays(list(corpus.replays)).train)

    with ShowdownBridge() as bridge:
        dex = Dex.cached(bridge, Path("data/dex.json"))
        env = BattleEnv(REGULATION_M_B, bridge=bridge)
        pool = harvested_pool(
            bridge, REGULATION_M_B.format_id, train, dex=dex, seed=1, cache=POOL
        )
        check_mirror(env, lambda: HeuristicAgent(dex, name="mirror"), pool, battles=60)
        print("harness sound: an agent tied every matchup against a copy of itself")
        print(f"frozen pool: {len(pool)} teams, {BATTLES} battles per scale, seed {SEED}")
        print("exploratory. A lead here is a place to point a confirmation.\n")

        print(f"  {'scale':<8} {'paired':>14} {'95% CI':>16} {'p':>8}  {'tied':>6}")
        for scale in SCALES:
            result = evaluate(
                env,
                HeuristicAgent(dex, name=f"status{scale:g}", status_scale=scale),
                HeuristicAgent(dex, name="shipped"),
                pool,
                battles=BATTLES,
                seed=SEED,
            )
            decided = result.decided_matchups
            if not decided:
                print(f"  {scale:<8} every matchup tied -- the knob changed nothing")
                continue
            ahead = result.matchups_won
            lo, hi = wilson_interval(ahead, decided)
            z = (ahead - decided / 2) / math.sqrt(decided * 0.25)
            p = math.erfc(abs(z) / math.sqrt(2))
            print(
                f"  {scale:<8} {ahead:>5}/{decided:<4} {result.paired_win_rate:>6.1%}"
                f"   {lo:>6.1%}-{hi:<6.1%} {p:>8.4f}  {result.matchups_tied:>6}"
            )


if __name__ == "__main__":
    main()
