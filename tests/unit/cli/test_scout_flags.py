"""`scout`'s flags, and the defaults they encode.

Two decisions live here rather than in prose. The opponent count defaults to
what the project measured as readable -- a 40-opponent draw once read 57.5%
where the same draw at 120 read 50.8% -- and `--bring` exists because a scout
without it measures the agent's Team Preview as much as the team.

A flag parsed and never forwarded is this project's most repeated bug, so the
pass-through is pinned too.
"""

import pytest

import champions_ai.__main__ as entry
from champions_ai.cli.scout import DEFAULT_OPPONENTS


def test_the_opponent_default_is_the_readable_one():
    args = entry.build_parser().parse_args(["scout", "--team", "team.txt"])
    assert args.opponents == DEFAULT_OPPONENTS == 120


def test_bring_is_empty_unless_asked_for():
    args = entry.build_parser().parse_args(["scout", "--team", "team.txt"])
    assert args.bring == ""


@pytest.mark.parametrize(
    "flags, expected",
    [
        ([], {"opponents": 120, "bring": ""}),
        (["--bring", "torkoal, kingambit, pelipper, rillaboom"],
         {"opponents": 120, "bring": "torkoal, kingambit, pelipper, rillaboom"}),
        (["--opponents", "40"], {"opponents": 40, "bring": ""}),
    ],
)
def test_main_passes_the_flags_to_scout(monkeypatch, flags, expected):
    calls = []
    monkeypatch.setattr(entry, "scout", lambda **kwargs: calls.append(kwargs) or 0)
    assert entry.main(["scout", "--team", "team.txt", *flags]) == 0
    for key, value in expected.items():
        assert calls[0][key] == value
