"""Our own side, seeded from the engine rather than recomputed.

The reason this goes through a real battle at all is that Champions' stat
formula is not the mainline one and natures truncate rather than round. A
Pokemon whose Speed is one point out never looks wrong on screen; it just loses
a turn order it should have won. So the numbers come from the engine.

The load-bearing test here is the Mega one. The engine reports which Pokemon
may Mega Evolve only for the two it has on the field, and the Pokemon whose
Mega matters most when deciding a switch is the one on the bench -- so the
bench is derived from the Dex instead. That derivation is checked here against
the engine's own verdict for the Pokemon it does describe, which is the only
place the two are held together.
"""

import pytest

from champions_ai.domain import REGULATION_M_B, Boosts, TeamPreviewAction
from champions_ai.env import BattleEnv
from champions_ai.position.setup import SETUP_SEED, own_side

pytestmark = pytest.mark.integration

PICKS = (0, 1, 2, 3)


@pytest.fixture(scope="module")
def dex(bridge):
    from champions_ai.dex import Dex

    return Dex.load(bridge, mod=REGULATION_M_B.mod)


@pytest.fixture(scope="module")
def engine_side(bridge, mega_team):
    """What the engine itself reports, before any cleaning."""
    env = BattleEnv(REGULATION_M_B, bridge=bridge)
    env.reset((mega_team, mega_team), seed=SETUP_SEED)
    action = TeamPreviewAction(picks=PICKS)
    env.step({0: action, 1: action})
    return env.observation(0).own_side


@pytest.fixture(scope="module")
def side(bridge, dex, mega_team):
    return own_side(bridge, REGULATION_M_B, dex, mega_team, PICKS)


def test_the_four_picked_arrive_in_lead_order(side, mega_team):
    """`picks` is in lead order everywhere else in this project, and a position
    that disagreed would put the wrong Pokemon in the wrong slot."""
    assert len(side.team) == len(PICKS)
    declared = [mega_team.team.pokemon[i].species for i in PICKS]
    assert [mon.pokemon_set.species for mon in side.team] == declared
    assert side.active_slots == (0, 1)


def test_the_stats_are_the_engines_with_the_nature_already_in_them(side):
    """Charizardite Y's holder is Timid: 32 Speed points on base 100 is
    100 + 32 + 20 = 152 neutral, and 152 * 110 // 100 = 167 boosted. Getting
    this from the engine is the entire reason a battle is started."""
    charizard = side.team[0]
    assert charizard.computed_stats is not None
    assert charizard.computed_stats["spe"] == 167
    assert charizard.max_hp == 78 + 0 + 75


def test_the_mirror_battle_leaves_nothing_behind(side):
    """Incineroar's Intimidate fires on the way in and would leave our own lead
    at -1 Attack; the position the player is actually in has none of that."""
    for mon in side.team:
        assert mon.current_hp == mon.max_hp
        assert mon.boosts == Boosts()
        assert mon.status is None
        assert not mon.volatile_conditions
        assert not mon.has_been_active
        assert mon.turns_on_field == 0
    assert side.side_conditions == {}
    assert not side.mega_used


def test_the_dex_derivation_of_mega_agrees_with_the_engine(side, engine_side):
    """The cross-check.

    The engine describes only the Pokemon on the field, so `own_side` derives
    Mega availability from the Dex for all four. If the two ever disagree about
    a Pokemon the engine *does* describe, the derivation is wrong and the bench
    is being told the wrong thing silently.
    """
    described = [i for i, mon in enumerate(engine_side.team) if mon.choosable_moves is not None]
    assert described, "the engine described no active Pokemon; the test proves nothing"
    for index in described:
        assert side.team[index].available_specials == engine_side.team[index].available_specials


def test_a_mega_stone_holder_on_the_bench_is_still_offered_its_mega(bridge, dex, mega_team):
    """The case the derivation exists for: the engine says nothing about the
    bench, and a Pokemon's Mega is exactly what makes it worth switching in."""
    benched = own_side(bridge, REGULATION_M_B, dex, mega_team, (1, 2, 3, 0))
    assert benched.team[3].pokemon_set.species.lower() == "charizard"
    assert benched.team[3].available_specials == frozenset({"mega"})
    assert benched.team[0].available_specials == frozenset()


def test_all_four_are_described_by_the_engine_not_two(side):
    """A battle request describes only the Pokemon on the field, so one battle
    leaves half the team without moves, PP or targets -- and half a team with
    engine data and half without is one position generating legal actions two
    different ways depending on who happened to lead. Rotating the leads and
    asking again is what closes that."""
    for mon in side.team:
        assert mon.choosable_moves == mon.pokemon_set.moves
        assert mon.choosable_move_targets is not None
        assert mon.move_pp is not None
        assert len(mon.move_pp) == len(mon.selectable_moves)


def test_pp_is_the_engines_number_and_not_the_mainline_one(side):
    """**Champions halves the protection moves.** `mods/champions/moves.ts`
    gives Protect `pp: 5` against mainline's 10, and does the same to King's
    Shield, Spiky Shield, Baneful Bunker, Obstruct and Beak Blast -- all of
    them 8 uses after PP-ups rather than 16.

    That is not a detail. Protect is the most-used move in the format, a game
    runs about fifteen turns, and eight uses is a number a player can actually
    reach. Deriving PP from mainline knowledge would have doubled it and never
    looked wrong.
    """
    charizard = side.team[0]
    index = charizard.selectable_moves.index("protect")
    assert charizard.move_pp[index] == 8
    assert all(pp > 0 for pp in charizard.move_pp)


def test_our_pp_is_the_same_pp_the_engine_reported(side, engine_side):
    """The cross-check, in the same shape as the Mega one: for the Pokemon a
    single battle *did* describe, what we kept must be what it said."""
    described = [i for i, mon in enumerate(engine_side.team) if mon.move_pp is not None]
    assert described, "the engine reported no PP; the test proves nothing"
    for index in described:
        assert side.team[index].move_pp == engine_side.team[index].move_pp


def test_bringing_the_wrong_number_is_refused(bridge, dex, mega_team):
    with pytest.raises(ValueError, match="brings 4"):
        own_side(bridge, REGULATION_M_B, dex, mega_team, (0, 1))
