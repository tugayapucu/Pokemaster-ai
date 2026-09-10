"""A cached dex must belong to the regulation that asked for it.

Each Champions regulation is a different Showdown mod with a different roster:
M-C carries 35 species and 18 items that M-B does not. A dex is therefore only
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

# Named for what they are in the pinned build. `champions` is the *current*
# regulation, which is M-C here; M-B has been frozen into `championsregmb`.
REG_M_C = "champions"
REG_M_B = "championsregmb"


def test_the_regulations_really_do_have_different_rosters(bridge):
    """If this ever stops being true the rest of the file is measuring nothing.

    The direction matters and it flipped with M-C. M-A was a *subset* of M-B;
    M-C is a strict *superset* of M-B -- 35 species added and none taken away.
    So this asserts the containment rather than a bare size difference, which
    would pass either way round.
    """
    newer = Dex.load(bridge, mod=REG_M_C)
    older = Dex.load(bridge, mod=REG_M_B)

    assert len(newer.species) > len(older.species)
    assert set(older.species) < set(newer.species)


def test_a_dump_records_the_mod_it_came_from(bridge):
    assert Dex.load(bridge, mod=REG_M_C).mod == REG_M_C
    assert Dex.load(bridge, mod=REG_M_B).mod == REG_M_B


def test_asking_for_another_mod_does_not_return_the_cached_one(bridge, tmp_path):
    """The bug. Same path, different regulation: it must re-dump, not reuse."""
    path = tmp_path / "dex.json"

    first = Dex.cached(bridge, path, mod=REG_M_B)
    second = Dex.cached(bridge, path, mod=REG_M_C)

    assert first.mod == REG_M_B
    assert second.mod == REG_M_C
    assert len(second.species) > len(first.species), (
        "the M-C request returned M-B's roster; the cache ignored the mod"
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
    legacy = Dex.load(bridge, mod=REG_M_C).model_copy(update={"mod": ""})
    path.write_text(legacy.model_dump_json(), encoding="utf-8")

    loaded = Dex.cached(bridge, path, mod=REG_M_B)

    assert loaded.mod == REG_M_B
