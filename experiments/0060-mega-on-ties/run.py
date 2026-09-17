"""0060 — break Mega ties toward the Mega.

    python experiments/0060-mega-on-ties/run.py [battles]

See PRE-REGISTRATION.md: instrument check with a must-be-0 row, Mega timing in
self-play with the setting on and off, then an 800-battle A/B on seed 60.
"""

import sys

from champions_ai.agents import HeuristicAgent
from champions_ai.agents.heuristic import _combined_targets, _mega_count
from champions_ai.cli.play import dex_path, load_pool, pool_path_for
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_C
from champions_ai.env import BattleEnv
from champions_ai.env.battle_env import Decision
from champions_ai.evaluation.runner import evaluate, wilson_interval
from champions_ai.simulator import ShowdownBridge

BATTLES = int(sys.argv[1]) if len(sys.argv) > 1 else 800
SEED = 60
CHECK_BATTLES = 20


def joint_total(agent, observation, joint) -> float:
    scored = [agent.score_slot_action(observation, slot, action)
              for slot, action in enumerate(joint.slot_actions)]
    return sum(s.score for s in scored) + _combined_targets(scored)


def battle_check(env, pool, on, off):
    decisions = differed = violations = 0
    for index, pair in enumerate(pool.matchups(CHECK_BATTLES, seed=SEED)):
        for agent in (on, off):
            agent.on_battle_start()
        env.reset(pair.teams, seed=str(index))
        while not env.terminal:
            waiting = env.awaiting()
            if not waiting:
                break
            choices = {}
            for player in waiting:
                if env.decision(player) is Decision.TEAM_PREVIEW:
                    choices[player] = on.select_team_preview(
                        env.team_preview(player), env.regulation.picked_team_size
                    )
                    continue
                observation = env.observation(player)
                legal = env.legal_actions(player)
                chosen = on.select_action(observation, legal)
                other = off.select_action(observation, legal)
                decisions += 1
                if chosen != other:
                    differed += 1
                    tie = joint_total(on, observation, chosen) == joint_total(
                        on, observation, other
                    )
                    if not (tie and _mega_count(chosen) > _mega_count(other)):
                        violations += 1
                choices[player] = chosen
            env.step(choices)
    return decisions, differed, violations


def mega_timing(env, pool, agent):
    """Share of the agent's Megas on the Pokemon's first turn out, in self-play."""
    first = total = 0
    for index, pair in enumerate(pool.matchups(CHECK_BATTLES, seed=SEED + 1)):
        agent.on_battle_start()
        env.reset(pair.teams, seed=str(index))
        while not env.terminal:
            waiting = env.awaiting()
            if not waiting:
                break
            choices = {}
            for player in waiting:
                if env.decision(player) is Decision.TEAM_PREVIEW:
                    choices[player] = agent.select_team_preview(
                        env.team_preview(player), env.regulation.picked_team_size
                    )
                else:
                    choices[player] = agent.select_action(
                        env.observation(player), env.legal_actions(player)
                    )
            env.step(choices)
        turn = 0
        arrived: dict[str, int] = {}
        for line in env.protocol:
            parts = line.split("|")
            if line.startswith("|turn|"):
                turn = int(parts[2])
            elif line.startswith(("|switch|", "|drag|", "|replace|")) and len(parts) > 2:
                arrived[parts[2].split(":")[0].strip()] = max(1, turn + 1)
            elif line.startswith("|-mega|") and len(parts) > 2:
                came = arrived.get(parts[2].split(":")[0].strip())
                if came is None:
                    continue
                total += 1
                first += turn <= came
    return first, total


def main() -> None:
    with ShowdownBridge() as bridge:
        dex = Dex.cached(bridge, dex_path(REGULATION_M_C), mod=REGULATION_M_C.mod)
        pool = load_pool(bridge, REGULATION_M_C, pool_path_for(REGULATION_M_C))
        env = BattleEnv(REGULATION_M_C, bridge=bridge)
        on = HeuristicAgent(dex, name="mega-on-ties", mega_on_ties=True)
        off = HeuristicAgent(dex, name="shipped")

        print("\n  0060 mega_on_ties\n")
        decisions, differed, violations = battle_check(env, pool, on, off)
        print("  instrument check")
        print(f"    battle decisions differ           {differed}/{decisions}"
              f"  ({differed / max(1, decisions):.1%})")
        print(f"    differing but not a Mega tie      {violations}  (must be 0)")
        for label, agent in (("off", HeuristicAgent(dex, name="off")),
                             ("on", HeuristicAgent(dex, name="on", mega_on_ties=True))):
            first, total = mega_timing(env, pool, agent)
            print(f"    Megas on first turn out, {label:<4}    {first}/{total}"
                  f"  ({first / max(1, total):.1%})   corpus: 88.9%")
        if violations:
            print("\n    The must-be-0 row is not 0. Not running the A/B.")
            return
        if differed == 0:
            print("\n    Nothing differs: a no-op. Not running the A/B.")
            return

        result = evaluate(env, on, off, pool, battles=BATTLES, seed=SEED)
        low, high = wilson_interval(result.wins_a, result.battles)
        decided = sum(1 for scores in result.matchup_scores.values() if sum(scores) != 0)
        print(f"  A/B, {result.battles} battles, seed {SEED}")
        print(f"    record                            {result.wins_a} / {result.wins_b}"
              f"  ({result.win_rate_a:.1%})")
        print(f"    95% Wilson                        [{low:.1%}, {high:.1%}]")
        print(f"    matchups decided                  {decided} of {len(result.matchup_scores)}")
        print(f"    adoption rule (lower bound > 50%) {'MET' if low > 0.5 else 'NOT met'}\n")


if __name__ == "__main__":
    main()
