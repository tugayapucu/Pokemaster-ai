"""Advice for a game being played somewhere else.

`play` runs a battle in our own engine and `review` walks a Showdown replay.
Neither helps during a real game of Pokemon Champions, which has no replay
export, no battle history and no share link -- there is nothing to hand the
replay pipeline, and the game itself is not something this project will touch
(`AGENTS.md` section 3).

What a player does have is the screen. So this asks them to describe it: their
opponent's six at Team Preview, which four they brought, who is out. After that
each turn is a line or two -- `char 55; gambit ko` -- and the same board, the
same ranked shortlist and the same reasons that `play` shows.

The advice is worth what it is worth. Over four candidates the agent picks the
best 57% of the time (0038), so the shortlist is a second opinion with its
reasoning attached, not an oracle.
"""

from pathlib import Path

from champions_ai.agents import HeuristicAgent
from champions_ai.cli.board import show_position
from champions_ai.cli.play import dex_path, load_team
from champions_ai.cli.preview import parse_picks, species_name
from champions_ai.data.reconstruct import move_data_from_dex
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_B, Regulation, legal_joint_actions
from champions_ai.position import Position
from champions_ai.position.commands import HELP, apply_all
from champions_ai.position.names import resolve_species
from champions_ai.position.setup import own_side
from champions_ai.recommendation import Recommender
from champions_ai.simulator import BridgeError, ShowdownBridge


class Stopped(Exception):
    """The player pressed Ctrl-C or Ctrl-D during setup."""


def _ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise Stopped from None


def _ask_their_team(dex: Dex, regulation: Regulation) -> tuple[str, ...]:
    """The six from Team Preview.

    All six, not the four they bring: which four is hidden information, and
    knowing the six is what makes a typed name checkable later.
    """
    size = regulation.min_team_size
    while True:
        answer = _ask(f"\n  Their {size}, as Team Preview shows them > ")
        names = [part for part in answer.replace(",", " ").split() if part]
        if len(names) != size:
            print(f"  Name all {size}, separated by spaces or commas.")
            continue
        try:
            resolved = tuple(resolve_species(dex, name) for name in names)
        except ValueError as error:
            print(f"  {error}")
            continue
        print(f"  Against: {', '.join(species_name(dex, s) for s in resolved)}")
        return resolved


def _ask_our_picks(dex: Dex, team, regulation: Regulation) -> tuple[int, ...]:
    """Which four we brought, in lead order -- the first two start on the field."""
    size = regulation.picked_team_size
    print("\n  Your team:")
    for number, entry in enumerate(team.team.pokemon, start=1):
        print(f"    {number}. {species_name(dex, entry.species)}")
    while True:
        answer = _ask(f"\n  Which {size} did you bring, leads first > ")
        picks = parse_picks(answer, len(team.team.pokemon), size)
        if picks is not None:
            chosen = [species_name(dex, team.team.pokemon[i].species) for i in picks]
            print(f"  Bringing: {', '.join(chosen)}")
            return picks
        print(f"  Give {size} different numbers from 1 to {len(team.team.pokemon)}.")


def _ask_their_leads(dex: Dex, position: Position) -> Position:
    slots = position.regulation.active_slots_per_side
    while True:
        answer = _ask(f"\n  Their {slots} leads > ")
        names = [part for part in answer.replace(",", " ").split() if part]
        if len(names) != slots:
            print(f"  Name {slots}, in the order they are on screen.")
            continue
        try:
            updated = position
            for slot, name in enumerate(names):
                species = resolve_species(dex, name, within=position.their_team)
                updated = updated.with_them_out(slot, species)
            return updated
        except ValueError as error:
            print(f"  {error}")


def _advise(position: Position, dex: Dex, move_data, recommender) -> None:
    """Board, movesets and the shortlist, or an honest account of why not."""
    try:
        observation = position.observation()
    except ValueError as error:
        print(f"\n  That position does not hold together: {error}")
        return
    if all(index is None for index in observation.own_side.active_slots):
        print("\n  Nobody of yours is on the field. Say who with: we <name> <name>")
        return
    try:
        legal = legal_joint_actions(observation, move_data)
    except KeyError as error:
        # A move with no data cannot be scored, and scoring the rest as if it
        # were the whole action space would rank a shortlist that is missing
        # its best entry without saying so.
        print(f"\n  No move data for {error}, so this position cannot be scored.")
        return
    if not legal:
        print("\n  No legal action from here, which usually means a switch is owed.")
        return
    show_position(observation, dex, recommender, legal)


def position(
    *,
    team_path: Path,
    regulation: Regulation = REGULATION_M_B,
) -> int:
    """Advise on a game being played elsewhere. Returns a process exit code."""
    if not team_path.exists():
        print(f"No team at {team_path}. Pass --team with a Showdown export file.")
        return 2

    with ShowdownBridge() as bridge:
        dex = Dex.cached(bridge, dex_path(regulation), mod=regulation.mod)
        try:
            team = load_team(bridge, regulation, team_path)
        except BridgeError as error:
            print(f"\n  {team_path} is not a legal {regulation.name} team.")
            print(f"\n  The engine's objection was:\n    {error}")
            return 2

        move_data = move_data_from_dex(dex)
        recommender = Recommender(dex, agent=HeuristicAgent(dex, name="adviser"))

        print(f"\n  {regulation.name}")
        print(f"  Your team: {team_path}")
        try:
            their_team = _ask_their_team(dex, regulation)
            picks = _ask_our_picks(dex, team, regulation)
            current = Position(
                regulation=regulation,
                own=own_side(bridge, regulation, dex, team, picks),
                their_team=their_team,
            )
            current = _ask_their_leads(dex, current)
        except Stopped:
            print("\n  Stopped.")
            return 0

        print("\n  Ready. Enter shows the board and the recommendation; ? for the commands.")
        history: list[Position] = []
        _advise(current, dex, move_data, recommender)

        while True:
            try:
                line = _ask("\n  > ")
            except Stopped:
                print("  Stopped.")
                return 0

            try:
                outcome = apply_all(current, dex, line)
            except ValueError as error:
                # Refusals are the common case at speed, and the position is
                # left exactly as it was, so this is information rather than a
                # failure.
                print(f"  {error}")
                continue

            if outcome.control == "quit":
                print("  Stopped.")
                return 0
            if outcome.control == "help":
                print(HELP)
                continue
            if outcome.control == "undo":
                if not history:
                    print("  Nothing to undo.")
                    continue
                current = history.pop()
                print("  Undone.")
                _advise(current, dex, move_data, recommender)
                continue

            if outcome.position is not current:
                history.append(current)
                current = outcome.position
            if outcome.message:
                print(f"  {outcome.message}")
            _advise(current, dex, move_data, recommender)
