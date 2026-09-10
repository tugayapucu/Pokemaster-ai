"""Every regulation's `mod` must be the one the installed engine actually uses.

**`champions` is not a fixed dex. It is whichever regulation is current.**
Observed on 2026-09-10:

    mod name          npm 0.11.11        pinned d849b22 (in use)
    champions         Reg M-B            Reg M-C
    championsregma    Reg M-A            deleted upstream
    championsregmb    -                  Reg M-B

So the base mod is rotated: when a regulation ships, it takes over `champions`
and its predecessor is frozen into `championsreg<x>`. `REGULATION_M_B.mod` was
`"champions"`, which was right for 0.11.11 and wrong the moment the rotation
happened -- and wrong *silently*, because the mod name
does not change, only the dex behind it. `Dex.cached` compares mod names, so it
would happily serve a freshly dumped M-C roster to a battle calling itself M-B.

That is the failure this file exists to make loud. It asks the engine what mod
each format really uses and refuses to agree with a hardcoded answer. On the
day someone bumps `pokemon-showdown`, this fails and names the regulation whose
`mod` needs changing, instead of every damage number quietly describing a
different game.
"""

import pytest

from champions_ai.domain import REGULATION_M_B, REGULATION_M_C

pytestmark = pytest.mark.integration

REGULATIONS = (REGULATION_M_B, REGULATION_M_C)


@pytest.fixture(scope="module")
def installed(bridge):
    """What the engine says, keyed by format id."""
    return {entry["id"]: entry for entry in bridge.formats("champions")}


@pytest.mark.parametrize("regulation", REGULATIONS, ids=lambda r: r.format_id)
def test_the_format_exists_in_this_build(regulation, installed):
    """A regulation naming a format the engine does not have cannot be played,
    and `championsregma` did in fact disappear in this
    very upgrade -- so this is not hypothetical."""
    assert regulation.format_id in installed, (
        f"{regulation.name} is not in this build. Champions formats present: "
        f"{', '.join(sorted(installed))}"
    )


@pytest.mark.parametrize("regulation", REGULATIONS, ids=lambda r: r.format_id)
def test_the_mod_is_the_one_the_engine_uses(regulation, installed):
    """The guard.

    If this fails after a dependency bump, the fix is to change that
    regulation's `mod` to what the engine reports -- and to delete every
    `data/dex-*.json` dumped under the old name, because the name is the only
    thing that would still match.
    """
    engine_mod = installed[regulation.format_id]["mod"]
    assert regulation.mod == engine_mod, (
        f"{regulation.name} claims mod {regulation.mod!r} but this build uses "
        f"{engine_mod!r}. The base `champions` mod rotates to whichever "
        f"regulation is current; a stale name here is a wrong dex, silently."
    )


def test_the_game_type_matches_too(installed):
    """Cheap, and the same class of drift: a format switching between singles
    and doubles would change how many slots a side has."""
    for regulation in REGULATIONS:
        assert installed[regulation.format_id]["gameType"] == regulation.game_type


def test_no_two_regulations_share_a_mod(installed):
    """Two sharing one would share a dex cache, and the difference between
    them -- which is the only difference there is -- would vanish."""
    mods = [regulation.mod for regulation in REGULATIONS]
    assert len(set(mods)) == len(mods)
