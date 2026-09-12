"""0051 — Trick Room priced by whether the speed flip helps us.

See PRE-REGISTRATION.md. The instrument check runs first and counts, over
battles driven by the new agent with the old one asked at every decision:

- whether a Trick Room move was legal (the ceiling),
- whether its *score* moved (does the change fire),
- whether the *choice* differed (does it decide anything),
- and whether a choice differed with no Trick Room move legal, which must be 0.

    python experiments/0051-trick-room-by-speed/run.py [battles]
"""

import sys

from champions_ai.agents import HeuristicAgent
from champions_ai.cli.play import dex_path, load_pool, pool_path_for
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_C, MoveAction
from champions_ai.env import BattleEnv
from champions_ai.env.battle_env import Decision
from champions_ai.evaluation.runner import evaluate, wilson_interval
from champions_ai.simulator import ShowdownBridge
from champions_ai.simulator.tracker import to_id

BATTLES = int(sys.argv[1]) if len(sys.argv) > 1 else 800
CHECK_BATTLES = 20


class Tally:
    def __init__(self) -> None:
        self.decisions = 0
        self.trick_room_legal = 0
        self.score_moved = 0
        self.differed = 0
        self.differed_without_trick_room = 0


def _trick_room_actions(dex, observation, legal):
    """Every (slot, MoveAction) in the legal set whose move is Trick Room."""
    found = set()
    for joint in legal:
        for slot, action in enumerate(joint.slot_actions):
            if not isinstance(action, MoveAction):
                continue
            index = observation.own_side.active_slots[slot]
            if index is None:
                continue
            moves = observation.own_side.team[index].selectable_moves
            if action.move_index >= len(moves):
                continue
            try:
                move = dex.get_move(moves[action.move_index])
            except KeyError:
                continue
            if to_id(move.pseudo_weather or "") == "trickroom":
                found.add((slot, action))
    return found


def count_differences(dex, env, pool, aware, blind, battles: int) -> Tally:
    tally = Tally()
    for index, matchup in enumerate(pool.matchups(battles, seed=0)):
        for agent in (aware, blind):
            agent.on_battle_start()
        env.reset(matchup.teams, seed=str(index))
        while not env.terminal:
            waiting = env.awaiting()
            if not waiting:
                break
            choices = {}
            for player in waiting:
                if env.decision(player) is Decision.TEAM_PREVIEW:
                    choices[player] = aware.select_team_preview(
                        env.team_preview(player), env.regulation.picked_team_size
                    )
                    continue
                observation = env.observation(player)
                legal = env.legal_actions(player)
                chosen = aware.select_action(observation, legal)
                alternative = blind.select_action(observation, legal)
                choices[player] = chosen

                tally.decisions += 1
                actions = _trick_room_actions(dex, observation, legal)
                if actions:
                    tally.trick_room_legal += 1
                if any(
                    aware.score_slot_action(observation, slot, action).score
                    != blind.score_slot_action(observation, slot, action).score
                    for slot, action in actions
                ):
                    tally.score_moved += 1
                if chosen != alternative:
                    tally.differed += 1
                    if not actions:
                        tally.differed_without_trick_room += 1
            env.step(choices)
    return tally


def main() -> None:
    with ShowdownBridge() as bridge:
        dex = Dex.cached(bridge, dex_path(REGULATION_M_C), mod=REGULATION_M_C.mod)
        pool = load_pool(bridge, REGULATION_M_C, pool_path_for(REGULATION_M_C))
        env = BattleEnv(REGULATION_M_C, bridge=bridge)

        aware = HeuristicAgent(dex, name="tr-by-speed", trick_room_by_speed=True)
        blind = HeuristicAgent(dex, name="tr-flat")

        print(f"\n  0051 — {len(pool.teams)} teams in the pool\n")
        tally = count_differences(dex, env, pool, aware, blind, CHECK_BATTLES)

        def share(n):
            return f"{n / tally.decisions:.1%}" if tally.decisions else "n/a"

        print(f"  instrument check over {CHECK_BATTLES} battles, before any win rate")
        print(f"    {'decisions compared':<34} {tally.decisions}")
        rows = (
            ("a Trick Room move was legal", tally.trick_room_legal),
            ("its score MOVED", tally.score_moved),
            ("decisions that DIFFERED", tally.differed),
        )
        for label, count in rows:
            print(f"    {label:<34} {count}  ({share(count)})")
        bare = tally.differed_without_trick_room
        print(f"    {'differed with no Trick Room legal':<34} {bare}  (must be 0)")

        if bare:
            print(
                "\n    The arms disagree where no Trick Room move is legal, so they"
                "\n    differ in something other than this change. Not running the A/B."
            )
            return
        if tally.score_moved == 0:
            print(
                "\n    No score moved. The change never fired on these battles;"
                "\n    an A/B would measure two identical agents. Not running it."
            )
            return

        print(f"\n  running {BATTLES} battles\n")
        result = evaluate(env, aware, blind, pool, battles=BATTLES, seed=0)
        low, high = wilson_interval(result.wins_a, result.battles)
        print(
            f"    by-speed {result.wins_a} / flat {result.wins_b} of {result.battles}"
            f"   ({result.win_rate_a:.1%})"
        )
        print(f"    95% Wilson [{low:.1%}, {high:.1%}]")
        verdict = (
            "above 50%: turn trick_room_by_speed on by default"
            if low > 0.5
            else "below 50%: keep it off and investigate the pricing"
            if high < 0.5
            else "neutral: keep it off and record the number"
        )
        print(f"\n    {verdict}\n")


if __name__ == "__main__":
    main()
