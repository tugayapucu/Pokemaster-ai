"""0054 — moves that cost a turn, priced as the turn they cost.

    python experiments/0054-turn-costs/run.py recharge    # E: recharge_turns
    python experiments/0054-turn-costs/run.py turncosts   # F: matchup_turn_costs

See PRE-REGISTRATION.md. Instrument checks first, on teams drawn at random.
"""

import random
import sys

from champions_ai.agents import HeuristicAgent
from champions_ai.cli.play import dex_path, load_pool, pool_path_for
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_C, MoveAction, TeamPreview
from champions_ai.env import BattleEnv
from champions_ai.env.battle_env import Decision
from champions_ai.evaluation.runner import evaluate, wilson_interval
from champions_ai.mechanics.charge import CHARGE_FLAG, RECHARGE_FLAG
from champions_ai.simulator import ShowdownBridge

CHECK_BATTLES = 20
CHECK_TEAMS = 40
BATTLES = 400


def _move(dex, move_id):
    try:
        return dex.get_move(move_id)
    except KeyError:
        return None


def _recharge_actions(dex, observation, legal):
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
            move = _move(dex, moves[action.move_index])
            if move is not None and RECHARGE_FLAG in move.flags:
                found.add((slot, action))
    return found


def _team_costs_a_turn(dex, team) -> bool:
    for mon in team.pokemon:
        for move_id in mon.moves:
            move = _move(dex, move_id)
            if move is not None and (CHARGE_FLAG in move.flags or RECHARGE_FLAG in move.flags):
                return True
    return False


def battle_check(dex, env, pool, aware, blind, track_recharge):
    decisions = legal_count = moved = differed = without = 0
    for index, matchup in enumerate(pool.matchups(CHECK_BATTLES, seed=1)):
        for agent in (aware, blind):
            agent.on_battle_start()
        # The engine accepts a numeric seed (or "sodium,<hex>"); a label like
        # "check0" is rejected outright.
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
                decisions += 1
                actions = _recharge_actions(dex, observation, legal) if track_recharge else set()
                legal_count += bool(actions)
                moved += any(
                    aware.score_slot_action(observation, s, a).score
                    != blind.score_slot_action(observation, s, a).score
                    for s, a in actions
                )
                if chosen != blind.select_action(observation, legal):
                    differed += 1
                    without += track_recharge and not actions
                choices[player] = chosen
            env.step(choices)
    return decisions, legal_count, moved, differed, without


def preview_check(dex, pool, aware, blind):
    teams = random.Random(0).sample(pool.teams, CHECK_TEAMS)
    size = REGULATION_M_C.picked_team_size
    previews = held = differed = without = 0
    for ours in teams:
        holds = _team_costs_a_turn(dex, ours.team)
        for theirs in teams:
            if ours is theirs:
                continue
            preview = TeamPreview.from_teams(REGULATION_M_C, ours.team, theirs.team)
            previews += 1
            held += holds
            if aware.select_team_preview(preview, size).picks != blind.select_team_preview(
                preview, size
            ).picks:
                differed += 1
                without += not holds
    return previews, held, differed, without


def main() -> None:
    which = sys.argv[1] if len(sys.argv) > 1 else "recharge"
    battles = int(sys.argv[2]) if len(sys.argv) > 2 else BATTLES
    with ShowdownBridge() as bridge:
        dex = Dex.cached(bridge, dex_path(REGULATION_M_C), mod=REGULATION_M_C.mod)
        pool = load_pool(bridge, REGULATION_M_C, pool_path_for(REGULATION_M_C))
        env = BattleEnv(REGULATION_M_C, bridge=bridge)

        if which == "recharge":
            aware = HeuristicAgent(dex, name="recharge-priced")
            blind = HeuristicAgent(dex, name="recharge-free", recharge_turns=False)
        elif which == "turncosts":
            aware = HeuristicAgent(dex, name="matchup-costs")
            blind = HeuristicAgent(dex, name="matchup-free", matchup_turn_costs=False)
        else:
            raise SystemExit(f"unknown comparison {which!r}: use 'recharge' or 'turncosts'")

        print(f"\n  0054 {which} — {len(pool.teams)} teams in the pool\n")
        print("  instrument check, before any win rate")
        bare = 0
        any_difference = False
        def row(label, count, total=None, fmt=".1%"):
            share = f"  ({count / max(1, total):{fmt}})" if total is not None else ""
            print(f"    {label:<38} {count}{share}")

        if which == "turncosts":
            previews, held, p_differed, p_without = preview_check(dex, pool, aware, blind)
            row("previews (40 random teams)", previews)
            row("our team costs a turn somewhere", held, previews, ".0%")
            row("Team Preview picks DIFFERED", p_differed, previews, ".0%")
            print(f"    {'differed without such a move':<38} {p_without}  (must be 0)")
            bare += p_without
            any_difference |= p_differed > 0

        decisions, legal, moved, differed, without = battle_check(
            dex, env, pool, aware, blind, track_recharge=which == "recharge"
        )
        row("battle decisions compared", decisions)
        if which == "recharge":
            row("a recharge move was legal", legal, decisions)
            row("its score MOVED", moved, decisions)
        row("battle decisions DIFFERED", differed, decisions)
        if which == "recharge":
            print(f"    {'differed with no recharge move legal':<38} {without}  (must be 0)")
            bare += without
            any_difference |= moved > 0
        any_difference |= differed > 0

        if bare:
            print("\n    Something differs where the change cannot apply. Not running the A/B.")
            return
        if not any_difference:
            print("\n    Nothing differs: a no-op. Not running the A/B.")
            return

        print(f"\n  running {battles} battles\n")
        result = evaluate(env, aware, blind, pool, battles=battles, seed=0)
        low, high = wilson_interval(result.wins_a, result.battles)
        print(
            f"    {aware.name} {result.wins_a} / {blind.name} {result.wins_b}"
            f" of {result.battles}   ({result.win_rate_a:.1%})"
        )
        print(f"    95% Wilson [{low:.1%}, {high:.1%}]\n")


if __name__ == "__main__":
    main()
