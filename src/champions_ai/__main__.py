"""Command line entry point.

Until now this project had 1,251 tests, forty experiments and no way to run any
of it. `AGENTS.md` says no polished frontend before the decision engine works;
the engine works and has the measurements to say so, so this is the smallest
thing that makes it usable.
"""

import argparse
import sys
from pathlib import Path

from champions_ai.cli.play import DEFAULT_POOL, play
from champions_ai.cli.regulations import check as check_regulations
from champions_ai.cli.review import DEFAULT_CORPUS, review, survey


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="champions-ai",
        description="Battle assistance for Pokemon Champions, Regulation M-B.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    battle = commands.add_parser(
        "play",
        help="play a battle in the terminal, with a ranked recommendation each turn",
    )
    battle.add_argument(
        "--team", type=Path, default=None,
        help="your team, as a Showdown export file. Defaults to one drawn from the pool.",
    )
    battle.add_argument(
        "--opponent", type=Path, default=None,
        help="the opposing team. Defaults to another drawn from the pool.",
    )
    battle.add_argument(
        "--pool", type=Path, default=DEFAULT_POOL,
        help=f"a file of teams to draw from, separated by '===' (default: {DEFAULT_POOL}).",
    )
    battle.add_argument(
        "--seed", default=None,
        help="fixes both the teams drawn and the battle itself, so a game can be replayed.",
    )
    battle.add_argument(
        "--auto", action="store_true",
        help="take the top recommendation every turn, without asking. Useful for a look.",
    )
    walk = commands.add_parser(
        "review",
        help="walk a real game, showing what a player did against what we would advise",
    )
    walk.add_argument(
        "--corpus", type=Path, default=DEFAULT_CORPUS,
        help=f"directory of collected replays (default: {DEFAULT_CORPUS}).",
    )
    walk.add_argument(
        "--replay", default=None,
        help="which replay, by id or a fragment of one. Defaults to one at random.",
    )
    walk.add_argument(
        "--player", type=int, choices=(0, 1), default=0,
        help="whose decisions to follow (default: 0).",
    )
    walk.add_argument(
        "--disagreements-only", action="store_true",
        help="skip turns where our top recommendation is what they played.",
    )
    walk.add_argument(
        "--limit", type=int, default=0,
        help="stop after this many positions. 0 means the whole game.",
    )
    walk.add_argument(
        "--seed", type=int, default=None,
        help="fixes which replay is drawn when --replay is not given.",
    )
    walk.add_argument(
        "--all", action="store_true",
        help="survey the whole corpus instead of one game: where do we and rated "
             "players systematically differ?",
    )
    walk.add_argument(
        "--replays", type=int, default=0,
        help="with --all, stop after this many replays. 0 means the whole corpus.",
    )
    walk.add_argument(
        "--minimum", type=int, default=40,
        help="with --all, how often an action must appear before it is listed.",
    )
    watch = commands.add_parser(
        "regulations",
        help="has a new Champions regulation appeared upstream yet?",
    )
    watch.add_argument(
        "--all", action="store_true",
        help="list every Champions format, not only the competitive ones.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "play":
        return play(
            team_path=args.team,
            opponent_path=args.opponent,
            pool_path=args.pool,
            seed=args.seed,
            auto=args.auto,
        )
    if args.command == "regulations":
        return check_regulations(competitive_only=not args.all)
    if args.command == "review":
        if args.all:
            return survey(
                corpus_path=args.corpus,
                replay_limit=args.replays,
                minimum=args.minimum,
            )
        return review(
            corpus_path=args.corpus,
            replay_id=args.replay,
            player=args.player,
            disagreements_only=args.disagreements_only,
            limit=args.limit,
            seed=args.seed,
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
