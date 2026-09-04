"""Can a policy trained on winning beat the hand-written heuristic?

Milestone 8, at the smallest size that can answer the question. 0006 built a
policy on these same 26 features and trained it to imitate rated humans: it
gained 4.2 points of agreement and lost 520-1080, because it learned to decline
a guaranteed knockout one time in four. Its own conclusion was that a learned
policy needs a signal tied to *winning*. This is that signal.

**Why linear, and why no new dependency.** If a policy warm-started at the
heuristic and handed a winning signal cannot improve on it, a deeper one
probably cannot either, and this costs an afternoon instead of a month. The
project's rule is baselines before deep learning, and torch is a decision to
take on evidence rather than in advance.

**The warm start is the whole reason this is worth running.** `heuristic_score`
is one of the features, so a weight vector concentrated on it reproduces the
heuristic's ranking. Measured before writing this: greedy, that policy plays the
shipped heuristic to 48.4% paired over 400 battles (CI 38.6%-58.3%). So
training starts *at* the bar rather than at 0006's 32.5%, and any gain is a gain
over an agent that took forty experiments to tune.

Greedy argmax is scale-invariant, so the warm-start weight does not change where
training starts -- it sets how much the policy explores while sampling. Measured
across 102 real decisions with a mean of 63 legal joint actions: at weight 1 a
sample picks the heuristic's own choice 27% of the time, at 5 it is 59%, at 10
it is 70%, at 20 it is 79%.

**Held out by team.** The frozen 200-team pool is split, and the policy never
trains on the teams it is judged on. Overfitting to a fixed pool is the obvious
way for this to produce a number that means nothing.

**Trained on mirror matchups.** 0031 measured team assignment at 93% of outcome
variance, so an episode between two different teams yields a reward that mostly
reports which team was luckier -- a gradient made almost entirely of noise. The
same team on both sides removes that term and leaves a signal about play.
Evaluation is unaffected: it uses the normal paired protocol with teams
exchanged, on teams never trained on.

**The opponent is the frozen heuristic, not self-play.** 0026 established that
self-play cannot surface a mechanic the agent under-uses, and the question here
is specifically "does this beat the heuristic". The cost is that the policy may
learn to exploit that one opponent rather than to play well, which is recorded
as a limitation rather than solved.
"""

import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from policy import (
    JOINT_FEATURE_NAMES,
    JointFeatures,
    JointPolicyAgent,
    warm_start_weights,
)

from champions_ai.agents import HeuristicAgent
from champions_ai.data import TeamPool, load_all
from champions_ai.data.harvest import harvested_pool
from champions_ai.data.reconstruct import move_data_from_dex
from champions_ai.data.split import split_replays
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_B
from champions_ai.env import BattleEnv
from champions_ai.env.battle_env import Decision
from champions_ai.evaluation.runner import evaluate, wilson_interval
from champions_ai.simulator import ShowdownBridge

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("policy.json")
BATCHES = int(sys.argv[2]) if len(sys.argv) > 2 else 60
BATCH = int(sys.argv[3]) if len(sys.argv) > 3 else 40
# Swept rather than sampled. 0032 is the reason: switching was called a null
# three times by three experiments that each tried one setting, and the answer
# changed sign the moment somebody swept it.
LEARNING_RATE = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5

WARM_START = 10.0        # 70% agreement with the heuristic's pick when sampling
EVAL_BATTLES = 400
EVAL_EVERY = 15
HOLDOUT = 50             # teams reserved for judging, never trained on


def softmax(logits):
    top = max(logits)
    exponentiated = [math.exp(v - top) for v in logits]
    total = sum(exponentiated)
    return [v / total for v in exponentiated]


def play_episode(env, weights, features, opponent, teams, seed, rng):
    """One battle, sampling our side. Returns (steps, reward).

    A step is (chosen feature vector, every candidate's vector, their
    probabilities) -- everything the gradient needs and nothing else.
    """
    steps = []
    opponent.on_battle_start()
    result = env.reset(teams, seed=seed)

    while not result.terminal:
        waiting = env.awaiting()
        if not waiting:
            break
        choices = {}
        for player in waiting:
            if player == 1:
                if env.decision(1) is Decision.TEAM_PREVIEW:
                    choices[1] = opponent.select_team_preview(
                        env.team_preview(1), REGULATION_M_B.picked_team_size
                    )
                else:
                    choices[1] = opponent.select_action(
                        env.observation(1), env.legal_actions(1)
                    )
                continue

            if env.decision(0) is Decision.TEAM_PREVIEW:
                # Team preview is a different decision with its own action
                # space; the heuristic makes it for both sides so that this
                # measures turn play alone.
                choices[0] = opponent.select_team_preview(
                    env.team_preview(0), REGULATION_M_B.picked_team_size
                )
                continue

            observation = env.observation(0)
            legal = env.legal_actions(0)
            if len(legal) == 1:
                choices[0] = legal[0]
                continue
            vectors = features.batch(observation, legal)
            probabilities = softmax(
                [sum(w * f for w, f in zip(weights, v, strict=True)) for v in vectors]
            )
            index = rng.choices(range(len(legal)), weights=probabilities, k=1)[0]
            choices[0] = legal[index]
            steps.append((vectors[index], vectors, probabilities))

        result = env.step(choices)

    reward = 1.0 if result.winner == 0 else -1.0
    return steps, reward


