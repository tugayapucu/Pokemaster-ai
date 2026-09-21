"""The board's forgiving search, and the resolver's "did you mean".

Typing Pokemon names under a clock is where the board was slowest. The search
suggests from a fragment or a typo and the player picks, so the exact id is
what gets sent; the resolver itself still refuses anything unclear, and now
says what it probably was.

The ranking lives in `search.js`, shared by the page, and is checked here
through Node -- the same runtime the simulator bridge needs -- rather than
left untested because it is JavaScript.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from champions_ai.position.names import UnknownName, resolve_species

SEARCH = Path(__file__).resolve().parents[3] / "src" / "champions_ai" / "ui" / "search.js"

SPECIES = [
    {"id": "kingambit", "name": "Kingambit"},
    {"id": "rillaboom", "name": "Rillaboom"},
    {"id": "pelipper", "name": "Pelipper"},
    {"id": "basculegion", "name": "Basculegion"},
    {"id": "mew", "name": "Mew"},
    {"id": "mewtwo", "name": "Mewtwo"},
    {"id": "indeedeef", "name": "Indeedee-F"},
    {"id": "golisopod", "name": "Golisopod"},
    {"id": "absol", "name": "Absol"},
]
MOVES = [
    {"id": "suckerpunch", "name": "Sucker Punch"},
    {"id": "machpunch", "name": "Mach Punch"},
    {"id": "ironhead", "name": "Iron Head"},
]


def _top(query: str, entries) -> list[str]:
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = (
        f"const s = require({json.dumps(str(SEARCH))});"
        f"console.log(JSON.stringify(s.rank({json.dumps(query)}, {json.dumps(entries)})"
        ".map(e => e.name)));"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


@pytest.mark.parametrize(
    "typed, expected",
    [
        ("kingambit", "Kingambit"),   # exact
        ("basc", "Basculegion"),      # start of the name
        ("ambit", "Kingambit"),       # inside it
        ("gmbt", "Kingambit"),        # letters in order, some skipped
        ("rilaboom", "Rillaboom"),    # a letter missing
        ("pellipper", "Pelipper"),    # a letter doubled
        ("kingamibt", "Kingambit"),   # two swapped
        ("asbol", "Absol"),           # neighbours swapped, in a short name
        ("indeedee", "Indeedee-F"),   # a forme, typed without its suffix
    ],
)
def test_a_fragment_or_a_typo_puts_the_right_pokemon_first(typed, expected):
    assert _top(typed, SPECIES)[0] == expected


def test_an_exact_name_beats_a_longer_one_that_starts_with_it():
    """`mew` is Mew. Otherwise the shorter name would be unreachable."""
    assert _top("mew", SPECIES)[:2] == ["Mew", "Mewtwo"]


def test_a_word_inside_a_move_name_reaches_it():
    assert set(_top("punch", MOVES)) == {"Sucker Punch", "Mach Punch"}
    assert _top("sucker", MOVES)[0] == "Sucker Punch"


def test_nothing_typed_suggests_nothing():
    assert _top("", SPECIES) == []


def test_garbage_suggests_nothing_rather_than_something():
    assert _top("zzqx", SPECIES) == []


class _Dex:
    species = {entry["id"]: None for entry in SPECIES}


def test_the_resolver_still_refuses_a_typo_but_names_the_likely_one():
    """The server never guesses: a wrong guess looks healthy afterwards."""
    with pytest.raises(UnknownName, match="Did you mean rillaboom"):
        resolve_species(_Dex(), "rilaboom")


def test_a_refusal_with_nothing_close_offers_nothing():
    with pytest.raises(UnknownName) as refused:
        resolve_species(_Dex(), "zzqx")
    assert "Did you mean" not in str(refused.value)
