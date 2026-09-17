"""`--mega-on-ties` on `position` and `scout`.

0060 measured `mega_on_ties` as neutral across the pool, so it stays off by
default -- which left the one place it matters most for a player, the shortlist
`position` prints, still hiding a Mega on a Protect turn. The flag makes it
available without changing the default.

The commands themselves need the engine, so these pin the wiring: off unless
asked for, and passed through when it is. A flag parsed and never forwarded is
this project's most repeated bug.
"""

import pytest

import champions_ai.__main__ as entry


@pytest.mark.parametrize("command", ["position", "scout"])
def test_it_is_off_unless_asked_for(command):
    args = entry.build_parser().parse_args([command, "--team", "team.txt"])
    assert args.mega_on_ties is False


@pytest.mark.parametrize("command", ["position", "scout"])
def test_the_flag_turns_it_on(command):
    args = entry.build_parser().parse_args([command, "--team", "team.txt", "--mega-on-ties"])
    assert args.mega_on_ties is True


@pytest.mark.parametrize("command", ["position", "scout"])
@pytest.mark.parametrize("flags, expected", [([], False), (["--mega-on-ties"], True)])
def test_main_passes_it_to_the_command(monkeypatch, command, flags, expected):
    calls = []
    monkeypatch.setattr(entry, command, lambda **kwargs: calls.append(kwargs) or 0)
    assert entry.main([command, "--team", "team.txt", *flags]) == 0
    assert calls[0]["mega_on_ties"] is expected
