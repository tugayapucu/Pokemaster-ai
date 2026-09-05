"""Python side of the Showdown bridge: spawns bridge.js and talks JSON to it.

Deliberately thin. This layer moves bytes and knows nothing about domain types
-- translating Showdown's protocol into BattleState/Observation is a separate
concern, so bridge failures and translation bugs stay distinguishable.
"""

import json
import subprocess
from pathlib import Path
from types import TracebackType

BRIDGE_JS = Path(__file__).with_name("bridge.js")


class BridgeError(RuntimeError):
    """The simulator reported an error, or died."""


class ShowdownBridge:
    """A long-lived Node process running Showdown's battle engine."""

    def __init__(self, node: str = "node", script: Path = BRIDGE_JS) -> None:
        self._node = node
        self._script = script
        self._process: subprocess.Popen[str] | None = None
        self._next_id = 0

    def __enter__(self) -> "ShowdownBridge":
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def start(self) -> None:
        self._process = subprocess.Popen(
            [self._node, str(self._script)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
            cwd=self._script.parent,
        )

    def close(self) -> None:
        if self._process is None:
            return
        try:
            if self._process.poll() is None:
                self._send({"cmd": "quit"})
                self._process.wait(timeout=5)
        except (BrokenPipeError, subprocess.TimeoutExpired):
            self._process.kill()
        finally:
            self._process = None

    def _require_process(self) -> subprocess.Popen[str]:
        if self._process is None or self._process.stdin is None or self._process.stdout is None:
            raise BridgeError("bridge is not running; call start() first")
        return self._process

    def _send(self, command: dict) -> None:
        process = self._require_process()
        assert process.stdin is not None
        process.stdin.write(f"{json.dumps(command)}\n")
        process.stdin.flush()

    def request(self, **command) -> list[dict]:
        """Send one command and collect every event it produced.

        Returns when the bridge acknowledges with a matching sync, so callers
        never have to guess whether more output is coming.
        """
        process = self._require_process()
        assert process.stdout is not None

        self._next_id += 1
        command_id = self._next_id
        self._send({**command, "id": command_id})

        events: list[dict] = []
        while True:
            raw = process.stdout.readline()
            if not raw:
                stderr = process.stderr.read() if process.stderr else ""
                raise BridgeError(f"bridge exited unexpectedly. stderr:\n{stderr}")
            event = json.loads(raw)
            if event.get("type") == "sync" and event.get("id") == command_id:
                return events
            events.append(event)

    def random_team(self, battle_format: str, generator: str | None = None) -> str:
        return self.random_team_pair(battle_format, generator)[0]

    def random_team_pair(
        self,
        battle_format: str,
        generator: str | None = None,
        seed: str | None = None,
    ) -> tuple[str, str]:
        """A legal team as (packed, export text).

        Both forms are returned because only Showdown can convert between them:
        the engine is started from the packed form, and the export form is what
        parses into domain objects.

        `seed` makes the draw reproducible, in the same `sodium,<hex>` shape a
        battle seed takes. Without one the pool differs every run, which is
        fine for a demo and quietly fatal for a measurement -- two runs of the
        same comparison then differ by which teams they happened to draw.
        """
        events = self.request(
            cmd="randomteam", format=battle_format, generator=generator, seed=seed
        )
        for event in events:
            if event["type"] == "team":
                return event["packed"], event.get("exported", "")
        raise BridgeError(f"no team returned: {events}")

    def validate_team(self, battle_format: str, team: str) -> str:
        """Validate an export-format team, returning it packed. Raises with the problems if not."""
        events = self.request(cmd="validateteam", format=battle_format, team=team)
        for event in events:
            if event["type"] == "team":
                return event["packed"]
            if event["type"] == "invalid":
                raise BridgeError("illegal team:\n  " + "\n  ".join(event["problems"]))
        raise BridgeError(f"no validation result: {events}")

    def start_battle(
        self,
        battle_format: str,
        p1_team: str,
        p2_team: str,
        *,
        seed: str | None = None,
        p1_name: str = "P1",
        p2_name: str = "P2",
    ) -> list[dict]:
        return self.request(
            cmd="start",
            format=battle_format,
            seed=seed,
            p1={"name": p1_name, "team": p1_team},
            p2={"name": p2_name, "team": p2_team},
        )

    def choose(self, player: str, choice: str) -> list[dict]:
        return self.request(cmd="choose", player=player, choice=choice)

    def formats(self, match: str | None = None) -> list[dict]:
        """Formats this build of Showdown accepts, optionally filtered by regex.

        Asked of the engine rather than hand-kept, because a hand-kept list of
        engine facts is exactly what drifts -- the same reasoning that put the
        dex behind a dump instead of a table.
        """
        events = self.request(cmd="formats", match=match)
        for event in events:
            if event["type"] == "formats":
                return event["formats"]
        raise BridgeError(f"no format list returned: {events}")

    def reseed(self, seed: str) -> str:
        """Replace the running battle's RNG, returning the seed now in force.

        Replaying a seed and a list of choices reproduces a position exactly,
        which is what makes a fork exact -- and also what would make every
        rollout from that position identical. Reseeding at the branch point is
        what turns one reproduced position into an independent sample of what
        follows it.
        """
        events = self.request(cmd="reseed", seed=seed)
        for event in events:
            if event["type"] == "seed":
                return event["seed"]
        raise BridgeError(f"reseed not acknowledged: {events}")

    def current_seed(self) -> str:
        events = self.request(cmd="seed")
        for event in events:
            if event["type"] == "seed":
                return event["seed"]
        raise BridgeError(f"no seed returned: {events}")
