"""Reference data pulled from the real engine.

Guards the seam where Showdown's vocabulary meets ours. Hand-copied enums drift
silently: the domain accepted every move target we had thought of, and Champions
turned out to use one more (`allies`, on Howl and Life Dew), which crashed the
tracker on a perfectly ordinary request. A unit test could not have caught it,
because the missing value was missing from the test data too.
"""

from champions_ai.dex import Dex
from champions_ai.dex.reference import ADDED_TYPES, EFFECTIVENESS_SUBSTITUTIONS
from champions_ai.domain.move_data import PROTECT_MOVES, STALL_MOVES, MoveData
from champions_ai.mechanics.items import (
    CATEGORY_BOOST_ITEMS,
    EXPERT_BELT,
    LIFE_ORB,
    LIGHT_BALL,
    RESIST_BERRIES,
    SPEED_MULTIPLIERS,
    TYPE_BOOST_ITEMS,
)


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


def test_moves_that_use_a_stat_their_category_does_not_imply(bridge):
    """Body Press, Psyshock and Foul Play read the stat the engine reads.

    Three moves in this dex override the stat their category implies, and the
    engine differential reported Psyshock as consistently under-predicted
    because we defended it with Special Defense.
    """
    dex = Dex.load(bridge)

    body_press = dex.get_move("bodypress")
    assert body_press.category == "Physical"
    assert body_press.offensive_stat == "def", "Body Press swings with Defense"
    assert body_press.defensive_stat == "def"

    psyshock = dex.get_move("psyshock")
    assert psyshock.category == "Special"
    assert psyshock.offensive_stat == "spa"
    assert psyshock.defensive_stat == "def", "Psyshock lands on Defense"

    foul_play = dex.get_move("foulplay")
    assert foul_play.uses_target_offense, "Foul Play swings with the target's Attack"
    assert foul_play.offensive_stat == "atk"


def test_an_ordinary_move_uses_the_stats_its_category_implies(bridge):
    """Guards the test above against passing because everything is overridden."""
    dex = Dex.load(bridge)

    physical = dex.get_move("dragonclaw")
    assert (physical.offensive_stat, physical.defensive_stat) == ("atk", "def")
    assert not physical.uses_target_offense

    special = dex.get_move("shadowball")
    assert (special.offensive_stat, special.defensive_stat) == ("spa", "spd")
    assert not special.uses_target_offense


def test_every_move_the_engine_adjusts_effectiveness_for_has_a_rule(bridge):
    """The rules cannot be dumped, only the fact that one exists.

    `onEffectiveness` is a JavaScript callback, so the two moves that use it in
    this dex are transcribed by hand. This fails the moment a regulation adds a
    third, rather than letting it silently follow the type chart.
    """
    dex = Dex.load(bridge)
    flagged = {m.move_id for m in dex.moves.values() if m.overrides_effectiveness}
    implemented = set(EFFECTIVENESS_SUBSTITUTIONS) | set(ADDED_TYPES)
    assert flagged == {"freezedry", "flyingpress"}
    assert not flagged - implemented, f"no effectiveness rule for {flagged - implemented}"


def test_freeze_dry_is_super_effective_against_water(bridge):
    """An Ice move the chart resists into Water at 0.5x and the engine sends at
    2x -- four times out, and it dominated the differential's residual."""
    dex = Dex.load(bridge)
    freeze_dry = dex.get_move("freezedry")
    slowking = dex.get_species("Slowking")  # Water / Psychic
    assert "Water" in slowking.types
    assert dex.effectiveness(freeze_dry, slowking) == 2.0

    # The substitution replaces only the Water half; the rest of the chart
    # still applies, so an Ice-resistant non-Water type is unaffected.
    charizard = dex.get_species("Charizard")  # Fire / Flying: 0.5x * 2x
    assert dex.effectiveness(freeze_dry, charizard) == 1.0


