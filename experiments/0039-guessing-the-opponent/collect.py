"""Does the search still win when it has to guess the opponent's move?

0038 confirmed +1.4 points for a one-ply search -- but that search was handed
the opponent's *true* simultaneous choice, computed from their full
information. A real search cannot do that: both players choose blind to each
other. This repeats the measurement with the opponent's move replaced by
`guess_opponent_action`, built from only what player 0 can see about them.

Two different opponent actions are used, deliberately, for two different
purposes:

  guessed_opponent   informs the SEARCH's ranking only. Each candidate is
                      forked with {our candidate, their guessed move} and the
                      successor is scored. This is what a real search would
                      compute before submitting.

  true_opponent       what actually happens. Grading a chosen action's real
                      win rate has to use the opponent's real move, or the
                      number would not describe the real game.

This separation also removes 0038's selection-bias problem for free: the
ranking never sees any rollout that shares a seed or an opponent action with
the rollouts used to grade it, so no odd/even split is needed here.

**Pre-registered before this runs.** One claim:

    on the true continuation, the action chosen by guessed-opponent search
    beats the agent's own pick -- paired sign test over decision points where
    the two choices differ, p < 0.05

A guessed-opponent search that fails this is not "no better than the agent" in
the way a coin flip is -- it would mean the +1.4 points measured in 0038 came
entirely from knowing the opponent's move, which a deployed search never has.
"""

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from opponent_guess import guess_opponent_action  # noqa: E402

from champions_ai.agents import HeuristicAgent  # noqa: E402
from champions_ai.agents.heuristic import _combined_targets  # noqa: E402
from champions_ai.data import load_all  # noqa: E402
from champions_ai.data.harvest import harvested_pool  # noqa: E402
from champions_ai.data.split import split_replays  # noqa: E402
from champions_ai.dex import Dex  # noqa: E402
from champions_ai.domain import REGULATION_M_B  # noqa: E402
from champions_ai.env import BattleEnv  # noqa: E402
from champions_ai.env.battle_env import Decision  # noqa: E402
from champions_ai.evaluation import play_battle, play_out  # noqa: E402
from champions_ai.mechanics import evaluate_position  # noqa: E402
from champions_ai.simulator import ShowdownBridge  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("ranking3.json")
BATTLES = int(sys.argv[2]) if len(sys.argv) > 2 else 200
IMAGINE = int(sys.argv[3]) if len(sys.argv) > 3 else 8
GRADE = int(sys.argv[4]) if len(sys.argv) > 4 else 24
CANDIDATES = 4
MAX_STEP = 6
POINTS_PER_BATTLE = 2

BATTLE_SEED_BASE = 0x5EED0000
IMAGINE_SEED_BASE = 0x1A0000
GRADE_SEED_BASE = 0x6A0000
CONTROL_SEED_BASE = 0x7A0000

# A guaranteed win or loss the imagination branch cannot evaluate a position
# for (the battle ended). Larger in magnitude than any real evaluate_position
# score seen in 0035-0038, so it never loses a comparison to a real value.
TERMINAL_WIN = 1000.0
TERMINAL_LOSS = -1000.0


def seed_for(n):
    return "sodium," + f"{n:032x}"


def joint_score(agent, observation, joint):
    scored = [
        agent.score_slot_action(observation, slot, slot_action)
        for slot, slot_action in enumerate(joint.slot_actions)
    ]
    return sum(s.score for s in scored) + _combined_targets(scored)


def rollout_win_rate(env, teams, trajectory, step, our_action, their_action, seeds, agents):
    wins = 0
    for seed in seeds:
        env.replay(trajectory, teams, stop_after=step)
        env.reseed(seed)
        result = env.step({0: our_action, 1: their_action})
        if not result.terminal:
            result = play_out(env, agents())
        if result.winner == 0:
            wins += 1
    return wins / len(seeds)


