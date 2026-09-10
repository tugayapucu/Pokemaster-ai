"""Where a regulation's dex is cached, and what happens when a pool is wrong.

Two things worth pinning. The dex path has to be per-mod, because a single
shared `data/dex.json` is what let a cached M-B dex be served to an M-A battle
without anyone noticing. And a pool harvested from one regulation's replays is
not legal in another, which is correct but used to surface as a traceback.
"""

from pathlib import Path

import champions_ai.cli.play as module
from champions_ai.cli.play import dex_path
from champions_ai.domain import REGULATION_M_B, REGULATION_M_C
from champions_ai.simulator import BridgeError


def test_each_mod_caches_its_own_dex():
    """The bug this shape prevents: one file, two dexes, last writer wins."""
    assert dex_path(REGULATION_M_C) != dex_path(REGULATION_M_B)


def test_the_path_is_named_for_the_mod_not_the_regulation():
    """Two regulations sharing a mod share a dex, and should share the cache
    rather than re-dumping the same data under two names."""
    assert dex_path(REGULATION_M_B) == Path("data/dex-championsregmb.json")
    assert dex_path(REGULATION_M_C, Path("elsewhere")) == Path(
        "elsewhere/dex-champions.json"
    )


class _Bridge:
    """A bridge that rejects every team, the way it does for a pool harvested
    from a different regulation's replays."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def validate_team(self, format_id, text):
        raise BridgeError("illegal team:\n  Staraptor (Staraptor-Mega) does not exist in Gen 9.")


class _Dex:
    @staticmethod
    def cached(*args, **kwargs):
        return None


def test_a_pool_from_another_regulation_is_explained_not_raised(monkeypatch, capsys, tmp_path):
    """Refusing is right -- the alternative is playing a different game than
    the one asked for -- but the refusal has to say why, and say which
    regulation and which file, because the fix is to change one of the two."""
    monkeypatch.setattr(module, "ShowdownBridge", _Bridge)
    monkeypatch.setattr(module, "Dex", _Dex)
    pool = tmp_path / "pool-eval.txt"
    pool.write_text("Staraptor-Mega @ Staraptorite\n", encoding="utf-8")

    assert module.play(pool_path=pool, regulation=REGULATION_M_C) == 2

    out = capsys.readouterr().out
    assert "pool-eval.txt" in out
    assert REGULATION_M_C.name in out
    assert "--team" in out
    # The engine's own words, not a paraphrase: the species it objected to is
    # the one piece of information that says which team to drop.
    assert "Staraptor" in out
