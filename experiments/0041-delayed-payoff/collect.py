"""Does a one-turn scorer underprice a move that pays off later?

0040 swept how far the status scorer is trusted and found the shipped weight at
the top of a clean inverted U -- then found the gap it was built to close does
not exist. Humans play non-damaging moves on 34.2% of move choices and this
agent on 29.6%, so the category is used about equally. The disagreement is over
*which* one and *when*, which a single scalar cannot touch.

The leading explanation for that, and the one 0040 left untested, is
structural: **the scorer prices one turn, and half the category pays off over
several.** Reflect lasts five turns. Will-O-Wisp halves physical damage for the
rest of the battle. Calm Mind is worth nothing on the turn it is used. Scaling a
price that cannot see the payoff amplifies a number rather than correcting it.

That is a hypothesis, and this project has twice named a "largest gap" that was
really a ceiling (0013, 0018), so it gets measured before anything is built.

**The method is 0038's fork, pointed at one slot.** At a decision point the
battle is forked once per candidate and each is rolled out to the end, which
prices an action by what it is actually worth rather than by what the scorer
thinks. Candidates differ in **exactly one slot**, with the other held at the
agent's own choice, so the difference between two rollouts is attributable to
one move rather than to a pair of them.

For each candidate the regret is `true win rate of the candidate` minus `true
win rate of the agent's pick`. Grouped by when the candidate's move pays off:

  damage (now)          the control -- no delayed value to miss
  heal (now or soon)    Roost, Life Dew
  boost (later turns)   Calm Mind, Swords Dance, Charm
  status (later turns)  Will-O-Wisp, Hypnosis
  field (many turns)    Reflect, Tailwind, Trick Room
  volatile (varies)     Substitute, Yawn, Disable, Protect
  other status          Parting Shot, After You, Baton Pass

**If the delayed classes carry positive regret while damage sits near zero, the
one-turn scorer is leaving value on the table and the fix is structural.** If
every class sits near zero, the hypothesis dies here for the cost of one run
and 0040's null needs no further explanation.

Selection and scoring are separated the way 0039 does it: candidates are chosen
by our own scorer, which knows nothing about the rollouts that then grade them,
so a candidate cannot be picked because it got lucky.
"""

import json
import random
import sys
from pathlib import Path

from champions_ai.agents import HeuristicAgent
from champions_ai.data import load_all
from champions_ai.data.harvest import harvested_pool
from champions_ai.data.split import split_replays
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_B, MoveAction
from champions_ai.env import BattleEnv
from champions_ai.env.battle_env import Decision
from champions_ai.evaluation import play_battle, play_out
from champions_ai.simulator import ShowdownBridge

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("delayed.json")
BATTLES = int(sys.argv[2]) if len(sys.argv) > 2 else 260
ROLLOUTS = int(sys.argv[3]) if len(sys.argv) > 3 else 14
MAX_STEP = 8
POINTS_PER_BATTLE = 2

BATTLE_SEED_BASE = 0x41000000
BRANCH_SEED_BASE = 0x41BEEF00


def payoff_class(move) -> str:
    """When this move pays off, read off the dex rather than a hand-kept list."""
    if move.is_damaging:
        return "damage (now)"
    if move.side_condition or move.pseudo_weather or move.sets_weather or move.sets_terrain:
        return "field (many turns)"
    if move.boosts or move.self_boosts:
        return "boost (later turns)"
    if move.status:
        return "status (later turns)"
    if move.heal or move.slot_condition:
        return "heal (now or soon)"
    if move.volatile_status:
        return "volatile (varies)"
    return "other status"


def seed_for(n: int) -> str:
    return "sodium," + f"{n:032x}"


def slot_move(observation, slot, action, dex):
    """The move a slot action would use, or None if it is not a move."""
    if not isinstance(action, MoveAction):
        return None
    index = observation.own_side.active_slots[slot]
    if index is None:
        return None
    moves = observation.own_side.team[index].selectable_moves
    if action.move_index >= len(moves):
        return None
    try:
        return dex.get_move(moves[action.move_index])
    except KeyError:
        return None


