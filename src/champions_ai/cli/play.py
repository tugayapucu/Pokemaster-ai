"""Play a battle in the terminal and see what the engine would advise.

The point of the whole project, finally reachable: a position in front of you,
a ranked shortlist with reasons, and the option to disagree. Everything under
this has been measured at length and none of it could be *used*.

Advice comes from `Recommender`, which shares the agent's own scorer, so what
it suggests is what it would play. Disagreeing is the interesting case rather
than the wrong one: over four candidates the agent picks the best 57% of the
time (0038), which is a long way from authority.
"""

import random
from pathlib import Path

from champions_ai.agents import HeuristicAgent
from champions_ai.cli.board import render_board, render_moves
from champions_ai.cli.preview import parse_picks, render_preview, species_name
from champions_ai.data import BattleTeam, TeamPool, parse_showdown_team
from champions_ai.dex import Dex
from champions_ai.domain import (
    REGULATION_M_B,
    JointAction,
    Regulation,
    TeamPreviewAction,
)
from champions_ai.env import BattleEnv
from champions_ai.env.battle_env import Decision
from champions_ai.recommendation import Recommender, describe_joint_action
from champions_ai.simulator import ShowdownBridge

DEFAULT_POOL = Path("data/pool-eval.txt")
DEFAULT_DEX = Path("data/dex.json")
POOL_SEPARATOR = "\n\n===\n\n"

# Protocol lines worth echoing after a turn. The whole stream is noise to a
# human; these are the ones that say what actually happened.
INTERESTING = (
    "|move|", "|-damage|", "|faint|", "|switch|", "|-status|", "|-boost|",
    "|-unboost|", "|-crit|", "|-supereffective|", "|-resisted|", "|-immune|",
    "|-miss|", "|-heal|", "|-weather|", "|-fieldstart|", "|-sidestart|",
    "|-activate|", "|-mega|", "|win|",
)


def load_team(bridge: ShowdownBridge, regulation: Regulation, path: Path) -> BattleTeam:
    """One team from a Showdown export file, validated by the engine."""
    text = path.read_text(encoding="utf-8").strip()
    return BattleTeam(
        team=parse_showdown_team(text),
        packed=bridge.validate_team(regulation.format_id, text),
        name=path.stem,
    )


def load_pool(bridge: ShowdownBridge, regulation: Regulation, path: Path) -> TeamPool:
    texts = [t for t in path.read_text(encoding="utf-8").split(POOL_SEPARATOR) if t.strip()]
    return TeamPool.from_texts(bridge, regulation.format_id, texts)


def _roster(dex: Dex, team: BattleTeam) -> str:
    """Species as the dex spells them, not as the packed form ids them."""
    return ", ".join(species_name(dex, e.species) for e in team.team.pokemon)


def _echo(protocol: tuple[str, ...], seen: int) -> int:
    """Print what happened since we last looked; return where we got to."""
    for line in protocol[seen:]:
        if line.startswith(INTERESTING):
            print(f"    {line}")
    return len(protocol)