def main():
    corpus = load_all(Path("data/replays"))
    train = list(split_replays(list(corpus.replays)).train)
    rng = random.Random(24601)
    rows = []

    with ShowdownBridge() as bridge:
        dex = Dex.cached(bridge, Path("data/dex.json"))
        env = BattleEnv(REGULATION_M_B, bridge=bridge)
        pool = harvested_pool(
            bridge,
            REGULATION_M_B.format_id,
            train,
            dex=dex,
            seed=1,
            cache=Path("data/pool-eval.txt"),
        )

        def agents():
            return (HeuristicAgent(dex, name="a"), HeuristicAgent(dex, name="b"))

        print(f"pool: {len(pool)} teams, {BATTLES} battles, "
              f"{IMAGINE} imagine seeds, {GRADE} grade seeds")
        print("pre-registered: on the true continuation, guessed-opponent search")
        print("beats the agent's own pick, paired sign test, p < 0.05\n", flush=True)

        for battle in range(BATTLES):
            first, second = rng.sample(range(len(pool)), 2)
            teams = (pool.teams[first], pool.teams[second])

            play_battle(env, agents(), teams, seed=seed_for(BATTLE_SEED_BASE + battle))
            trajectory = env.trajectory()

            steps = min(MAX_STEP, max(1, len(trajectory.decisions) // 2))
            for step in rng.sample(range(1, steps + 1), min(POINTS_PER_BATTLE, steps)):
                env.replay(trajectory, teams, stop_after=step)
                if env.terminal or env.awaiting() != (0, 1):
                    continue
                if env.decision(0) is not Decision.TURN:
                    continue

                observation = env.observation(0)
                legal = env.legal_actions(0)
                if len(legal) < 2:
                    continue

                probe = agents()
                best = probe[0].select_action(observation, legal)
                others = [a for a in legal if a != best]
                rng.shuffle(others)
                candidates = [best] + others[: CANDIDATES - 1]

                guessed_opponent = guess_opponent_action(dex, env, observation)
                true_opponent = probe[1].select_action(env.observation(1), env.legal_actions(1))

                base = battle * 100000 + step * 1000
                imagine_seeds = [seed_for(IMAGINE_SEED_BASE + base + i) for i in range(IMAGINE)]

                imagined = []
                for candidate in candidates:
                    values = []
                    for seed in imagine_seeds:
                        env.replay(trajectory, teams, stop_after=step)
                        env.reseed(seed)
                        result = env.step({0: candidate, 1: guessed_opponent})
                        if result.terminal:
                            values.append(TERMINAL_WIN if result.winner == 0 else TERMINAL_LOSS)
                        else:
                            values.append(evaluate_position(env.observation(0)).advantage)
                    imagined.append(sum(values) / len(values))

                search_index = max(range(len(candidates)), key=lambda i: imagined[i])
                search_choice = candidates[search_index]

                grade_seeds = [seed_for(GRADE_SEED_BASE + base + i) for i in range(GRADE)]
                agent_rate = rollout_win_rate(
                    env, teams, trajectory, step, best, true_opponent, grade_seeds, agents
                )
                if search_choice == best:
                    search_rate = agent_rate
                else:
                    search_rate = rollout_win_rate(
                        env, teams, trajectory, step, search_choice, true_opponent,
                        grade_seeds, agents,
                    )

                control_seeds = [seed_for(CONTROL_SEED_BASE + base + i) for i in range(GRADE)]
                control_rate = rollout_win_rate(
                    env, teams, trajectory, step, best, true_opponent, control_seeds, agents
                )

                rows.append(
                    {
                        "battle": battle,
                        "step": step,
                        "turn": observation.turn,
                        "legal": len(legal),
                        "search_picked_the_same_action": search_choice == best,
                        "agent_rate": agent_rate,
                        "search_rate": search_rate,
                        "control_rate": control_rate,
                        "imagined": imagined,
                        "action_scores": [
                            joint_score(probe[0], observation, c) for c in candidates
                        ],
                    }
                )
                print(
                    f"  battle {battle:>3} step {step} turn {observation.turn:>2}"
                    f"  same={search_choice == best!s:<5}"
                    f"  agent {agent_rate:5.1%}  search {search_rate:5.1%}"
                    f"  ({len(rows)} points)",
                    flush=True,
                )

    OUT.write_text(json.dumps(rows), encoding="utf-8")
    print(f"\n{len(rows)} decision points written to {OUT}")


if __name__ == "__main__":
    main()