def test_flying_press_applies_flying_on_top_of_fighting(bridge):
    dex = Dex.load(bridge)
    flying_press = dex.get_move("flyingpress")
    chart = dex.type_chart

    venusaur = dex.get_species("Venusaur")  # Grass / Poison
    assert dex.effectiveness(flying_press, venusaur) == (
        chart.effectiveness("Fighting", venusaur.types)
        * chart.effectiveness("Flying", venusaur.types)
    )

    # Ghost is immune to the Fighting half, and nothing the Flying half adds
    # can bring that back above zero.
    gengar = dex.get_species("Gengar")
    assert dex.effectiveness(flying_press, gengar) == 0.0


def test_an_ordinary_move_still_follows_the_chart(bridge):
    dex = Dex.load(bridge)
    move = dex.get_move("icebeam")
    slowking = dex.get_species("Slowking")
    assert dex.effectiveness(move, slowking) == dex.type_chart.effectiveness(
        "Ice", slowking.types
    )


def test_every_item_we_model_exists_in_this_dex(bridge):
    """The multipliers are hand-transcribed from the engine's `items.ts`, so
    the ids are the part that can silently rot.

    A typo, or a regulation dropping an item, would make the entry simply
    never match -- no error, just a multiplier that stops applying. This is
    the same guard as the effectiveness overrides and for the same reason.
    """
    dex = Dex.load(bridge)
    modelled = (
        set(TYPE_BOOST_ITEMS)
        | set(CATEGORY_BOOST_ITEMS)
        | set(RESIST_BERRIES)
        | set(SPEED_MULTIPLIERS)
        | {LIFE_ORB, EXPERT_BELT, LIGHT_BALL}
    )
    missing = sorted(item for item in modelled if item not in dex.items)
    assert not missing, f"modelled items absent from this dex: {missing}"


def test_the_type_boosting_items_cover_every_type_exactly_once(bridge):
    """Eighteen items, eighteen types, no duplicates -- which is what makes a
    missing one detectable at all."""
    dex = Dex.load(bridge)
    # Stellar exists only as a Tera type: no move has it, so it has neither a
    # boosting item nor a berry.
    real_types = set(dex.types) - {"Stellar"}
    covered = sorted(TYPE_BOOST_ITEMS.values())
    assert len(covered) == len(set(covered)), "two items claim the same type"
    assert set(covered) == real_types
    assert set(RESIST_BERRIES.values()) == real_types


def test_the_items_we_rely_on_being_absent_really_are(bridge):
    """Choice Band and friends are not in Champions. If a regulation adds one,
    the table here is silently incomplete rather than wrong, so this fails to
    say so.
    """
    dex = Dex.load(bridge)
    for absent in ("choiceband", "choicespecs", "assaultvest", "eviolite"):
        assert absent not in dex.items, f"{absent} is now legal and unmodelled"


def test_the_fixed_damage_moves_do_not_read_as_status_moves(bridge):
    """Nine moves here bypass the damage formula, and all nine carry a zero
    base power with no `basePowerCallback` -- so `is_damaging` classed every
    one as a status move and the heuristic scored them as support."""
    dex = Dex.load(bridge)
    for move_id in (
        "seismictoss", "nightshade", "superfang", "endeavor", "finalgambit",
        "counter", "mirrorcoat", "metalburst", "comeuppance",
    ):
        move = dex.get_move(move_id)
        assert move.base_power == 0, f"{move_id} should carry no static power"
        assert move.deals_fixed_damage, f"{move_id} must be flagged"
        assert move.is_damaging, f"{move_id} must not read as a status move"


def test_an_ordinary_move_deals_no_fixed_damage(bridge):
    """Guards the test above against passing because everything is flagged."""
    dex = Dex.load(bridge)
    assert not dex.get_move("dragonclaw").deals_fixed_damage
    assert not dex.get_move("protect").deals_fixed_damage
