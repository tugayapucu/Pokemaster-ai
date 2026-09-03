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
    return 1


if __name__ == "__main__":
    sys.exit(main())
