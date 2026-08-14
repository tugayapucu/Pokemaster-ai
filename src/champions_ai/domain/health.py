"""Parsing Champions' shared HP readings, including its HP-bar colour quirk.

Showdown's champions mod reports opponent HP as a floored percentage, and at
exactly 20% or 50% appends a colour letter -- those are the thresholds where
the in-game bar changes colour, so the percentage alone is ambiguous there:

    20y  ->  20%, still yellow (above the red threshold)
    20r  ->  20%, already red
    50g  ->  50%, still green
    50y  ->  50%, already yellow

The letter is genuine information a player has from looking at the bar, so it
is preserved rather than discarded. See Pokemon.getHealth() in sim/pokemon.ts.
"""

from typing import Literal, NamedTuple

HpBarColor = Literal["green", "yellow", "red"]

_SUFFIX_COLORS: dict[str, HpBarColor] = {"g": "green", "y": "yellow", "r": "red"}

GREEN_ABOVE = 50
YELLOW_ABOVE = 20


class SharedHealth(NamedTuple):
    """An opponent's HP as reported: a percentage, a bar colour, and fainted-ness."""

    percent: int
    color: HpBarColor | None
    fainted: bool
    status: str | None


class ExactHealth(NamedTuple):
    """Own-side HP, which the engine reports in real points rather than percent."""

    current: int
    maximum: int
    fainted: bool
    status: str | None


def parse_exact_health(condition: str) -> ExactHealth:
    """Parse an own-side `condition` such as `114/153`, `153/153 brn`, or `0 fnt`.

    Kept separate from `parse_shared_health` on purpose: both read the same
    syntax but mean different things, and conflating them would silently treat
    a Pokemon's real HP as a percentage.
    """
    parts = condition.split()
    health = parts[0]
    status = parts[1] if len(parts) > 1 else None

    if health == "0" or status == "fnt":
        return ExactHealth(current=0, maximum=1, fainted=True, status=None)

    current, _, maximum = health.partition("/")
    return ExactHealth(
        current=int(current),
        maximum=int(maximum) if maximum else int(current),
        fainted=False,
        status=status,
    )


def color_for_percent(percent: int) -> HpBarColor:
    """The bar colour implied by a percentage away from the ambiguous thresholds."""
    if percent > GREEN_ABOVE:
        return "green"
    if percent > YELLOW_ABOVE:
        return "yellow"
    return "red"


def parse_shared_health(condition: str) -> SharedHealth:
    """Parse a `condition` field as it appears on the player-visible stream.

    Handles `0 fnt`, `77/100`, `20/100y`, and `56/100 brn`.
    """
    parts = condition.split()
    health = parts[0]
    status = parts[1] if len(parts) > 1 else None

    if health == "0" or status == "fnt":
        return SharedHealth(percent=0, color=None, fainted=True, status=None)

    numerator, _, denominator = health.partition("/")
    suffix = denominator[-1:] if denominator and denominator[-1].isalpha() else ""
    percent = int(numerator)

    color = _SUFFIX_COLORS.get(suffix) or color_for_percent(percent)
    return SharedHealth(percent=percent, color=color, fainted=False, status=status)
