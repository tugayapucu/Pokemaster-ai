"""Turning what a person types into what the dex calls it.

Typing has to be fast. A player has about forty seconds a turn and is reading
a screen at the same time, so `char` should reach Charizard and `sucker`
should reach Sucker Punch. Guessing wrong is worse than asking, though: a
silently mismatched name puts the wrong Pokemon or the wrong move into the
position, and it looks perfectly healthy afterwards. So this resolves when it
can and refuses when it cannot, and never picks a favourite among equals.

Matching runs in tiers -- exact, then prefix, then substring -- and stops at
the first tier that matches anything. That is what lets an exact name win
outright: `mew` is Mew, even though Mewtwo also starts with it.
"""

from collections.abc import Iterable
from difflib import get_close_matches

from champions_ai.dex import Dex
from champions_ai.dex.reference import to_id

# How many candidates to name back when a fragment is ambiguous. Enough to
# choose from, few enough to read at a glance mid-game.
SHOWN = 6


class UnknownName(ValueError):
    """Nothing matched. Subclasses ValueError so one handler catches both."""


class AmbiguousName(ValueError):
    """Several things matched and none of them outright."""

    def __init__(self, text: str, candidates: tuple[str, ...], kind: str) -> None:
        shown = ", ".join(candidates[:SHOWN])
        extra = f" (+{len(candidates) - SHOWN} more)" if len(candidates) > SHOWN else ""
        super().__init__(f"{text!r} could be {shown}{extra}. Type more of the {kind}.")
        self.candidates = candidates


def _match(text: str, ids: Iterable[str]) -> tuple[str, ...]:
    """Candidate ids for a typed fragment, best tier only."""
    wanted = to_id(text)
    if not wanted:
        return ()
    pool = tuple(ids)
    for tier in (
        [i for i in pool if i == wanted],
        [i for i in pool if i.startswith(wanted)],
        [i for i in pool if wanted in i],
    ):
        if tier:
            return tuple(sorted(tier))
    return ()


def _resolve(text: str, ids: Iterable[str], kind: str) -> str:
    pool = tuple(ids)
    candidates = _match(text, pool)
    if not candidates:
        # A typo gets a suggestion, never an answer: resolving `garchmop` to
        # the nearest name would one day land on the wrong Pokemon without
        # anyone noticing. Naming the closest few costs nothing and turns a
        # dead end into a retype.
        close = get_close_matches(to_id(text), pool, n=3, cutoff=0.6)
        hint = f" Did you mean {', '.join(close)}?" if close else ""
        raise UnknownName(f"no {kind} matches {text!r}.{hint}")
    if len(candidates) > 1:
        raise AmbiguousName(text, candidates, kind)
    return candidates[0]


def resolve_species(dex: Dex, text: str, *, within: Iterable[str] | None = None) -> str:
    """A species id. `within` narrows the search to a known set.

    Narrowing matters more than it looks: resolving an opponent's Pokemon
    against the six they showed at Team Preview makes almost every fragment
    unambiguous, and rules out reaching a species that is not in the game.
    """
    pool = [to_id(name) for name in within] if within is not None else list(dex.species)
    return _resolve(text, pool, "species")


def resolve_move(dex: Dex, text: str, *, within: Iterable[str] | None = None) -> str:
    pool = [to_id(name) for name in within] if within is not None else list(dex.moves)
    return _resolve(text, pool, "move")


def resolve_item(dex: Dex, text: str) -> str:
    return _resolve(text, list(dex.items), "item")
