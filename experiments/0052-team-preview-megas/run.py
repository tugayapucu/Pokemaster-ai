"""0052 — Team Preview learns that Pokemon Mega Evolve.

    python experiments/0052-team-preview-megas/run.py own       # B: own_megas
    python experiments/0052-team-preview-megas/run.py opponent  # A: opponent_megas

See PRE-REGISTRATION.md. Each comparison runs its instrument check first --
380 Team Previews, no battles -- and only then the A/B.
"""

import sys
from pathlib import Path

from champions_ai.agents import HeuristicAgent
from champions_ai.cli.play import dex_path, load_pool, pool_path_for
from champions_ai.data.priors import load_mega_priors
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_C, TeamPreview
from champions_ai.env import BattleEnv
from champions_ai.evaluation.runner import evaluate, wilson_interval
from champions_ai.simulator import ShowdownBridge
from champions_ai.simulator.tracker import to_id

CHECK_TEAMS = 20


def _has_own_holder(agent, team) -> bool:
    return any(agent._own_mega_set(mon) is not None for mon in team.pokemon)


def _has_rated_opponent(agent, dex, team) -> bool:
    for mon in team.pokemon:
        try:
            base = dex.get_species(mon.species).base_species
        except KeyError:
            continue
        if to_id(base) in agent.mega_priors:
            return True
    return False


def instrument_check(pool, aware, blind, precondition):
    teams = pool.teams[:CHECK_TEAMS]
    size = REGULATION_M_C.picked_team_size
    previews = held = differed = differed_without = 0
    for ours in teams:
        for theirs in teams:
            if ours is theirs:
                continue
            preview = TeamPreview.from_teams(REGULATION_M_C, ours.team, theirs.team)
            previews += 1
            holds = precondition(ours.team, theirs.team)
            held += holds
            if aware.select_team_preview(preview, size).picks != blind.select_team_preview(
                preview, size
            ).picks:
                differed += 1
                differed_without += not holds
    return previews, held, differed, differed_without


def main() -> None:
    which = sys.argv[1] if len(sys.argv) > 1 else "own"
    with ShowdownBridge() as bridge:
        dex = Dex.cached(bridge, dex_path(REGULATION_M_C), mod=REGULATION_M_C.mod)
        pool = load_pool(bridge, REGULATION_M_C, pool_path_for(REGULATION_M_C))
        env = BattleEnv(REGULATION_M_C, bridge=bridge)

        if which == "own":
            aware = HeuristicAgent(dex, name="own-megas")
            blind = HeuristicAgent(dex, name="base-formes", own_megas=False)
            battles = 400

            def precondition(ours, theirs):
                return _has_own_holder(aware, ours)

            label = "our team has a stone holder"
        elif which == "opponent":
            priors = load_mega_priors(Path(f"data/mega-priors-{REGULATION_M_C.mod}.json"))
            if not priors:
                raise SystemExit("no mega-priors file; run build.py first")
            aware = HeuristicAgent(
                dex, name="opp-megas", mega_priors=priors, opponent_megas=True
            )
            blind = HeuristicAgent(dex, name="opp-base", mega_priors=priors)
            battles = 800

            def precondition(ours, theirs):
                return _has_rated_opponent(aware, dex, theirs)

            label = "their team has a rated species"
        else:
            raise SystemExit(f"unknown comparison {which!r}: use 'own' or 'opponent'")

        battles = int(sys.argv[2]) if len(sys.argv) > 2 else battles
        print(f"\n  0052 {which} — {len(pool.teams)} teams in the pool\n")
        previews, held, differed, without = instrument_check(pool, aware, blind, precondition)
        print("  instrument check, before any win rate")
        print(f"    {'previews compared':<34} {previews}")
        print(f"    {label:<34} {held}  ({held / previews:.0%})")
        print(f"    {'picks that DIFFERED':<34} {differed}  ({differed / previews:.0%})")
        print(f"    {'differed without it':<34} {without}  (must be 0)")

        if without:
            print("\n    Picks differ where the change cannot apply. Not running the A/B.")
            return
        if differed == 0:
            print("\n    No pick differs: a no-op. Not running the A/B.")
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
