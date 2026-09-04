"""Turn `evaluate_position` into a baseline REINFORCE can subtract.

0043 gave every decision in a battle the same advantage: `R - b`, where `b` was
a running mean over episodes. That is the highest-variance credit assignment
available. A turn played while comfortably ahead and a turn played while nearly
dead both received the same credit for the same eventual win, so most of the
gradient was the outcome rather than the choice.

A state-dependent baseline fixes that, and this project already owns one.
`evaluate_position` predicts the winner from a position at about 63% (0035),
costs nothing to call, and is not learned -- so it cannot co-adapt with the
policy the way a trained critic can.

It returns a *score*, though, and REINFORCE needs an expected *reward*. This
fits the mapping.

    V(s) = 2 * sigmoid(a * advantage + b) - 1

`a` and `b` are fitted on self-play mirror battles, which is the distribution
training actually samples -- not on human replays, where 0035 measured a
different population and where the teams are not the pool's.

**Whether it helps at all is checked here rather than assumed.** A baseline
only reduces variance if it tracks the outcome; a flat one subtracts a constant
and changes nothing. The report prints accuracy and Brier score against the
constant baseline it replaces, so a useless critic is visible before it is
wired into anything.
"""

import json
import math
import random
import statistics
import sys
from pathlib import Path

from champions_ai.agents import HeuristicAgent
from champions_ai.data import TeamPool, load_all
from champions_ai.data.harvest import harvested_pool
from champions_ai.data.split import split_replays
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_B
from champions_ai.env import BattleEnv
from champions_ai.env.battle_env import Decision
from champions_ai.mechanics import evaluate_position
from champions_ai.simulator import ShowdownBridge

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("critic.json")
BATTLES = int(sys.argv[2]) if len(sys.argv) > 2 else 300
HOLDOUT = 50


def sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))


def fit(samples, steps=400, rate=0.5):
    """Logistic on one feature. Standardised so one learning rate works."""
    values = [x for x, _ in samples]
    mean = statistics.fmean(values)
    spread = statistics.pstdev(values) or 1.0
    a, b = 0.0, 0.0
    for _ in range(steps):
        ga = gb = 0.0
        for x, y in samples:
            z = a * ((x - mean) / spread) + b
            error = sigmoid(z) - y
            ga += error * ((x - mean) / spread)
            gb += error
        a -= rate * ga / len(samples)
        b -= rate * gb / len(samples)
    return a, b, mean, spread


def main() -> None:
    corpus = load_all(Path("data/replays"))
    train_replays = list(split_replays(list(corpus.replays)).train)
    rng = random.Random(717)

    with ShowdownBridge() as bridge:
        dex = Dex.cached(bridge, Path("data/dex.json"))
        env = BattleEnv(REGULATION_M_B, bridge=bridge)
        pool = harvested_pool(
            bridge, REGULATION_M_B.format_id, train_replays, dex=dex, seed=1,
            cache=Path("data/pool-eval.txt"),
        )
        training_pool = TeamPool(pool.teams[:-HOLDOUT])

        samples = []
        print(f"  collecting from {BATTLES} mirror battles on training teams", flush=True)
        for battle in range(BATTLES):
            pick = rng.randrange(len(training_pool))
            teams = (training_pool.teams[pick], training_pool.teams[pick])
            agents = (HeuristicAgent(dex), HeuristicAgent(dex))
            for agent in agents:
                agent.on_battle_start()
            result = env.reset(teams, seed="sodium," + f"{rng.getrandbits(128):032x}")
            seen = []
            while not result.terminal:
                waiting = env.awaiting()
                if not waiting:
                    break
                choices = {}
                for player in waiting:
                    if env.decision(player) is Decision.TEAM_PREVIEW:
                        choices[player] = agents[player].select_team_preview(
                            env.team_preview(player), REGULATION_M_B.picked_team_size
                        )
                        continue
                    observation = env.observation(player)
                    choices[player] = agents[player].select_action(
                        observation, env.legal_actions(player)
                    )
                    if player == 0:
                        try:
                            seen.append(evaluate_position(observation).advantage)
                        except RuntimeError:
                            pass
                result = env.step(choices)
            won = 1 if result.winner == 0 else 0
            samples.extend((value, won) for value in seen)
            if (battle + 1) % 100 == 0:
                print(f"    {battle + 1} battles, {len(samples)} positions", flush=True)

        rng.shuffle(samples)
        cut = len(samples) // 3
        test, train = samples[:cut], samples[cut:]
        a, b, mean, spread = fit(train)

        def predict(x):
            return sigmoid(a * ((x - mean) / spread) + b)

        base = statistics.fmean(y for _, y in train)
        accuracy = sum((predict(x) > 0.5) == (y == 1) for x, y in test) / len(test)
        brier = statistics.fmean((predict(x) - y) ** 2 for x, y in test)
        flat = statistics.fmean((base - y) ** 2 for x, y in test)

        print(f"\n  {len(samples)} positions, held out {len(test)}")
        print(f"    accuracy            {accuracy:.1%}   (0035 measured ~63% on human games)")
        print(f"    Brier, fitted       {brier:.4f}")
        print(f"    Brier, flat baseline{flat:>8.4f}   <- what 0043 used")
        gain = (flat - brier) / flat if flat else 0.0
        print(f"    variance explained  {gain:.1%}")
        print()
        print("  P(win) by position score, held out:")
        ordered = sorted(test)
        step = max(1, len(ordered) // 6)
        for i in range(0, len(ordered), step):
            chunk = ordered[i:i + step]
            if len(chunk) < 20:
                continue
            print(f"    score {chunk[0][0]:>7.0f} to {chunk[-1][0]:<7.0f}"
                  f"  actual {statistics.fmean(y for _, y in chunk):>5.1%}"
                  f"  predicted {statistics.fmean(predict(x) for x, _ in chunk):>5.1%}")

        OUT.write_text(
            json.dumps({"a": a, "b": b, "mean": mean, "spread": spread,
                        "accuracy": accuracy, "brier": brier, "flat_brier": flat},
                       indent=2),
            encoding="utf-8",
        )
        print(f"\n  written to {OUT}")
        if gain < 0.02:
            print("  WARNING: this baseline explains almost nothing and will not "
                  "reduce variance.")


if __name__ == "__main__":
    main()
