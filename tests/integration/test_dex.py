"""Reference data pulled from the real engine.

Guards the seam where Showdown's vocabulary meets ours. Hand-copied enums drift
silently: the domain accepted every move target we had thought of, and Champions
turned out to use one more (`allies`, on Howl and Life Dew), which crashed the
tracker on a perfectly ordinary request. A unit test could not have caught it,
because the missing value was missing from the test data too.
"""

from champions_ai.dex import Dex
from champions_ai.domain.move_data import PROTECT_MOVES, STALL_MOVES, MoveData


def test_every_move_target_in_the_dex_is_one_we_accept(bridge):
    dex = Dex.load(bridge)
    unknown = sorted(
        {
            info.target
            for info in dex.moves.values()
            if not _accepted(info.move_id, info.target)
        }
    )
    assert not unknown, f"MoveTargetType is missing target types the engine uses: {unknown}"


def _accepted(move_id: str, target: str) -> bool:
    try:
        MoveData(move_id=move_id, target=target)
    except ValueError:
        return False
    return True


def test_the_dex_actually_loaded(bridge):
    """Guards against the test above passing vacuously on an empty dump."""
    dex = Dex.load(bridge)
    assert len(dex.species) > 100
    assert len(dex.moves) > 100


def test_our_stall_move_list_matches_the_engine(bridge):
    """`STALL_MOVES` is a hand-copied engine fact, so it is checked against one.

    Getting it wrong is silent and reachable: Endure drives the same counter as
    Protect without blocking anything, and omitting it left the agent expecting
    a Protect to succeed where the engine gives it one chance in three.
    """
    dex = Dex.load(bridge)
    engine = {info.move_id for info in dex.moves.values() if info.stalling}
    assert engine, "the dex dump must actually carry the stallingMove flag"

    # Champions has a restricted move pool, so ours may legitimately name moves
    # this regulation omits -- but never the reverse.
    missing = sorted(engine - STALL_MOVES)
    assert not missing, f"STALL_MOVES is missing engine stalling moves: {missing}"


def test_protect_moves_are_stall_moves_that_actually_block(bridge):
    """Endure shares the counter but the hit still lands, so it must not be
    priced as damage avoided."""
    assert PROTECT_MOVES < STALL_MOVES
    assert "endure" not in PROTECT_MOVES
    assert "protect" in PROTECT_MOVES


def test_wide_and_quick_guard_do_not_touch_the_counter(bridge):
    """They protect a category of move and, since Gen 6, may be repeated."""
    dex = Dex.load(bridge)
    for move_id in ("wideguard", "quickguard"):
        assert not dex.get_move(move_id).stalling
        assert move_id not in STALL_MOVES


def test_move_effects_survive_the_dump(bridge):
    """The dump is where move effects were being silently discarded.

    Checked against named moves with known riders rather than by counting,
    because an empty `secondaries` is indistinguishable from a move that has
    none -- the failure this guards is silent by construction.
    """
    dex = Dex.load(bridge)

    nuzzle = dex.get_move("nuzzle")
    assert nuzzle.guaranteed_status == "par", "Nuzzle is 20 BP and always paralyses"

    fakeout = dex.get_move("fakeout")
    assert fakeout.flinch_chance == 1.0
    assert fakeout.priority == 3

    rockslide = dex.get_move("rockslide")
    assert 0 < rockslide.flinch_chance < 1, "Rock Slide flinches sometimes, not always"

    icywind = dex.get_move("icywind")
    assert any(s.boosts.get("spe") == -1 for s in icywind.secondaries)

    assert dex.get_move("drainpunch").drain_fraction == 0.5
    assert 0.3 < dex.get_move("flareblitz").recoil_fraction < 0.35
    # Unconditional, not a rider: Close Combat never rolls for this.
    assert dex.get_move("closecombat").self_boosts == {"def": -1, "spd": -1}


def test_a_plain_move_carries_no_effects(bridge):
    """Guards the test above against passing because everything looks empty.

    Dragon Claw rather than Tackle: Champions has a restricted move pool and
    Tackle is not in it.
    """
    dex = Dex.load(bridge)
    plain = dex.get_move("dragonclaw")
    assert plain.secondaries == ()
    assert plain.drain is None and plain.recoil is None
    assert plain.self_boosts == {}
    assert plain.flinch_chance == 0.0
    assert plain.guaranteed_status is None


def test_cosmetic_formes_resolve_to_their_base_entry(bridge):
    """Furfrou-Debutante has Furfrou's stats to the last point and no entry of
    its own. Before this it raised, and every caller that guarded the KeyError
    silently scored an ordinary team member neutrally on every move.
    """
    dex = Dex.load(bridge)
    assert dex.species_aliases, "the dump must carry cosmeticFormes"

    base = dex.get_species("Furfrou")
    assert dex.get_species("Furfrou-Debutante") is base

    # Every alias must point at an entry that actually exists.
    for forme, target in dex.species_aliases.items():
        assert target in dex.species, f"{forme} aliases missing species {target}"


def test_a_species_outside_the_regulation_still_raises(bridge):
    """Resolution must not turn a genuine gap into a silent default."""
    import pytest

    dex = Dex.load(bridge)
    with pytest.raises(KeyError):
        dex.get_species("Definitely-Not-A-Pokemon")


def test_moves_the_engine_computes_are_flagged_as_dynamic(bridge):
    """Eleven moves carry a zero static base power because the engine works it
    out per hit. Without the flag, `is_damaging` classed them as status moves
    and the heuristic priced Low Kick and Grass Knot as support.
    """
    dex = Dex.load(bridge)
    for move_id in ("lowkick", "grassknot", "gyroball", "heavyslam", "electroball", "flail"):
        move = dex.get_move(move_id)
        assert move.base_power == 0, f"{move_id} should carry no static power"
        assert move.dynamic_power, f"{move_id} must be flagged as computed at run time"
        assert move.is_damaging, f"{move_id} must not read as a status move"


def test_an_ordinary_move_is_not_flagged_as_dynamic(bridge):
    """Guards the test above against passing because everything is flagged."""
    dex = Dex.load(bridge)
    ordinary = dex.get_move("dragonclaw")
    assert ordinary.base_power > 0
    assert not ordinary.dynamic_power