def main() -> None:
    corpus = load_all(Path("data/replays"))
    train_replays = list(split_replays(list(corpus.replays)).train)
    rng = random.Random(4343)

    with ShowdownBridge() as bridge:
        dex = Dex.cached(bridge, Path("data/dex.json"))
        features = JointFeatures(dex, move_data_from_dex(dex))
        env = BattleEnv(REGULATION_M_B, bridge=bridge)
        pool = harvested_pool(
            bridge, REGULATION_M_B.format_id, train_replays, dex=dex, seed=1,
            cache=Path("data/pool-eval.txt"),
        )
        training_pool = TeamPool(pool.teams[:-HOLDOUT])
        holdout_pool = TeamPool(pool.teams[-HOLDOUT:])

        weights = warm_start_weights(WARM_START)
        opponent = HeuristicAgent(dex, name="frozen")

        def judge(label):
            agent = JointPolicyAgent(weights, features, name="policy")
            result = evaluate(
                env, agent, HeuristicAgent(dex, name="shipped"), holdout_pool,
                battles=EVAL_BATTLES, seed=7,
            )
            decided = result.decided_matchups
            lo, hi = wilson_interval(result.matchups_won, decided) if decided else (0.0, 0.0)
            print(
                f"  [{label}] held-out paired {result.matchups_won}/{decided}"
                f" = {result.paired_win_rate:.1%}  CI {lo:.1%}-{hi:.1%}"
                f"  raw {result.win_rate_a:.1%}",
                flush=True,
            )
            return result.paired_win_rate

        print(f"{len(training_pool)} teams to train on, {len(holdout_pool)} held out")
        print(f"warm start: heuristic_score = {WARM_START}, lr {LEARNING_RATE},"
              f" {BATCHES} batches of {BATCH}\n", flush=True)
        judge("warm start")

        baseline = 0.0
        history = []
        for batch in range(1, BATCHES + 1):
            gradient = [0.0] * len(JOINT_FEATURE_NAMES)
            rewards = []
            total_steps = 0
            for episode in range(BATCH):
                # **Mirror matchups.** 0031 measured that team assignment
                # accounts for 93% of outcome variance, so a reward from two
                # different teams mostly reports which team was luckier. The
                # same team on both sides removes that entirely and leaves a
                # reward about play, which is the only thing the gradient can
                # act on. Evaluation still uses the normal paired protocol with
                # teams exchanged, so this does not leak into the result.
                pick = rng.randrange(len(training_pool))
                teams = (training_pool.teams[pick], training_pool.teams[pick])
                seed = "sodium," + f"{rng.getrandbits(128):032x}"
                steps, reward = play_episode(
                    env, weights, features, opponent, teams, seed, rng
                )
                rewards.append(reward)
                advantage = reward - baseline
                total_steps += len(steps)
                for chosen, vectors, probabilities in steps:
                    # d/dw log pi(a) = phi(a) - sum_b pi(b) phi(b)
                    for i in range(len(gradient)):
                        expected = sum(
                            p * v[i] for p, v in zip(probabilities, vectors, strict=True)
                        )
                        gradient[i] += advantage * (chosen[i] - expected)

            mean_reward = sum(rewards) / len(rewards)
            baseline = 0.9 * baseline + 0.1 * mean_reward
            # Per decision, not per episode and not per episode squared. The
            # gradient was summed over every step in the batch, so the mean
            # gradient is what the learning rate should multiply.
            scale = LEARNING_RATE / max(1, total_steps)
            for i in range(len(weights)):
                weights[i] += scale * gradient[i]

            history.append({"batch": batch, "win_rate": (mean_reward + 1) / 2})
            print(
                f"  batch {batch:>3}  sampled win rate {(mean_reward + 1) / 2:>6.1%}"
                f"  baseline {(baseline + 1) / 2:>6.1%}  {total_steps} decisions",
                flush=True,
            )
            if batch % EVAL_EVERY == 0:
                judge(f"batch {batch}")

        final = judge("final")
        OUT.write_text(
            json.dumps(
                {
                    "weights": dict(zip(JOINT_FEATURE_NAMES, weights, strict=True)),
                    "held_out_paired": final,
                    "history": history,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nwritten to {OUT}")
        print("\n  weights that moved most from the warm start:")
        # Movement from the warm start, not absolute size. Sorting by |w| put
        # `combined_targets` at the top of every run at +10.00 -- which is
        # exactly where the warm start left it, and therefore the one feature
        # that had not moved at all.
        start = warm_start_weights(WARM_START)
        moved = sorted(
            (
                (abs(w - s), n, w)
                for n, w, s in zip(JOINT_FEATURE_NAMES, weights, start, strict=True)
                if n != "heuristic_score"
            ),
            reverse=True,
        )
        for _, name, value in moved[:8]:
            print(f"    {name:<26} {value:>+8.3f}")


if __name__ == "__main__":
    main()
