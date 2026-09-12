"""0055 — moving first, valued over a race of any length.

    python experiments/0055-speed-beyond-knockouts/run.py [battles]

See PRE-REGISTRATION.md. Instrument checks on randomly drawn teams, then the
A/B, with decided matchups counted so an even record is read correctly.
"""

import random
import sys

from champions_ai.agents import HeuristicAgent
from champions_ai.cli.play import dex_path, load_pool, pool_path_for
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_C, TeamPreview
from champions_ai.env import BattleEnv
from champions_ai.env.battle_env import Decision
from champions_ai.evaluation.runner import evaluate, wilson_interval
from champions_ai.simulator import ShowdownBridge

CHECK_TEAMS = 40
CHECK_BATTLES = 20
BATTLES = int(sys.argv[1]) if len(sys.argv) > 1 else 800


def preview_check(pool, aware, blind):
    teams = random.Random(0).sample(pool.teams, CHECK_TEAMS)
    size = REGULATION_M_C.picked_team_size
    previews = differed = 0
    for ours in teams:
        for theirs in teams:
            if ours is theirs:
                continue
            preview = TeamPreview.from_teams(REGULATION_M_C, ours.team, theirs.team)
            previews += 1
            differed += aware.select_team_preview(preview, size).picks != (
                blind.select_team_preview(preview, size).picks
            )
    return previews, differed


def battle_check(env, pool, aware, blind):
    decisions = differed = 0
    for index, matchup in enumerate(pool.matchups(CHECK_BATTLES, seed=1)):
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
                decisions += 1
                differed += chosen != blind.select_action(observation, legal)
                choices[player] = chosen
            env.step(choices)
    return decisions, differed


def main() -> None:
    with ShowdownBridge() as bridge:
        dex = Dex.cached(bridge, dex_path(REGULATION_M_C), mod=REGULATION_M_C.mod)
        pool = load_pool(bridge, REGULATION_M_C, pool_path_for(REGULATION_M_C))
        env = BattleEnv(REGULATION_M_C, bridge=bridge)

        aware = HeuristicAgent(dex, name="speed-beyond-ko", speed_beyond_knockouts=True)
        blind = HeuristicAgent(dex, name="speed-one-hit")

        print(f"\n  0055 — {len(pool.teams)} teams in the pool\n")
        print("  instrument check, before any win rate")
        previews, p_differed = preview_check(pool, aware, blind)
        print(f"    {'previews (40 random teams)':<34} {previews}")
        picks_share = p_differed / previews
        print(f"    {'Team Preview picks DIFFERED':<34} {p_differed}  ({picks_share:.0%})")
        decisions, differed = battle_check(env, pool, aware, blind)
        print(f"    {'battle decisions compared':<34} {decisions}")
        share = differed / max(1, decisions)
        print(f"    {'battle decisions DIFFERED':<34} {differed}  ({share:.1%})")
        print("    (no must-be-0 row: speed enters nearly every matchup)")

        if p_differed == 0 and differed == 0:
            print("\n    Nothing differs: a no-op. Not running the A/B.")
            return

        print(f"\n  running {BATTLES} battles\n")
        result = evaluate(env, aware, blind, pool, battles=BATTLES, seed=0)
        low, high = wilson_interval(result.wins_a, result.battles)
        decided = sum(1 for scores in result.matchup_scores.values() if sum(scores) != 0)
        print(
            f"    {aware.name} {result.wins_a} / {blind.name} {result.wins_b}"
            f" of {result.battles}   ({result.win_rate_a:.1%})"
        )
        print(f"    95% Wilson [{low:.1%}, {high:.1%}]")
        print(f"    matchups decided: {decided} of {len(result.matchup_scores)}\n")


if __name__ == "__main__":
    main()
