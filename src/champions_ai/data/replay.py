"""Human battle replays, as published by Showdown.

The only source of real human decisions this project has, and therefore the
only way to measure the system against something other than agents we wrote
ourselves.

**A replay is the spectator view, not a player's view.** HP is a percentage for
both sides, there are no `|request|` lines, and movesets are unknown until
used. So a replay records what a player *chose*, never what they were choosing
*from*. Anything learned from this is "what a player does given the spectator
view", which is strictly less than the player knew — a limitation to state in
results rather than gloss over.

Reconstruction must also respect time: a replay log contains the whole battle,
so it is trivially easy to leak a later move, or the outcome, backwards into a
decision's features. `AGENTS.md` forbids exactly that.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# `|player|p1|NAME|AVATAR|RATING` -- rating is absent on unrated games.
_PLAYER = re.compile(r"^\|player\|(p[12])\|([^|]*)\|([^|]*)\|(\d*)")


@dataclass(frozen=True)
class ReplayMetadata:
    """Provenance for one replay.

    `AGENTS.md` requires every dataset to record where it came from; this is
    that record for a single battle.
    """

    replay_id: str
    format_id: str
    players: tuple[str, str]
    ratings: tuple[int | None, int | None]
    upload_time: int
    rated: bool

    @property
    def minimum_rating(self) -> int | None:
        """The weaker player's rating -- the honest bar for 'both were strong'."""
        known = [rating for rating in self.ratings if rating is not None]
        return min(known) if len(known) == len(self.ratings) else None

    def is_high_level(self, threshold: int) -> bool:
        """Whether *both* players cleared the bar.

        Deliberately both: a strong player beating a weak one produces a game
        where the strong player's choices were never really tested.
        """
        floor = self.minimum_rating
        return floor is not None and floor >= threshold


@dataclass(frozen=True)
class Replay:
    """A downloaded replay: provenance plus the raw protocol log."""

    metadata: ReplayMetadata
    log: tuple[str, ...] = field(repr=False)

    @property
    def turn_count(self) -> int:
        return sum(1 for line in self.log if line.startswith("|turn|"))

    @property
    def winner(self) -> str | None:
        for line in self.log:
            if line.startswith("|win|"):
                return line.split("|")[2]
        return None

    def lines_before_turn(self, turn: int) -> tuple[str, ...]:
        """Everything visible up to the start of `turn`.

        The guard against leaking the future into a decision: reconstructing
        what a player saw on turn N must not see turn N+1.
        """
        collected: list[str] = []
        for line in self.log:
            if line.startswith("|turn|") and int(line.split("|")[2]) >= turn:
                break
            collected.append(line)
        return tuple(collected)

    @classmethod
    def from_payload(cls, payload: dict) -> "Replay":
        log = tuple(payload.get("log", "").split("\n"))
        return cls(metadata=parse_metadata(payload, log), log=log)

    @classmethod
    def load(cls, path: Path) -> "Replay":
        return cls.from_payload(json.loads(path.read_text(encoding="utf-8")))

    def save(self, path: Path) -> None:
        """Store the raw payload, so reprocessing never needs to refetch."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "id": self.metadata.replay_id,
                    "formatid": self.metadata.format_id,
                    "uploadtime": self.metadata.upload_time,
                    "log": "\n".join(self.log),
                },
                indent=2,
            ),
            encoding="utf-8",
        )


def parse_ratings(log: tuple[str, ...]) -> dict[str, tuple[str, int | None]]:
    """Player names and Elo from the log's `|player|` lines."""
    found: dict[str, tuple[str, int | None]] = {}
    for line in log:
        match = _PLAYER.match(line)
        if match:
            side, name, _avatar, rating = match.groups()
            found[side] = (name, int(rating) if rating else None)
    return found


def parse_metadata(payload: dict, log: tuple[str, ...]) -> ReplayMetadata:
    players = parse_ratings(log)
    p1 = players.get("p1", (None, None))
    p2 = players.get("p2", (None, None))

    listed = payload.get("players") or []
    names = (
        p1[0] or (listed[0] if len(listed) > 0 else ""),
        p2[0] or (listed[1] if len(listed) > 1 else ""),
    )

    return ReplayMetadata(
        replay_id=payload.get("id", ""),
        format_id=payload.get("formatid", ""),
        players=names,
        ratings=(p1[1], p2[1]),
        upload_time=int(payload.get("uploadtime", 0)),
        rated=any(line == "|rated|" or line.startswith("|rated|") for line in log),
    )


# Accounts that are visibly bots. Training on these while calling the result
# "expert play" is a silent quality failure, and the pattern is easy to spot:
# Showdown's ladder bots use generated names with a fixed prefix.
BOT_NAME_PATTERNS = (re.compile(r"^pcrlbot", re.IGNORECASE),)


def looks_like_bot(name: str) -> bool:
    return any(pattern.search(name) for pattern in BOT_NAME_PATTERNS)


def has_human_players(metadata: ReplayMetadata) -> bool:
    return not any(looks_like_bot(name) for name in metadata.players)
