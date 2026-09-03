"""How good is the guesser, and how good could any guesser be?

The null in 0039 has one obvious objection: the opponent model is simply bad,
so the experiment measured a bad guesser rather than the difficulty of
guessing. This measures the guesser directly -- no rollouts, just the guess
against what the opponent truly did -- and reports it against the two
reference points that bound it.

  a fixed default   always their first offered attack. What a model that
                    knows nothing scores, and the floor.
  repeat last move  they use whatever they used last turn. The cheapest
                    non-trivial model there is, and a real pattern in VGC.
  revealed-best     the guesser 0039 actually used.

Broken down by how much has been revealed about the Pokemon doing the acting,
because that is the thing a better model would have more of.
"""

import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from opponent_guess import guess_opponent_action  # noqa: E402

from champions_ai.agents import HeuristicAgent  # noqa: E402
from champions_ai.data import load_all  # noqa: E402
from champions_ai.data.harvest import harvested_pool  # noqa: E402
from champions_ai.data.split import split_replays  # noqa: E402
from champions_ai.dex import Dex  # noqa: E402
from champions_ai.domain import REGULATION_M_B, MoveAction  # noqa: E402
from champions_ai.env import BattleEnv  # noqa: E402
from champions_ai.env.battle_env import Decision  # noqa: E402
from champions_ai.evaluation import play_battle  # noqa: E402
from champions_ai.simulator import ShowdownBridge  # noqa: E402

BATTLES = int(sys.argv[1]) if len(sys.argv) > 1 else 150
MAX_STEP = 6


def seed_for(n):
    return "sodium," + f"{n:032x}"


def slot_move_names(observation):
    """Real move names per active slot, for the side that owns the observation."""
    names = {}
    for slot, team_index in enumerate(observation.own_side.active_slots):
        if team_index is not None:
            names[slot] = list(observation.own_side.team[team_index].selectable_moves)
    return names


def resolve(names, slot, action):
    if not isinstance(action, MoveAction):
        return None
    per_slot = names.get(slot)
    if per_slot is None or action.move_index >= len(per_slot):
        return None
    return per_slot[action.move_index]


def main():
    corpus = load_all(Path("data/replays"))
    train = list(split_replays(list(corpus.replays)).train)
    rng = random.Random(13579)

    exact = defaultdict(lambda: [0, 0])       # model -> [right, total] joint actions
    per_slot = defaultdict(lambda: [0, 0])    # model -> [right, total] slot moves
    by_revealed = defaultdict(lambda: [0, 0])  # revealed count -> slot moves
    by_turn = defaultdict(lambda: [0, 0])

    with ShowdownBridge() as bridge:
        dex = Dex.cached(bridge, Path("data/dex.json"))
        env = BattleEnv(REGULATION_M_B, bridge=bridge)
        pool = harvested_pool(
            bridge, REGULATION_M_B.format_id, train, dex=dex, seed=1,
            cache=Path("data/pool-eval.txt"),
        )

        def agents():
            return (HeuristicAgent(dex, name="a"), HeuristicAgent(dex, name="b"))

        for battle in range(BATTLES):
            first, second = rng.sample(range(len(pool)), 2)
            teams = (pool.teams[first], pool.teams[second])
            play_battle(env, agents(), teams, seed=seed_for(0xACC00000 + battle))
            trajectory = env.trajectory()

            steps = min(MAX_STEP, max(1, len(trajectory.decisions) // 2))
            for step in range(1, steps + 1):
                env.replay(trajectory, teams, stop_after=step)
                if env.terminal or env.awaiting() != (0, 1):
                    continue
                if env.decision(0) is not Decision.TURN:
                    continue

                observation = env.observation(0)
                their_observation = env.observation(1)
                legal = env.legal_actions(1)
                if not legal:
                    continue

                truth = agents()[1].select_action(their_observation, legal)
                names = slot_move_names(their_observation)

                models = {"revealed-best": guess_opponent_action(dex, env, observation)}
                # Floor: the first legal joint action that attacks at all.
                models["fixed default"] = next(
                    (j for j in legal if any(isinstance(a, MoveAction) for a in j.slot_actions)),
                    legal[0],
                )
                # Cheapest non-trivial model: they repeat what we watched them use.
                wanted = {}
                for slot, index in enumerate(observation.opponent_side.active_slots):
                    if index is None:
                        continue
                    last = observation.opponent_side.revealed[index].last_move
                    if last:
                        wanted[slot] = last
                best_repeat, best_hits = models["fixed default"], -1
                for joint in legal:
                    hits = sum(
                        1
                        for slot, name in wanted.items()
                        if slot < len(joint.slot_actions)
                        and resolve(names, slot, joint.slot_actions[slot]) == name
                    )
                    if hits > best_hits:
                        best_repeat, best_hits = joint, hits
                models["repeat last move"] = best_repeat

                for label, guess in models.items():
                    exact[label][1] += 1
                    exact[label][0] += guess == truth
                    for slot in range(len(truth.slot_actions)):
                        true_name = resolve(names, slot, truth.slot_actions[slot])
                        if true_name is None:
                            continue
                        got = resolve(names, slot, guess.slot_actions[slot]) == true_name
                        per_slot[label][1] += 1
                        per_slot[label][0] += got
                        if label == "revealed-best":
                            index = observation.opponent_side.active_slots[slot]
                            count = (
                                len(observation.opponent_side.revealed[index].revealed_moves)
                                if index is not None
                                else 0
                            )
                            bucket = "4+" if count >= 4 else str(count)
                            by_revealed[bucket][1] += 1
                            by_revealed[bucket][0] += got
                            by_turn[min(observation.turn, 6)][1] += 1
                            by_turn[min(observation.turn, 6)][0] += got

    print(f"{exact['revealed-best'][1]} decision points\n")
    print(f"  {'opponent model':<22} {'whole turn right':>17} {'per slot right':>16}")
    for label in ("fixed default", "repeat last move", "revealed-best"):
        right, total = exact[label]
        sright, stotal = per_slot[label]
        print(f"  {label:<22} {right / total:>16.1%} {sright / stotal:>16.1%}")

    print("\n  revealed-best, by how many of their moves we have seen:")
    print(f"    {'moves seen':<14} {'slots':>7} {'right':>8}")
    for bucket in sorted(by_revealed, key=lambda b: (b == "4+", b)):
        right, total = by_revealed[bucket]
        print(f"    {bucket:<14} {total:>7} {right / total:>7.1%}")

    print("\n  revealed-best, by turn:")
    print(f"    {'turn':<14} {'slots':>7} {'right':>8}")
    for turn in sorted(by_turn):
        right, total = by_turn[turn]
        print(f"    {turn:<14} {total:>7} {right / total:>7.1%}")


if __name__ == "__main__":
    main()
