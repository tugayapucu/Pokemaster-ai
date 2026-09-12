"""0048 — the same agent, but for predicting the field their six will set.

See PRE-REGISTRATION.md. Two phases, in this order and not the other:

1. **Do the two arms decide anything differently?** 0047 measured a change that
   could never fire and returned 200/200, which is exactly what `evaluate`
   produces for two identical agents. The A/B here does not run until the
   picks are known to differ.
2. The A/B itself: `evaluate` swaps the agents between the two passes of every
   matchup on a shared seed, so the teams and the seats are identical and the
   only difference is the flag.

    python experiments/0048-team-preview-field/run.py [battles]
"""

import sys
from pathlib import Path

from champions_ai.agents import HeuristicAgent
from champions_ai.cli.play import dex_path, load_pool, pool_path_for
from champions_ai.data.priors import load_field_priors
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_C, TeamPreview
from champions_ai.env import BattleEnv
from champions_ai.evaluation.runner import evaluate, wilson_interval
from champions_ai.simulator import ShowdownBridge

BATTLES = int(sys.argv[1]) if len(sys.argv) > 1 else 400
# Every ordered pair of the first this-many teams. The check needs no engine --
# Team Preview is decided before a battle exists -- so it is cheap enough to
# run over far more previews than the A/B itself plays battles.
CHECK_TEAMS = 20


def count_differences(dex, pool, predicting, blind) -> tuple[int, int, int]:
    """(previews, differing picks, previews containing a covered species).

    The third number separates the two ways a no-op can happen: the prior
    never applies, or it applies and changes nothing. 0047 was the first, and
    reported the second by accident.
    """
    teams = pool.teams[:CHECK_TEAMS]
    size = REGULATION_M_C.picked_team_size
    previews = differed = covered = 0
    for ours in teams:
        for theirs in teams:
            if ours is theirs:
                continue
            preview = TeamPreview.from_teams(REGULATION_M_C, ours.team, theirs.team)
            previews += 1
            if predicting._predicted_field(preview.opponent_team):
                covered += 1
            a = predicting.select_team_preview(preview, size).picks
            b = blind.select_team_preview(preview, size).picks
            if a != b:
                differed += 1
    return previews, differed, covered


def main() -> None:
    priors = load_field_priors(Path(f"data/field-priors-{REGULATION_M_C.mod}.json"))
    if not priors:
        raise SystemExit("no field-priors file; run build.py before measuring against it")

    with ShowdownBridge() as bridge:
        dex = Dex.cached(bridge, dex_path(REGULATION_M_C), mod=REGULATION_M_C.mod)
        pool = load_pool(bridge, REGULATION_M_C, pool_path_for(REGULATION_M_C))
        env = BattleEnv(REGULATION_M_C, bridge=bridge)

        predicting = HeuristicAgent(dex, name="field", field_priors=priors)
        blind = HeuristicAgent(dex, name="bare")

        print(f"\n  0048 — {len(pool.teams)} teams in the pool")
        print(f"  prior covers {len(priors)} species\n")

        previews, differed, covered = count_differences(dex, pool, predicting, blind)
        print("  instrument check, before any win rate is read")
        print(f"    previews compared              {previews}")
        print(f"    with a covered species on side {covered}")
        print(f"    picks that DIFFERED            {differed}")

        if differed == 0:
            print(
                "\n    No-op. The arms agree on every pick, so an A/B would be"
                "\n    measuring two identical agents. Not running it."
            )
            return

        print(f"\n  arms differ on {differed / previews:.0%} of previews — running {BATTLES}\n")
        result = evaluate(env, predicting, blind, pool, battles=BATTLES, seed=0)
        low, high = wilson_interval(result.wins_a, result.battles)
        print(
            f"    field {result.wins_a} / bare {result.wins_b} of {result.battles}"
            f"   ({result.win_rate_a:.1%})"
        )
        print(f"    95% Wilson [{low:.1%}, {high:.1%}]")
        verdict = (
            "above 50%: predicting the field earns its place"
            if low > 0.5
            else "below 50%: the prediction is worse than ignorance"
            if high < 0.5
            else "neutral: better-informed picks that do not convert"
        )
        print(f"\n    {verdict}\n")


if __name__ == "__main__":
    main()