def _ask(options: int) -> str:
    """Read a choice. An empty line means 'the top one', which is the common case."""
    try:
        answer = input(f"\n  choose 1-{options}, [a]uto, [q]uit > ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return "q"
    return answer or "1"


def _choose_team(preview, adviser, dex, regulation, *, auto: bool):
    """Show the Team Preview screen and take a pick, ours or theirs."""
    size = regulation.picked_team_size
    table = adviser.matchup_table(preview)
    suggested = adviser.select_team_preview(preview, size)
    reasons = adviser.explain_team_preview(preview, size)
    print(render_preview(preview, table, suggested.picks, reasons, dex))

    if auto:
        return suggested

    while True:
        try:
            answer = input(
                f"\n  enter to accept, or {size} numbers to choose your own > "
            ).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return suggested
        if not answer:
            return suggested
        picks = parse_picks(answer, len(preview.own_team.pokemon), size)
        if picks is not None:
            names = [
                species_name(dex, preview.own_team.pokemon[i].species) for i in picks
            ]
            print(f"  Bringing: {', '.join(names)}")
            return TeamPreviewAction(picks=picks)
        print(f"  Give {size} different numbers from 1 to {len(preview.own_team.pokemon)}.")


def _show_position(observation, dex, recommender, legal):
    """Board, movesets and the ranked shortlist. Returns the recommendations."""
    print()
    print(render_board(observation))
    for slot, index in enumerate(observation.own_side.active_slots):
        if index is None:
            continue
        mon = observation.own_side.team[index]
        if mon.fainted:
            continue
        print(f"\n  {mon.pokemon_set.species}:")
        print(render_moves(observation, dex, slot))

    advice = recommender.recommend(observation, legal)
    print("\n  Recommended:")
    for entry in advice.recommendations:
        print(f"    {entry.rank}. {entry.description}   {entry.confidence:.0%}")
        for reason in entry.reasons[:3]:
            print(f"         - {reason}")
    if not advice.is_clear:
        print("    (close call: the top two are hard to separate)")
    return advice


def play(
    *,
    team_path: Path | None = None,
    opponent_path: Path | None = None,
    pool_path: Path = DEFAULT_POOL,
    seed: str | None = None,
    auto: bool = False,
) -> int:
    """Run one battle against the heuristic agent. Returns a process exit code."""
    regulation = REGULATION_M_B
    rng = random.Random(seed)

    with ShowdownBridge() as bridge:
        dex = Dex.cached(bridge, DEFAULT_DEX)

        pool = None
        if (team_path is None or opponent_path is None) and pool_path.exists():
            pool = load_pool(bridge, regulation, pool_path)

        if team_path is not None:
            yours = load_team(bridge, regulation, team_path)
        elif pool is not None:
            yours = rng.choice(pool.teams)
        else:
            print(
                f"No team given, and no team pool at {pool_path}.\n"
                "  Pass --team with a Showdown export file, or build a pool from a\n"
                "  local replay corpus with champions_ai.data.harvest."
            )
            return 2

        if opponent_path is not None:
            theirs = load_team(bridge, regulation, opponent_path)
        elif pool is not None:
            theirs = rng.choice(pool.teams)
        else:
            theirs = yours

        env = BattleEnv(regulation, bridge=bridge)
        opponent = HeuristicAgent(dex, name="opponent")
        adviser = HeuristicAgent(dex, name="adviser")
        recommender = Recommender(dex)
        opponent.on_battle_start()

        print(f"\n  You:  {_roster(dex, yours)}")
        print(f"  Them: {_roster(dex, theirs)}")

        result = env.reset((yours, theirs), seed=seed)
        seen = 0

        while not result.terminal:
            waiting = env.awaiting()
            if not waiting:
                break

            choices: dict[int, object] = {}
            chosen_from = None

            for player in waiting:
                if player == 1:
                    if env.decision(1) is Decision.TEAM_PREVIEW:
                        choices[1] = opponent.select_team_preview(
                            env.team_preview(1), regulation.picked_team_size
                        )
                    else:
                        choices[1] = opponent.select_action(
                            env.observation(1), env.legal_actions(1)
                        )
                    continue

                if env.decision(0) is Decision.TEAM_PREVIEW:
                    choices[0] = _choose_team(
                        env.team_preview(0), adviser, dex, regulation, auto=auto
                    )
                    continue

                observation = env.observation(0)
                advice = _show_position(observation, dex, recommender, env.legal_actions(0))

                if auto:
                    print(f"\n  auto: {advice.best.description}")
                    choices[0] = advice.best.action
                    chosen_from = observation
                    continue

                answer = _ask(len(advice.recommendations))
                if answer == "q":
                    print("\n  Stopped.")
                    return 0
                if answer == "a":
                    auto = True
                    choices[0] = advice.best.action
                elif answer.isdigit() and 1 <= int(answer) <= len(advice.recommendations):
                    choices[0] = advice.recommendations[int(answer) - 1].action
                else:
                    print("  Not one of the options, so taking the top recommendation.")
                    choices[0] = advice.best.action
                chosen_from = observation

            if chosen_from is not None and isinstance(choices.get(0), JointAction):
                print(f"\n  You: {describe_joint_action(chosen_from, choices[0], dex=dex)}")

            result = env.step(choices)
            seen = _echo(result.protocol, seen)

        print()
        if result.winner == 0:
            print("  You win.")
        elif result.winner == 1:
            print("  You lose.")
        else:
            print("  No winner recorded.")
        return 0
