"""A page on localhost that drives a typed position with buttons.

The terminal client is fast to read and slow to type, and a ladder turn allows
about forty seconds. This serves one page that turns the same facts into
buttons; every button sends a line of the language `position.commands` already
parses, so the rules, the refusals and their tests stay in one place and this
layer stays a view.

Local by construction: bound to the loopback address, no authentication, no
state beyond the position in memory. It is a control surface for the person at
the keyboard, not a service.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from champions_ai.domain import Regulation
from champions_ai.position import Position
from champions_ai.position.commands import apply_all
from champions_ai.position.names import resolve_species
from champions_ai.ui.state import advice, board

PAGE = Path(__file__).parent / "index.html"
SEARCH = Path(__file__).parent / "search.js"


class Session:
    """One game being advised: the position, what it came from, and the advice.

    Holds no engine. The caller builds our side once -- which needs the
    simulator, because our own stats are exact and come from it -- and hands it
    in, so everything here is testable without starting one.
    """

    def __init__(self, *, dex, regulation: Regulation, own_species, move_data, recommender):
        self.dex = dex
        self.regulation = regulation
        self.own_species = tuple(own_species)
        self.move_data = move_data
        self.recommender = recommender
        self.position: Position | None = None
        self.history: list[Position] = []
        self.message = ""
        self.lock = threading.Lock()

    # -- setup ---------------------------------------------------------------

    def start(self, *, their_team, picks, leads, own_side) -> None:
        """Team Preview: their six, the four we brought in lead order, their leads."""
        size = self.regulation.min_team_size
        if len(their_team) != size:
            raise ValueError(f"name all {size} of theirs")
        resolved = tuple(resolve_species(self.dex, name) for name in their_team)
        position = Position(regulation=self.regulation, own=own_side, their_team=resolved)
        for slot, name in enumerate(leads):
            position = position.with_them_out(
                slot, resolve_species(self.dex, name, within=resolved)
            )
        self.position = position
        self.history = []
        self.message = f"Turn {position.turn}."
        self.picks = tuple(picks)

    # -- play ----------------------------------------------------------------

    def apply(self, line: str) -> None:
        """One typed line, or one button. Refusals leave the position alone."""
        if self.position is None:
            raise ValueError("the game has not started yet")
        outcome = apply_all(self.position, self.dex, line)
        if outcome.control == "undo":
            self.undo()
            return
        if outcome.position is not self.position:
            self.history.append(self.position)
            self.position = outcome.position
        self.message = outcome.message

    def undo(self) -> None:
        if not self.history:
            self.message = "Nothing to undo."
            return
        self.position = self.history.pop()
        self.message = "Undone."

    # -- reading -------------------------------------------------------------

    def names(self) -> dict:
        """Every species, move and item the dex knows, for the page's search.

        Sent once. The page suggests from these while the player types and sends
        back the exact id they picked, so a typo costs a glance rather than a
        refusal -- or worse, a wrong match.
        """

        def listed(table) -> list[dict]:
            return sorted(
                ({"id": key, "name": getattr(value, "name", key)} for key, value in table.items()),
                key=lambda entry: entry["name"],
            )

        return {
            "species": listed(self.dex.species),
            "moves": listed(self.dex.moves),
            "items": listed(self.dex.items),
        }

    def snapshot(self) -> dict:
        if self.position is None:
            return {
                "ready": False,
                "message": self.message,
                "team": [
                    {"index": index, "species": species}
                    for index, species in enumerate(self.own_species)
                ],
                "picked_team_size": self.regulation.picked_team_size,
                "team_size": self.regulation.min_team_size,
                "slots": self.regulation.active_slots_per_side,
            }
        return {
            "ready": True,
            "message": self.message,
            "can_undo": bool(self.history),
            "board": board(self.position, self.dex),
            "advice": advice(self.position, self.dex, self.move_data, self.recommender),
        }


def _handler(session: Session, build_own_side):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:  # noqa: D102 - quiet by default
            pass

        def _send(self, payload: dict, status: int = 200) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 - the base class names it
            if self.path in ("/", "/index.html"):
                body = PAGE.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path == "/search.js":
                body = SEARCH.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/javascript; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path == "/api/names":
                self._send(session.names())
                return
            if self.path == "/api/state":
                with session.lock:
                    self._send(session.snapshot())
                return
            self._send({"error": "no such page"}, status=404)

        def do_POST(self) -> None:  # noqa: N802 - the base class names it
            length = int(self.headers.get("Content-Length") or 0)
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                self._send({"error": "that was not JSON"}, status=400)
                return
            with session.lock:
                try:
                    if self.path == "/api/start":
                        session.start(
                            their_team=payload.get("their_team", []),
                            picks=payload.get("picks", []),
                            leads=payload.get("leads", []),
                            own_side=build_own_side(tuple(payload.get("picks", []))),
                        )
                    elif self.path == "/api/command":
                        session.apply(payload.get("line", ""))
                    elif self.path == "/api/undo":
                        session.undo()
                    else:
                        self._send({"error": "no such page"}, status=404)
                        return
                except ValueError as error:
                    # A refusal is the common case at speed and leaves the
                    # position untouched, so it is reported beside the board
                    # rather than as a failure.
                    snapshot = session.snapshot()
                    snapshot["refused"] = str(error)
                    self._send(snapshot)
                    return
                self._send(session.snapshot())

    return Handler


def serve(session: Session, build_own_side, *, host: str = "127.0.0.1", port: int = 8765):
    """A server for one player, on the loopback address only."""
    return ThreadingHTTPServer((host, port), _handler(session, build_own_side))
