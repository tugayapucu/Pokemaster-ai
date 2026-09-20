"""`champions-ai ui`: the same advice as `position`, driven by buttons.

Same position, same language, same refusals -- the page posts lines that
`position.commands` parses. What it removes is typing: a ladder turn allows
about forty seconds, and most of that went on naming things.

Local only. The server binds the loopback address and holds one game in memory.
"""

import webbrowser
from pathlib import Path

from champions_ai.agents import HeuristicAgent
from champions_ai.cli.play import dex_path, load_team
from champions_ai.data.reconstruct import move_data_from_dex
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_C, Regulation
from champions_ai.position.setup import own_side
from champions_ai.recommendation import Recommender
from champions_ai.simulator import BridgeError, ShowdownBridge
from champions_ai.ui.server import Session, serve


def ui(
    *,
    team_path: Path,
    regulation: Regulation = REGULATION_M_C,
    mega_on_ties: bool = False,
    port: int = 8765,
    open_browser: bool = True,
) -> int:
    """Serve the board on localhost. Returns a process exit code."""
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

        session = Session(
            dex=dex,
            regulation=regulation,
            own_species=[entry.species for entry in team.team.pokemon],
            move_data=move_data_from_dex(dex),
            recommender=Recommender(
                dex, agent=HeuristicAgent(dex, name="adviser", mega_on_ties=mega_on_ties)
            ),
        )
        # Our own side comes from the engine rather than from arithmetic: the
        # stats are exact, with the nature already in them.
        server = serve(session, lambda picks: own_side(bridge, regulation, dex, team, picks),
                       port=port)
        address = f"http://127.0.0.1:{port}"
        print(f"\n  {regulation.name}")
        if mega_on_ties:
            print("  Mega Evolving is ranked first when it ties with not doing so.")
        print(f"  Your team: {team_path}")
        print(f"\n  Board at {address}   (Ctrl-C to stop)")
        if open_browser:
            webbrowser.open(address)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n  Stopped.")
        finally:
            server.server_close()
    return 0
