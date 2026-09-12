"""0053 — our own set, and the field our own team creates.

    python experiments/0053-own-set-and-field/run.py ourset    # C: matchup_reads_our_set
    python experiments/0053-own-set-and-field/run.py ownfield  # D: own_field

See PRE-REGISTRATION.md. Instrument checks first, the A/B only after.
"""

import sys

from champions_ai.agents import HeuristicAgent
from champions_ai.cli.play import dex_path, load_pool, pool_path_for
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_C, TeamPreview
from champions_ai.env import BattleEnv
from champions_ai.env.battle_env import Decision
from champions_ai.evaluation.runner import evaluate, wilson_interval
from champions_ai.mechanics.abilities import terrain_on_arrival, weather_on_arrival
from champions_ai.simulator import ShowdownBridge
from champions_ai.simulator.tracker import to_id

CHECK_TEAMS = 20
CHECK_BATTLES = 20
BATTLES = 400


def _has_arrival_setter(agent, team) -> bool:
    for mon in team.pokemon:
        forms = [mon]
        evolved = agent._own_mega_set(mon)
        if evolved is not None:
            forms.append(evolved)
        for form in forms:
            ability = to_id(form.ability)
            if weather_on_arrival(ability) or terrain_on_arrival(ability):
                return True
    return False


def preview_check(pool, aware, blind, precondition):
    teams = pool.teams[:CHECK_TEAMS]
    size = REGULATION_M_C.picked_team_size
    previews = held = differed = without = 0
    for ours in teams:
        for theirs in teams:
            if ours is theirs:
                continue
            preview = TeamPreview.from_teams(REGULATION_M_C, ours.team, theirs.team)
            previews += 1
            holds = precondition(ours.team)
            held += holds
            if aware.select_team_preview(preview, size).picks != blind.select_team_preview(
                preview, size
            ).picks:
                differed += 1
                without += not holds
    return previews, held, differed, without


def battle_check(env, pool, aware, blind):
    """Decisions compared in battles driven by the aware agent."""
    decisions = differed = 0
    for index, matchup in enumerate(pool.matchups(CHECK_BATTLES, seed=0)):
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
    which = sys.argv[1] if len(sys.argv) > 1 else "ourset"
    battles = int(sys.argv[2]) if len(sys.argv) > 2 else BATTLES
    with ShowdownBridge() as bridge:
        dex = Dex.cached(bridge, dex_path(REGULATION_M_C), mod=REGULATION_M_C.mod)
        pool = load_pool(bridge, REGULATION_M_C, pool_path_for(REGULATION_M_C))
        env = BattleEnv(REGULATION_M_C, bridge=bridge)

        if which == "ourset":
            aware = HeuristicAgent(dex, name="reads-our-set")
            blind = HeuristicAgent(dex, name="blind-to-our-set", matchup_reads_our_set=False)
        elif which == "ownfield":
            aware = HeuristicAgent(dex, name="own-field")
            blind = HeuristicAgent(dex, name="bare-ground", own_field=False)
        else:
            raise SystemExit(f"unknown comparison {which!r}: use 'ourset' or 'ownfield'")

        print(f"\n  0053 {which} — {len(pool.teams)} teams in the pool\n")
        print("  instrument check, before any win rate")
        def precondition(team):
            return _has_arrival_setter(aware, team) if which == "ownfield" else True

        previews, held, differed, without = preview_check(pool, aware, blind, precondition)
        print(f"    {'previews compared':<36} {previews}")
        if which == "ownfield":
            print(f"    {'our team has an arrival setter':<36} {held}  ({held / previews:.0%})")
        print(f"    {'Team Preview picks DIFFERED':<36} {differed}  ({differed / previews:.0%})")
        if which == "ownfield":
            print(f"    {'differed without a setter':<36} {without}  (must be 0)")
            if without:
                print("\n    Picks differ where the change cannot apply. Not running the A/B.")
                return

        moved_in_battle = 0
        if which == "ourset":
            decisions, moved_in_battle = battle_check(env, pool, aware, blind)
            print(
                f"    {'in-battle decisions DIFFERED':<36} {moved_in_battle} of {decisions}"
                f"  ({moved_in_battle / max(1, decisions):.1%})"
            )

        if differed == 0 and moved_in_battle == 0:
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
