"""Can the evaluator *rank* the actions available at one decision point?

0035 and 0037 measured a different task: name the eventual winner from a
position. They agree it saturates near 63% and that `evaluate_position` is
already there. A search does not need that. It needs a local ordering -- is
what follows action A better than what follows action B -- and an evaluator can
be mediocre at the absolute question while being fine at the relative one.
Nobody has checked, and it is the only route by which Milestone 11 reopens.

Ground truth comes from the engine rather than from a corpus. At a decision
point the battle is forked once per candidate action, the action is applied,
and the rest is rolled out repeatedly with the heuristic on both sides. The
win rate over those rollouts is what the action was actually worth.

Two questions, in this order, because the second is worth nothing if the first
comes back small:

  1. **How much does one decision matter?** The spread between the best and
     worst legal action, in win rate. This is the ceiling on *any* ranker,
     ours or a perfect one, and it prices Milestone 11 the way 0018 priced
     opponent knowledge and 0035 priced the value model. If choosing the worst
     available action costs three points, search cannot be worth building
     however well it ranks.

  2. **Who ranks better** -- the position evaluator applied to the successor,
     which is what a one-ply search does, or the heuristic's own action score,
     which is what we ship. If the thing search would use is no better than
     the thing we already have, search has nothing to offer even where the
     decision matters.

**Pre-registered before running.** One claim, on the paired sign test over
candidate pairs whose true win rates differ by at least 15 points:

    the successor evaluator ranks those pairs more accurately than the
    shipped action score, p < 0.05

15 points because with 24 rollouts a win rate carries about 10 points of
standard error, so a smaller gap is mostly noise about which action was really
better. Everything else here is descriptive and is reported as such.

**Common random numbers.** Every candidate at a decision point is rolled out
against the same list of branch seeds, so the comparison between candidates is
paired. Different actions consume the RNG differently, so this is variance
reduction rather than perfect pairing -- the same caveat the battle harness
carries.

**A noise control, because the headline statistic needs one.** A win rate over
24 rollouts carries about 10 points of standard error, so the largest minus the
smallest of four of them is a few tens of points wide *even when all four
actions are identical*. Reporting a raw spread as "how much the decision
matters" would therefore be measuring the sample size. So every decision point
also rolls out the agent's own chosen action a second time against a disjoint
set of branch seeds. That pair differs by construction only by luck, and the
distribution of those differences is what a real difference has to beat.

**Two readings of the successor**, because they are different searches. A
naive one steps the engine once and evaluates what it sees, which is one
sample of a stochastic transition. A proper one evaluates the *expected*
successor. Both are recorded: `eval_one` is the first rollout's successor,
`eval_mean` the average over all of them.
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

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("ranking.json")
BATTLES = int(sys.argv[2]) if len(sys.argv) > 2 else 40
ROLLOUTS = int(sys.argv[3]) if len(sys.argv) > 3 else 24
CANDIDATES = 4

# Fork inside the first few turns: prefixes stay short, and it is where 0035
# found prediction weakest (54.8% on turns 1-2) and so where a search would
# have to earn its keep.
MAX_STEP = 6
POINTS_PER_BATTLE = 2


def seed_for(n):
    return "sodium," + f"{n:032x}"


def joint_score(agent, observation, joint):
    """The number `select_action` maximises, for one joint action."""
    scored = [
        agent.score_slot_action(observation, slot, slot_action)
        for slot, slot_action in enumerate(joint.slot_actions)
    ]
    return sum(s.score for s in scored) + _combined_targets(scored)


def main():
    corpus = load_all(Path("data/replays"))
    train = list(split_replays(list(corpus.replays)).train)
    rng = random.Random(4242)
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

        print(f"pool: {len(pool)} teams, {BATTLES} battles, {ROLLOUTS} rollouts", flush=True)

        for battle in range(BATTLES):
            first, second = rng.sample(range(len(pool)), 2)
            teams = (pool.teams[first], pool.teams[second])

            play_battle(env, agents(), teams, seed=seed_for(0x5EED0000 + battle))
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

                # The opponent chooses before the dice are rolled, so its
                # action is the same for every branch and every candidate.
                opponent = probe[1].select_action(env.observation(1), env.legal_actions(1))

                base = 0xB0000 + battle * 100000 + step * 1000
                branches = [seed_for(base + i) for i in range(ROLLOUTS)]
                # Disjoint seeds, same action: a difference that is luck alone.
                control_branches = [seed_for(base + 500 + i) for i in range(ROLLOUTS)]

                def measure(candidate, seeds):
                    wins, evals = 0, []
                    for branch in seeds:
                        env.replay(trajectory, teams, stop_after=step)
                        env.reseed(branch)
                        result = env.step({0: candidate, 1: opponent})
                        if result.terminal:
                            # Keep the lists aligned. Appending only on the
                            # non-terminal branch made `evals[0]` the first
                            # *surviving* rollout rather than rollout 0, so
                            # `eval_one` could describe a different branch than
                            # the one it was paired with. 0.36% of rollouts.
                            evals.append(None)
                        else:
                            evals.append(evaluate_position(env.observation(0)).advantage)
                            result = play_out(env, agents())
                        if result.winner == 0:
                            wins += 1
                    live = [e for e in evals if e is not None]
                    return {
                        "win_rate": wins / len(seeds),
                        # None means the branch ended in the step itself, so
                        # there was no position left to score.
                        "eval_one": evals[0] if evals and evals[0] is not None else 0.0,
                        "eval_mean": sum(live) / len(live) if live else 0.0,
                        "action_score": joint_score(probe[0], observation, candidate),
                        "is_heuristic_pick": candidate == best,
                    }

                measured = [measure(c, branches) for c in candidates]
                control = measure(best, control_branches)

                rates = [c["win_rate"] for c in measured]
                rows.append(
                    {
                        "battle": battle,
                        "step": step,
                        "turn": observation.turn,
                        "legal": len(legal),
                        "candidates": measured,
                        "control": control,
                    }
                )
                print(
                    f"  battle {battle:>3} step {step} turn {observation.turn:>2}"
                    f"  spread {max(rates) - min(rates):5.1%}"
                    f"  noise {abs(control['win_rate'] - measured[0]['win_rate']):5.1%}"
                    f"  picked {measured[0]['win_rate']:5.1%}"
                    f"  ({len(rows)} points)",
                    flush=True,
                )

    OUT.write_text(json.dumps(rows), encoding="utf-8")
    print(f"\n{len(rows)} decision points written to {OUT}")


if __name__ == "__main__":
    main()
