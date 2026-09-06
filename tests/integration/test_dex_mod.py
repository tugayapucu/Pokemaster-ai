"""A cached dex must belong to the regulation that asked for it.

Each Champions regulation is a different Showdown mod with a different roster:
M-B carries 38 species and 31 items that M-A does not. A dex is therefore only
correct for the regulation it was dumped from.

`Dex.cached` used to ignore its `mod` argument entirely whenever the cache file
existed, so asking for one regulation and receiving another's roster was
silent -- every damage number, legality check and species lookup would run
against the wrong data while looking completely healthy. Correctness rested on
somebody remembering to delete a file.
"""

import pytest

from champions_ai.dex import Dex

pytestmark = pytest.mark.integration

REG_M_B = "champions"
REG_M_A = "championsregma"


def test_the_regulations_really_do_have_different_rosters(bridge):
    """If this ever stops being true the rest of the file is measuring nothing."""
    a = Dex.load(bridge, mod=REG_M_A)
    b = Dex.load(bridge, mod=REG_M_B)

    assert len(b.species) > len(a.species)
    assert set(a.species) < set(b.species)


def test_a_dump_records_the_mod_it_came_from(bridge):
    assert Dex.load(bridge, mod=REG_M_A).mod == REG_M_A
    assert Dex.load(bridge, mod=REG_M_B).mod == REG_M_B


def test_asking_for_another_mod_does_not_return_the_cached_one(bridge, tmp_path):
    """The bug. Same path, different regulation: it must re-dump, not reuse."""
    path = tmp_path / "dex.json"

    first = Dex.cached(bridge, path, mod=REG_M_B)
    second = Dex.cached(bridge, path, mod=REG_M_A)

    assert first.mod == REG_M_B
    assert second.mod == REG_M_A
    assert len(second.species) < len(first.species), (
        "the M-A request returned M-B's roster; the cache ignored the mod"
    )


def test_the_same_mod_is_served_from_cache(bridge, tmp_path):
    """The fix must not throw away the cache it exists to provide."""
    path = tmp_path / "dex.json"
    Dex.cached(bridge, path, mod=REG_M_B)
    written = path.stat().st_mtime_ns

    again = Dex.cached(bridge, path, mod=REG_M_B)

    assert again.mod == REG_M_B
    assert path.stat().st_mtime_ns == written, "it re-dumped a cache that was already right"


def test_a_cache_from_before_the_mod_was_recorded_is_not_trusted(bridge, tmp_path):
    """Backwards compatibility, in the safe direction.

    An older cache has no mod. That is unknown rather than matching, so it is
    replaced once instead of being served for a regulation it may not be for.
    """
    path = tmp_path / "dex.json"
    legacy = Dex.load(bridge, mod=REG_M_A).model_copy(update={"mod": ""})
    path.write_text(legacy.model_dump_json(), encoding="utf-8")

    loaded = Dex.cached(bridge, path, mod=REG_M_B)

    assert loaded.mod == REG_M_B
