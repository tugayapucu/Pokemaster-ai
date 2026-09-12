"""0050 — charge moves priced as the turn they charge, not as a hit.

See PRE-REGISTRATION.md. The instrument check runs first and counts, over
battles driven by the new agent with the old one asked at every decision:

- whether a charge-flagged move was legal at all (the ceiling),
- whether any such move's *score* moved (does the change fire),
- whether the *choice* differed (does it decide anything),
- and whether a choice differed with no charge move legal, which must be zero.

The ceiling is a deliberate superset -- "a charge move is legal", not "a move
would charge in the field's weather" -- because a Mega that changes the weather
can make a move charge that the field alone says would not, and a narrower
ceiling would raise a false alarm on exactly the case this change handles.

    python experiments/0050-charge-turns/run.py [battles]
"""

import sys

from champions_ai.agents import HeuristicAgent
from champions_ai.cli.play import dex_path, load_pool, pool_path_for
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_C, MoveAction
from champions_ai.env import BattleEnv
from champions_ai.env.battle_env import Decision
from champions_ai.evaluation.runner import evaluate, wilson_interval
from champions_ai.mechanics.charge import CHARGE_FLAG
from champions_ai.simulator import ShowdownBridge

BATTLES = int(sys.argv[1]) if len(sys.argv) > 1 else 400
CHECK_BATTLES = 20


class Tally:
    def __init__(self) -> None:
        self.decisions = 0
        self.charge_move_legal = 0
        self.score_moved = 0
        self.differed = 0
        self.differed_without_a_charge_move = 0


def _charge_actions(dex, observation, legal):
    """Every (slot, MoveAction) in the legal set whose move carries the flag."""
    found = set()
    for joint in legal:
        for slot, action in enumerate(joint.slot_actions):
            if not isinstance(action, MoveAction):
                continue
            index = observation.own_side.active_slots[slot]
            if index is None:
                continue
            mon = observation.own_side.team[index]
            moves = mon.selectable_moves
            if action.move_index >= len(moves):
                continue
            try:
                move = dex.get_move(moves[action.move_index])
            except KeyError:
                continue
            if CHARGE_FLAG in move.flags:
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
                charge_actions = _charge_actions(dex, observation, legal)
                if charge_actions:
                    tally.charge_move_legal += 1
                if any(
                    aware.score_slot_action(observation, slot, action).score
                    != blind.score_slot_action(observation, slot, action).score
                    for slot, action in charge_actions
                ):
                    tally.score_moved += 1
                if chosen != alternative:
                    tally.differed += 1
                    if not charge_actions:
                        tally.differed_without_a_charge_move += 1
            env.step(choices)
    return tally


def main() -> None:
    with ShowdownBridge() as bridge:
        dex = Dex.cached(bridge, dex_path(REGULATION_M_C), mod=REGULATION_M_C.mod)
        pool = load_pool(bridge, REGULATION_M_C, pool_path_for(REGULATION_M_C))
        env = BattleEnv(REGULATION_M_C, bridge=bridge)

        aware = HeuristicAgent(dex, name="charge-aware")
        blind = HeuristicAgent(dex, name="charge-blind", charge_turns=False)

        print(f"\n  0050 — {len(pool.teams)} teams in the pool\n")
        tally = count_differences(dex, env, pool, aware, blind, CHECK_BATTLES)

        def share(n):
            return f"{n / tally.decisions:.1%}" if tally.decisions else "n/a"

        print(f"  instrument check over {CHECK_BATTLES} battles, before any win rate")
        print(f"    decisions compared               {tally.decisions}")
        rows = (
            ("a charge move was legal", tally.charge_move_legal),
            ("a charge move's score MOVED", tally.score_moved),
            ("decisions that DIFFERED", tally.differed),
        )
        for label, count in rows:
            print(f"    {label:<32} {count}  ({share(count)})")
        bare = tally.differed_without_a_charge_move
        print(f"    {'differed with no charge move':<32} {bare}  (must be 0)")

        if tally.differed_without_a_charge_move:
            print(
                "\n    The arms disagree where no charge move is legal, so they"
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
            f"    aware {result.wins_a} / blind {result.wins_b} of {result.battles}"
            f"   ({result.win_rate_a:.1%})"
        )
        print(f"    95% Wilson [{low:.1%}, {high:.1%}]")
        verdict = (
            "above 50%: the fix pays, and the size is measured"
            if low > 0.5
            else "below 50%: STOP -- something was compensating for the old pricing"
            if high < 0.5
            else "neutral: ships on correctness; 400 battles cannot resolve the size"
        )
        print(f"\n    {verdict}\n")


if __name__ == "__main__":
    main()
