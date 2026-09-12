"""0049 — the switch scorer, told what field it is actually standing on.

See PRE-REGISTRATION.md. Two phases, in this order:

1. **Do the two arms decide anything differently, and how often is a field even
   up?** Fields are not up on turn one; somebody has to set one. So the share
   of decisions taken on a field is the ceiling on any effect here, and it is
   measured rather than assumed.
2. The A/B: `evaluate` swaps the agents between the two passes of every matchup
   on a shared seed, so teams and seats are identical and only the flag differs.

Unlike 0047 and 0048 the A/B does not decide this one. Passing the real field
to a damage calculation is an engine fact, not a judgement, so it ships on
correctness and the number sizes it. A *negative* result that clears its
interval is the one outcome that stops the ship, and it would mean something
downstream was compensating for the bare-field score.

    python experiments/0049-switching-on-the-field/run.py [battles]
"""

import sys

from champions_ai.agents import HeuristicAgent
from champions_ai.cli.play import dex_path, load_pool, pool_path_for
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_C, SwitchAction
from champions_ai.env import BattleEnv
from champions_ai.env.battle_env import Decision
from champions_ai.evaluation.runner import evaluate, wilson_interval
from champions_ai.simulator import ShowdownBridge

BATTLES = int(sys.argv[1]) if len(sys.argv) > 1 else 400
CHECK_BATTLES = 20


class Tally:
    """What the instrument check counts."""

    def __init__(self) -> None:
        self.decisions = 0
        self.on_a_field = 0
        self.differed = 0
        # Decisions where the field changed what a *switch* is worth, whether
        # or not it changed the action finally chosen. The gap between this and
        # `differed` is the whole story: a score can move without moving the
        # argmax, and without this counter a small `differed` is unreadable --
        # indistinguishable from the fix not firing at all.
        self.switch_score_moved = 0
        # A difference with no field up would mean the two arms disagree about
        # something other than the field, which would invalidate the A/B. It
        # must stay at zero.
        self.differed_on_bare_ground = 0


def _switch_scores_moved(observation, legal, aware, blind) -> bool:
    """Did knowing the field change what any switch is worth here?

    Asked of the score rather than the choice, because those are different
    questions and only the pair of them is readable. `_score_switch_on_matchup`
    prices the *difference* between two Pokemon on the same field, so a
    modifier that moves both candidates alike cancels before it reaches the
    number -- the fix bites where the two differ in type, not merely where a
    field is up.
    """
    seen: set[tuple[int, int]] = set()
    for joint in legal:
        for slot, action in enumerate(joint.slot_actions):
            if not isinstance(action, SwitchAction):
                continue
            key = (slot, action.team_index)
            if key in seen:
                continue
            seen.add(key)
            if (
                aware.score_slot_action(observation, slot, action).score
                != blind.score_slot_action(observation, slot, action).score
            ):
                return True
    return False


def count_differences(env, pool, aware, blind, battles: int) -> Tally:
    """Play with the aware agent and ask the blind one what it would have done.

    The aware agent drives both seats so the battles are the ones the shipped
    agent actually plays; the blind arm is asked at every decision without ever
    acting on its answer, which keeps the trajectory fixed while both policies
    are evaluated against the same states.
    """
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
                field_up = bool(observation.weather or observation.terrain)
                if field_up:
                    tally.on_a_field += 1
                if _switch_scores_moved(observation, legal, aware, blind):
                    tally.switch_score_moved += 1
                if chosen != alternative:
                    tally.differed += 1
                    if not field_up:
                        tally.differed_on_bare_ground += 1
            env.step(choices)
    return tally


def main() -> None:
    with ShowdownBridge() as bridge:
        dex = Dex.cached(bridge, dex_path(REGULATION_M_C), mod=REGULATION_M_C.mod)
        pool = load_pool(bridge, REGULATION_M_C, pool_path_for(REGULATION_M_C))
        env = BattleEnv(REGULATION_M_C, bridge=bridge)

        aware = HeuristicAgent(dex, name="aware")
        blind = HeuristicAgent(dex, name="blind", field_aware_switching=False)

        print(f"\n  0049 — {len(pool.teams)} teams in the pool\n")

        tally = count_differences(env, pool, aware, blind, CHECK_BATTLES)
        share = tally.on_a_field / tally.decisions if tally.decisions else 0.0
        print(f"  instrument check over {CHECK_BATTLES} battles, before any win rate")
        print(f"    decisions compared        {tally.decisions}")
        print(f"    taken with a field up     {tally.on_a_field}  ({share:.0%})")
        moved = tally.switch_score_moved
        print(f"    a switch score MOVED      {moved}  ({moved / max(1, tally.decisions):.0%})")
        print(f"    decisions that DIFFERED   {tally.differed}")
        print(f"    differed on bare ground   {tally.differed_on_bare_ground}  (must be 0)")

        if tally.differed_on_bare_ground:
            print(
                "\n    The arms disagree with no field up, so they differ in"
                "\n    something other than the field. The A/B would not be"
                "\n    measuring this change. Not running it."
            )
            return
        if tally.differed == 0:
            print(
                "\n    No-op. The arms agree on every decision, so an A/B would"
                "\n    be measuring two identical agents. Not running it."
            )
            return

        print(f"\n  arms differ on {tally.differed / tally.decisions:.1%} — running {BATTLES}\n")
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
            else "below 50%: STOP -- something was compensating for the bare-field score"
            if high < 0.5
            else "neutral: ships on correctness, and 400 battles cannot resolve the size"
        )
        print(f"\n    {verdict}\n")


if __name__ == "__main__":
    main()