def main() -> None:
    corpus = load_all(Path("data/replays"))
    train = list(split_replays(list(corpus.replays)).train)
    rng = random.Random(41041)
    rows = []

    with ShowdownBridge() as bridge:
        dex = Dex.cached(bridge, Path("data/dex.json"))
        env = BattleEnv(REGULATION_M_B, bridge=bridge)
        pool = harvested_pool(
            bridge, REGULATION_M_B.format_id, train, dex=dex, seed=1,
            cache=Path("data/pool-eval.txt"),
        )

        def agents():
            return (HeuristicAgent(dex, name="a"), HeuristicAgent(dex, name="b"))

        print(f"pool {len(pool)} teams, {BATTLES} battles, {ROLLOUTS} rollouts each")
        print("candidates differ in exactly one slot, so a regret is one move's\n", flush=True)

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
                base = probe[0].select_action(observation, legal)
                opponent = probe[1].select_action(env.observation(1), env.legal_actions(1))

                # Vary exactly one slot; hold the rest at the agent's own choice.
                slots = [
                    s for s in range(len(base.slot_actions))
                    if observation.own_side.active_slots[s] is not None
                ]
                if not slots:
                    continue
                slot = rng.choice(slots)
                variants = [
                    joint for joint in legal
                    if all(
                        joint.slot_actions[i] == base.slot_actions[i]
                        for i in range(len(base.slot_actions))
                        if i != slot
                    )
                ]
                if len(variants) < 2:
                    continue

                scored = []
                for joint in variants:
                    move = slot_move(observation, slot, joint.slot_actions[slot], dex)
                    if move is None:
                        continue
                    scored.append(
                        (
                            probe[0].score_slot_action(
                                observation, slot, joint.slot_actions[slot]
                            ).score,
                            payoff_class(move),
                            move.name,
                            joint,
                        )
                    )
                if not scored:
                    continue

                # The agent's own pick, plus the best alternative our scorer
                # offers in each direction, plus one at random for spread.
                # Chosen by the scorer, which has not seen the rollouts.
                chosen = {id(base): ("the agent's pick", base)}
                status = [s for s in scored if s[1] != "damage (now)"]
                damage = [s for s in scored if s[1] == "damage (now)"]
                for group in (status, damage):
                    if not group:
                        continue
                    best = max(group, key=lambda entry: entry[0])
                    chosen.setdefault(id(best[3]), (best[2], best[3]))
                spare = rng.choice(scored)
                chosen.setdefault(id(spare[3]), (spare[2], spare[3]))

                branches = [
                    seed_for(BRANCH_SEED_BASE + battle * 10000 + step * 100 + i)
                    for i in range(ROLLOUTS)
                ]
                measured = []
                for _, joint in chosen.values():
                    move = slot_move(observation, slot, joint.slot_actions[slot], dex)
                    wins = 0
                    for branch in branches:
                        env.replay(trajectory, teams, stop_after=step)
                        env.reseed(branch)
                        result = env.step({0: joint, 1: opponent})
                        if not result.terminal:
                            result = play_out(env, agents())
                        wins += int(result.winner == 0)
                    measured.append(
                        {
                            "move": move.name if move else None,
                            "payoff": payoff_class(move) if move else "not a move",
                            "score": probe[0].score_slot_action(
                                observation, slot, joint.slot_actions[slot]
                            ).score,
                            "win_rate": wins / len(branches),
                            "is_pick": joint == base,
                        }
                    )

                if not any(entry["is_pick"] for entry in measured):
                    continue
                rows.append(
                    {
                        "battle": battle,
                        "turn": observation.turn,
                        "slot": slot,
                        "variants": len(variants),
                        "candidates": measured,
                    }
                )
                picked = next(e for e in measured if e["is_pick"])
                best = max(measured, key=lambda e: e["win_rate"])
                print(
                    f"  battle {battle:>3} turn {observation.turn:>2}"
                    f"  pick {picked['move'] or '-':<14} {picked['win_rate']:>5.0%}"
                    f"  best {best['move'] or '-':<14} {best['win_rate']:>5.0%}"
                    f"  ({len(rows)})",
                    flush=True,
                )

    OUT.write_text(json.dumps(rows), encoding="utf-8")
    print(f"\n{len(rows)} decision points written to {OUT}")


if __name__ == "__main__":
    main()
