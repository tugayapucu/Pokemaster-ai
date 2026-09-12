"""0056 — how much of a denied hit should speed be worth?

    python experiments/0056-speed-race-credit/run.py <credit> [battles]

One arm per process: `speed_beyond_knockouts` on at <credit>, against the shipped
agent. See PRE-REGISTRATION.md: seed 1 (fresh against 0055's seed 0), 800
battles, 95% and Bonferroni-adjusted 98.75% intervals, decided matchups, and the
magnitude table that shows whether a credit is a sane size.
"""

import random
import statistics
import sys

from champions_ai.agents import HeuristicAgent
from champions_ai.cli.play import dex_path, load_pool, pool_path_for
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_C, TeamPreview
from champions_ai.env import BattleEnv
from champions_ai.env.battle_env import Decision
from champions_ai.evaluation.runner import evaluate, wilson_interval
from champions_ai.mechanics import matchup
from champions_ai.simulator import ShowdownBridge

CREDIT = float(sys.argv[1])
BATTLES = int(sys.argv[2]) if len(sys.argv) > 2 else 800
SEED = 1
Z_ADJUSTED = 2.4977  # two-sided 98.75%: 95% split across four arms
NEUTRAL_HIT = 0.224
CHECK_TEAMS = 40
CHECK_BATTLES = 20


def magnitude(dex, pool, agent):
    rng = random.Random(7)
    teams = rng.sample(pool.teams, 60)
    sets = [m for t in teams[:30] for m in t.team.pokemon]
    foes = [dex.get_species(m.species) for t in teams[30:] for m in t.team.pokemon]
    shared = dict(
        level=50, doubles=True, assumed_points=agent.assumed_opponent_points,
        price_turn_costs=True,
    )
    edges, above_hit, above_trade, flips = [], 0, 0, 0
    for mon in sets:
        own = agent._set_for_matchup(mon)
        for foe in foes:
            try:
                off = matchup(dex, mon, foe, **shared, **own)
                on = matchup(
                    dex, mon, foe, speed_beyond_knockouts=True, speed_race_credit=CREDIT,
                    **shared, **own,
                )
            except KeyError:
                continue
            edge = abs(on.speed_edge)
            edges.append(edge)
            above_hit += edge > NEUTRAL_HIT
            above_trade += edge > abs(on.offence - on.defence)
            flips += (off.net > 0) != (on.net > 0)
    n = len(edges)
    return n, statistics.median(edges), above_hit / n, above_trade / n, flips / n


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
    for index, matchup_pair in enumerate(pool.matchups(CHECK_BATTLES, seed=SEED)):
        for agent in (aware, blind):
            agent.on_battle_start()
        env.reset(matchup_pair.teams, seed=str(index))
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

        aware = HeuristicAgent(
            dex, name=f"credit-{CREDIT:g}",
            speed_beyond_knockouts=True, speed_race_credit=CREDIT,
        )
        blind = HeuristicAgent(dex, name="one-hit")

        print(f"\n  0056 credit {CREDIT:g}\n")
        n, median, above_hit, above_trade, flips = magnitude(dex, pool, blind)
        print(f"  magnitude over {n} pool pairings")
        print(f"    median speed edge                 {median:.3f}")
        print(f"    above a neutral hit ({NEUTRAL_HIT})      {above_hit:.0%}")
        print(f"    above the whole damage trade      {above_trade:.0%}")
        print(f"    verdicts flipped                  {flips:.0%}")

        previews, p_differed = preview_check(pool, aware, blind)
        decisions, differed = battle_check(env, pool, aware, blind)
        print("  instrument check")
        print(f"    Team Preview picks differ         {p_differed}/{previews}"
              f"  ({p_differed / previews:.0%})")
        print(f"    battle decisions differ           {differed}/{decisions}"
              f"  ({differed / max(1, decisions):.1%})")

        if p_differed == 0 and differed == 0:
            print("\n    Nothing differs: a no-op. Not running the A/B.")
            return

        result = evaluate(env, aware, blind, pool, battles=BATTLES, seed=SEED)
        low, high = wilson_interval(result.wins_a, result.battles)
        low_adj, high_adj = wilson_interval(result.wins_a, result.battles, z=Z_ADJUSTED)
        decided = sum(1 for scores in result.matchup_scores.values() if sum(scores) != 0)
        print(f"  A/B, {result.battles} battles, seed {SEED}")
        print(f"    record                            {result.wins_a} / {result.wins_b}"
              f"  ({result.win_rate_a:.1%})")
        print(f"    95% Wilson                        [{low:.1%}, {high:.1%}]")
        print(f"    98.75% Wilson (adjusted bar)      [{low_adj:.1%}, {high_adj:.1%}]")
        print(f"    matchups decided                  {decided} of {len(result.matchup_scores)}\n")


if __name__ == "__main__":
    main()
