"""The regulation watch, including the case it exists for.

A detector that has only ever been run while there is nothing to detect has not
been tested. These feed it a format it does not know about and require it to
say so, because the day it matters is the day nobody is watching the output
closely.

The three exit codes carry the meaning, so they are pinned:

  0  nothing upstream that the installed build lacks
  1  something new is upstream
  2  could not tell -- and that is deliberately not 0
"""

import champions_ai.cli.regulations as module
from champions_ai.cli.regulations import _slug

KNOWN = """
    name: "[Gen 9 Champions] VGC 2026 Reg M-A",
    name: "[Gen 9 Champions] VGC 2026 Reg M-B",
"""
WITH_NEW = KNOWN + '    name: "[Gen 9 Champions] VGC 2026 Reg M-Q",\n'

INSTALLED = [
    {"id": "gen9championsvgc2026regma", "name": "[Gen 9 Champions] VGC 2026 Reg M-A",
     "mod": "championsregma", "gameType": "doubles"},
    {"id": "gen9championsvgc2026regmb", "name": "[Gen 9 Champions] VGC 2026 Reg M-B",
     "mod": "champions", "gameType": "doubles"},
]


class _Bridge:
    def __init__(self, formats=INSTALLED):
        self._formats = formats

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def formats(self, match=None):
        return self._formats


def _run(monkeypatch, upstream, installed=INSTALLED, npm='{"version": "0.11.11"}'):
    monkeypatch.setattr(module, "ShowdownBridge", lambda: _Bridge(installed))
    monkeypatch.setattr(
        module, "_fetch",
        lambda url: upstream if "githubusercontent" in url else npm,
    )
    return module.check()


def test_the_id_is_derived_the_way_showdown_derives_it():
    """Lowercase, drop everything not alphanumeric. If this is wrong, a known
    format looks new and the watch cries wolf on every run."""
    assert _slug("[Gen 9 Champions] VGC 2026 Reg M-B") == "gen9championsvgc2026regmb"
    assert _slug("[Gen 9 Champions] VGC 2026 Reg M-A (Bo3)") == "gen9championsvgc2026regmabo3"


def test_nothing_new_reports_nothing_new(monkeypatch, capsys):
    assert _run(monkeypatch, KNOWN) == 0
    assert "Nothing upstream" in capsys.readouterr().out


def test_a_format_upstream_that_is_not_installed_is_reported(monkeypatch, capsys):
    """The case the whole thing exists for."""
    assert _run(monkeypatch, WITH_NEW) == 1
    out = capsys.readouterr().out
    assert "Reg M-Q" in out
    assert "NEW" in out


def test_it_says_what_it_does_not_know(monkeypatch, capsys):
    """It reports a name and availability. It must not imply anything about
    the regulation's dex, rules or metagame, because it inspects none of them."""
    _run(monkeypatch, WITH_NEW)
    out = capsys.readouterr().out
    assert "does NOT tell you" in out
    assert "dex" in out


def test_unreachable_upstream_is_not_reported_as_nothing_new(monkeypatch, capsys):
    """Absence of evidence. Returning 0 here would let a silent network
    failure read as 'no new regulation' for as long as it lasted."""
    assert _run(monkeypatch, None) == 2
    out = capsys.readouterr().out.lower()
    assert "unreachable" in out
    assert "nothing is concluded" in out


def test_an_unparseable_upstream_file_is_also_not_nothing_new(monkeypatch, capsys):
    """Showdown may restructure `formats.ts`. Parsing zero names out of a file
    that downloaded fine is a reason to look, not a reason to relax."""
    assert _run(monkeypatch, "// no formats here at all") == 2
    assert "may have changed" in capsys.readouterr().out


def test_it_survives_the_simulator_being_unavailable(monkeypatch, capsys):
    """Reporting upstream is still useful without a working local sim."""
    def explode():
        raise RuntimeError("node is not installed")

    monkeypatch.setattr(module, "ShowdownBridge", explode)
    monkeypatch.setattr(
        module, "_fetch",
        lambda url: KNOWN if "githubusercontent" in url else '{"version": "0.11.11"}',
    )

    # Every upstream format is unknown when nothing is installed.
    assert module.check() == 1
    assert "could not ask the local simulator" in capsys.readouterr().out
