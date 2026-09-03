"""Confirmation run: select on one half of the rollouts, score on the other.

The first run put one-ply search at +2.9 points of win rate over the shipped
action score. That number has a bias in it. The search picks the candidate with
the highest mean successor evaluation, and that evaluation is computed from the
*same* rollouts whose outcomes give the win rate -- so a candidate that got
lucky in its rollouts is both more likely to be picked and more likely to look
good. Selecting and scoring on one sample is how 0029 got published and
retracted.

This run fixes it by saving the rollouts individually. The analysis then splits
them: odd-numbered rollouts choose the action, even-numbered ones say what it
was worth. The choice can no longer be contaminated by the outcomes it is
graded against.

**Pre-registered, before this runs.** One claim:

    on held-out rollouts, the action chosen by successor evaluation beats the
    action the agent actually picked -- paired sign test over decision points,
    p < 0.05

If it does not clear that, the +2.9 was selection bias and one-ply search is
closed on the same terms redirection and speed control were. No third attempt
and no re-picking a different ranker afterwards.

The noise control is dropped: the first run already measured it at a 9.0 point
standard deviation for the same action rolled twice, and dropping it buys a
fifth of the runtime back.
"""

import json
import random
import sys
from pathlib import Path

from champions_ai.agents import HeuristicAgent
from champions_ai.agents.heuristic import _combined_targets
from champions_ai.data import load_all
from champions_ai.data.harvest import harvested_pool
from champions_ai.data.split import split_replays
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_B
from champions_ai.env import BattleEnv
from champions_ai.env.battle_env import Decision
from champions_ai.evaluation import play_battle, play_out
from champions_ai.mechanics import evaluate_position
from champions_ai.simulator import ShowdownBridge

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("ranking2.json")
BATTLES = int(sys.argv[2]) if len(sys.argv) > 2 else 220
ROLLOUTS = int(sys.argv[3]) if len(sys.argv) > 3 else 24
CANDIDATES = 4
MAX_STEP = 6
POINTS_PER_BATTLE = 2

# Fresh seeds. The first run used 0x5EED0000 and 0xB0000; reusing them would
# re-measure the same battles and the same luck, which is not a confirmation.
BATTLE_SEED_BASE = 0x0C0FFEE0
BRANCH_SEED_BASE = 0x0A5E0000


def seed_for(n):
    return "sodium," + f"{n:032x}"


def joint_score(agent, observation, joint):
    scored = [
        agent.score_slot_action(observation, slot, slot_action)
        for slot, slot_action in enumerate(joint.slot_actions)
    ]
    return sum(s.score for s in scored) + _combined_targets(scored)


def main():
    corpus = load_all(Path("data/replays"))
    train = list(split_replays(list(corpus.replays)).train)
    rng = random.Random(97531)
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

        print(f"pool: {len(pool)} teams, {BATTLES} battles, {ROLLOUTS} rollouts each")
        print("pre-registered: on held-out rollouts, successor evaluation beats")
        print("the agent's own pick, paired sign test, p < 0.05\n", flush=True)

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
                opponent = probe[1].select_action(env.observation(1), env.legal_actions(1))

                base = BRANCH_SEED_BASE + battle * 100000 + step * 1000
                branches = [seed_for(base + i) for i in range(ROLLOUTS)]

                measured = []
                for candidate in candidates:
                    # Per rollout, so selection and scoring can be split later.
                    won, evals = [], []
                    for branch in branches:
                        env.replay(trajectory, teams, stop_after=step)
                        env.reseed(branch)
                        result = env.step({0: candidate, 1: opponent})
                        if result.terminal:
                            evals.append(None)
                        else:
                            evals.append(evaluate_position(env.observation(0)).advantage)
                            result = play_out(env, agents())
                        won.append(1 if result.winner == 0 else 0)
                    measured.append(
                        {
                            "won": won,
                            "evals": evals,
                            "action_score": joint_score(probe[0], observation, candidate),
                        }
                    )

                rows.append(
                    {
                        "battle": battle,
                        "step": step,
                        "turn": observation.turn,
                        "legal": len(legal),
                        "candidates": measured,
                    }
                )
                rates = [sum(c["won"]) / len(c["won"]) for c in measured]
                print(
                    f"  battle {battle:>3} step {step} turn {observation.turn:>2}"
                    f"  spread {max(rates) - min(rates):5.1%}"
                    f"  picked {rates[0]:5.1%}"
                    f"  ({len(rows)} points)",
                    flush=True,
                )

    OUT.write_text(json.dumps(rows), encoding="utf-8")
    print(f"\n{len(rows)} decision points written to {OUT}")


if __name__ == "__main__":
    main()
