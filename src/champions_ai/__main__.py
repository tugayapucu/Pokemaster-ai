"""Command line entry point.

Until now this project had 1,251 tests, forty experiments and no way to run any
of it. `AGENTS.md` says no polished frontend before the decision engine works;
the engine works and has the measurements to say so, so this is the smallest
thing that makes it usable.
"""

import argparse
import sys
from pathlib import Path

from champions_ai.cli.collect import DEFAULT_CORPUS as COLLECT_CORPUS
from champions_ai.cli.collect import DEFAULT_MIN_RATING, collect
from champions_ai.cli.play import DEFAULT_POOL, play
from champions_ai.cli.position import position
from champions_ai.cli.regulations import check as check_regulations
from champions_ai.cli.review import DEFAULT_CORPUS, review, survey
from champions_ai.domain import REGULATION_M_B, REGULATION_M_C

# Keyed by the short name a person would type. Built from the instances rather
# than a parallel list, so a regulation added to the domain is offered here
# without anyone remembering to update a second place.
REGULATIONS = {
    "m-b": REGULATION_M_B,
    "m-c": REGULATION_M_C,
}
# Frankfurt is Reg M-C, and it is what the live ladder plays.
DEFAULT_REGULATION = "m-c"


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
        "--regulation", choices=sorted(REGULATIONS), default=DEFAULT_REGULATION,
        help=f"which regulation to use (default: {DEFAULT_REGULATION}). Each has its "
             "own dex, so this changes which Pokemon and items exist.",
    )
    battle.add_argument(
        "--seed", default=None,
        help="fixes both the teams drawn and the battle itself, so a game can be replayed.",
    )
    battle.add_argument(
        "--auto", action="store_true",
        help="take the top recommendation every turn, without asking. Useful for a look.",
    )
    gather = commands.add_parser(
        "collect",
        help="download a replay corpus for one format, by format id",
    )
    gather.add_argument(
        "--format", dest="format_id", default=REGULATION_M_B.format_id,
        help="the Showdown format id (default: %(default)s). A raw id rather than "
             "a regulation, so a format this project cannot yet simulate -- a new "
             "one, before its mod is released -- can still be collected for.",
    )
    gather.add_argument(
        "--corpus", type=Path, default=COLLECT_CORPUS,
        help=f"where to write replays and the run manifest (default: {COLLECT_CORPUS}).",
    )
    gather.add_argument(
        "--target", type=int, default=500,
        help="how many usable replays to keep (default: %(default)s).",
    )
    gather.add_argument(
        "--min-rating", type=int, default=DEFAULT_MIN_RATING,
        help="both players must be at least this rated (default: %(default)s). "
             "0 keeps every rating, which is what a ladder in its first days needs "
             "-- and makes the corpus unusable as an agreement signal.",
    )
    advise = commands.add_parser(
        "position",
        help="advise on a game you are playing elsewhere, from a position you type in",
    )
    advise.add_argument(
        "--team", type=Path, required=True,
        help="your team, as a Showdown export file. Required: this advises on your game.",
    )
    advise.add_argument(
        "--regulation", choices=sorted(REGULATIONS), default=DEFAULT_REGULATION,
        help=f"which regulation to use (default: {DEFAULT_REGULATION}). Each has its "
             "own dex, so this changes which Pokemon and items exist.",
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
        "--regulation", choices=sorted(REGULATIONS), default=DEFAULT_REGULATION,
        help=f"which regulation to use (default: {DEFAULT_REGULATION}). Each has its "
             "own dex, so this changes which Pokemon and items exist.",
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
            regulation=REGULATIONS[args.regulation],
        )
    if args.command == "collect":
        return collect(
            format_id=args.format_id,
            corpus_path=args.corpus,
            target=args.target,
            min_rating=args.min_rating or None,
        )
    if args.command == "position":
        return position(
            team_path=args.team,
            regulation=REGULATIONS[args.regulation],
        )
    if args.command == "regulations":
        return check_regulations(competitive_only=not args.all)
    if args.command == "review":
        if args.all:
            return survey(
                corpus_path=args.corpus,
                replay_limit=args.replays,
                minimum=args.minimum,
                regulation=REGULATIONS[args.regulation],
            )
        return review(
            corpus_path=args.corpus,
            replay_id=args.replay,
            player=args.player,
            disagreements_only=args.disagreements_only,
            limit=args.limit,
            seed=args.seed,
            regulation=REGULATIONS[args.regulation],
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
