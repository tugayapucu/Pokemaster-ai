"""Tracker tests driven by hand-written protocol, so they run without Node."""

import pytest

from champions_ai.domain import REGULATION_M_B, PokemonSet, StatSpread, Team
from champions_ai.simulator import BattleTracker, to_id


def _team() -> Team:
    return Team(
        pokemon=tuple(
            PokemonSet(
                species=species,
                level=50,
                ability="someability",
                moves=("tackle", "protect"),
                stats=StatSpread(hp=32, speed=30),
            )
            for species in ("Charizard", "Garchomp", "Incineroar", "Gholdengo")
        )
    )


def _tracker(player: int = 0) -> BattleTracker:
    return BattleTracker(REGULATION_M_B, player=player, own_team=_team())


def _sideline(tracker: BattleTracker, *lines: str) -> None:
    for line in lines:
        tracker.handle({"type": "sideline", "player": tracker.own_tag, "line": line})


def _request(tracker: BattleTracker, request: dict) -> None:
    tracker.handle({"type": "request", "player": tracker.own_tag, "request": request})


def test_to_id_matches_showdown_normalisation():
    assert to_id("Heat Wave") == "heatwave"
    assert to_id("Will-O-Wisp") == "willowisp"
    assert to_id("King's Rock") == "kingsrock"


def test_opponent_switch_registers_species_and_hp():
    tracker = _tracker()
    _sideline(tracker, "|switch|p2a: Incineroar|Incineroar, L50, F|100/100")
    side = tracker.opponent_side()
    assert [mon.species for mon in side.revealed] == ["Incineroar"]
    assert side.revealed[0].hp_percent == 100
    assert side.active_slots[0] == 0


def test_opponent_damage_updates_percentage_only():
    tracker = _tracker()
    _sideline(
        tracker,
        "|switch|p2a: Garchomp|Garchomp, L50, M|100/100",
        "|-damage|p2a: Garchomp|64/100",
    )
    assert tracker.opponent_side().revealed[0].hp_percent == 64


def test_hp_bar_colour_suffix_is_parsed_not_crashed_on():
    tracker = _tracker()
    _sideline(
        tracker,
        "|switch|p2a: Garchomp|Garchomp, L50, M|100/100",
        "|-damage|p2a: Garchomp|20/100y",
    )
    assert tracker.opponent_side().revealed[0].hp_percent == 20


def test_moves_are_revealed_only_once_used():
    tracker = _tracker()
    _sideline(
        tracker,
        "|switch|p2a: Garchomp|Garchomp, L50, M|100/100",
        "|move|p2a: Garchomp|Earthquake|p1a: Charizard",
    )
    assert tracker.opponent_side().revealed[0].revealed_moves == frozenset({"earthquake"})


def test_boosts_accumulate_and_clear_on_switch_out():
    tracker = _tracker()
    _sideline(
        tracker,
        "|switch|p2a: Garchomp|Garchomp, L50, M|100/100",
        "|-boost|p2a: Garchomp|atk|2",
    )
    assert tracker.opponent_side().revealed[0].boosts.attack == 2

    _sideline(
        tracker,
        "|switch|p2a: Incineroar|Incineroar, L50, F|100/100",
        "|switch|p2a: Garchomp|Garchomp, L50, M|100/100",
    )
    assert tracker.opponent_side().revealed[0].boosts.attack == 0


def test_faint_marks_the_pokemon_and_empties_its_slot():
    tracker = _tracker()
    _sideline(
        tracker,
        "|switch|p2a: Garchomp|Garchomp, L50, M|100/100",
        "|faint|p2a: Garchomp",
    )
    side = tracker.opponent_side()
    assert side.revealed[0].fainted
    assert side.active_slots[0] is None


def test_unseen_opponents_stay_a_count():
    tracker = _tracker()
    _sideline(
        tracker,
        "|teamsize|p2|4",
        "|switch|p2a: Garchomp|Garchomp, L50, M|100/100",
    )
    assert tracker.opponent_side().unrevealed_count == 3


def test_our_own_lines_are_not_mistaken_for_the_opponent():
    tracker = _tracker()
    _sideline(tracker, "|switch|p1a: Charizard|Charizard, L50, F|153/153")
    assert tracker.opponent_side().revealed == ()


def test_level_parsing_survives_species_containing_the_letter_l():
    """Splitting details on "L" mangled Lopunny into level "opunny"."""
    tracker = _tracker()
    _sideline(tracker, "|switch|p2a: Lopunny|Lopunny, L50, F|100/100")
    assert tracker.opponent_side().revealed[0].level == 50


def test_level_falls_back_to_the_regulation_when_omitted():
    """Showdown omits the level field entirely at level 100."""
    tracker = _tracker()
    _sideline(tracker, "|switch|p2a: Lugia|Lugia|100/100")
    assert tracker.opponent_side().revealed[0].level == REGULATION_M_B.level


def test_team_preview_roster_parses_levels_too():
    tracker = _tracker()
    _sideline(tracker, "|poke|p2|Lopunny, L50, F|", "|poke|p2|Ludicolo, L50|")
    assert [mon.level for mon in tracker._opponent_roster] == [50, 50]
    assert [mon.species for mon in tracker._opponent_roster] == ["Lopunny", "Ludicolo"]


def test_broken_illusion_corrects_the_species_without_losing_hp():
    """Zoroark switches in disguised, so the species recorded first was wrong.

    `|replace|` carries no HP field, which previously crashed the parser.
    """
    tracker = _tracker()
    _sideline(
        tracker,
        "|switch|p2a: Incineroar|Incineroar, L50, F|100/100",
        "|-damage|p2a: Incineroar|55/100",
        "|replace|p2a: Zoroark|Zoroark-Hisui, L50, F",
    )
    side = tracker.opponent_side()
    species = [mon.species for mon in side.revealed]

    assert "Zoroark-Hisui" in species
    assert "Incineroar" not in species, "the disguise should not linger as a real Pokemon"
    revealed = side.revealed[side.active_slots[0]]
    assert revealed.hp_percent == 55, "the HP belonged to the real Pokemon all along"


def test_replace_to_the_same_species_is_a_no_op():
    tracker = _tracker()
    _sideline(
        tracker,
        "|switch|p2a: Garchomp|Garchomp, L50, M|100/100",
        "|replace|p2a: Garchomp|Garchomp, L50, M",
    )
    assert [mon.species for mon in tracker.opponent_side().revealed] == ["Garchomp"]


def test_mega_evolution_changes_the_tracked_species():
    """Aerodactyl-Mega has different base stats; keeping the base forme would
    make every damage estimate against it wrong for the rest of the battle."""
    tracker = _tracker()
    _sideline(
        tracker,
        "|switch|p2a: Aerodactyl|Aerodactyl, L50, M|100/100",
        "|-damage|p2a: Aerodactyl|60/100",
        "|-mega|p2a: Aerodactyl|Aerodactyl|Aerodactylite",
        "|detailschange|p2a: Aerodactyl|Aerodactyl-Mega, L50, M",
    )
    side = tracker.opponent_side()
    assert [mon.species for mon in side.revealed] == ["Aerodactyl-Mega"]
    assert side.revealed[0].hp_percent == 60, "HP belongs to the same Pokemon"
    assert side.active_slots[0] == 0
    assert side.mega_used


def test_volatile_conditions_start_and_end():
    tracker = _tracker()
    _sideline(
        tracker,
        "|switch|p2a: Garchomp|Garchomp, L50, M|100/100",
        "|-start|p2a: Garchomp|Substitute",
    )
    assert "substitute" in tracker.opponent_side().revealed[0].volatile_conditions

    _sideline(tracker, "|-end|p2a: Garchomp|Substitute")
    assert "substitute" not in tracker.opponent_side().revealed[0].volatile_conditions


def test_protect_is_recorded_as_a_single_turn_effect():
    """Knowing an opponent just protected matters -- consecutive Protects fail."""
    tracker = _tracker()
    _sideline(
        tracker,
        "|switch|p2a: Garchomp|Garchomp, L50, M|100/100",
        "|-singleturn|p2a: Garchomp|Protect",
    )
    assert "protect" in tracker.opponent_side().revealed[0].volatile_conditions


def test_an_activated_ability_reveals_it():
    tracker = _tracker()
    _sideline(
        tracker,
        "|switch|p2a: Garchomp|Garchomp, L50, M|100/100",
        "|-activate|p2a: Garchomp|ability: Rough Skin",
    )
    assert tracker.opponent_side().revealed[0].revealed_ability == "roughskin"


def test_an_activated_item_reveals_it():
    tracker = _tracker()
    _sideline(
        tracker,
        "|switch|p2a: Garchomp|Garchomp, L50, M|100/100",
        "|-activate|p2a: Garchomp|item: Sitrus Berry",
    )
    assert tracker.opponent_side().revealed[0].revealed_item == "sitrusberry"


def test_our_own_forme_change_is_not_applied_to_the_opponent():
    tracker = _tracker()
    _sideline(
        tracker,
        "|switch|p2a: Garchomp|Garchomp, L50, M|100/100",
        "|detailschange|p1a: Charizard|Charizard-Mega-Y, L50, F",
    )
    assert [mon.species for mon in tracker.opponent_side().revealed] == ["Garchomp"]


def test_status_and_cure_are_tracked():
    tracker = _tracker()
    _sideline(
        tracker,
        "|switch|p2a: Garchomp|Garchomp, L50, M|100/100",
        "|-status|p2a: Garchomp|brn",
    )
    assert tracker.opponent_side().revealed[0].status == "brn"
    _sideline(tracker, "|-curestatus|p2a: Garchomp|brn")
    assert tracker.opponent_side().revealed[0].status is None


def test_turn_and_winner_are_tracked():
    tracker = _tracker()
    _sideline(tracker, "|turn|7")
    assert not tracker.finished
    _sideline(tracker, "|win|P2")
    assert tracker.finished
    assert tracker.winner == "P2"


def _move_request(**overrides) -> dict:
    request = {
        "active": [
            {
                "moves": [
                    {"id": "tackle", "pp": 32, "target": "normal", "disabled": False},
                    {"id": "protect", "pp": 8, "target": "self", "disabled": False},
                ],
            }
        ],
        "side": {
            "id": "p1",
            "pokemon": [
                {
                    "ident": "p1: Charizard",
                    "details": "Charizard, L50, F",
                    "condition": "120/153",
                    "active": True,
                    "moves": ["tackle", "protect"],
                    "baseAbility": "blaze",
                    "item": "charizarditey",
                },
                {
                    "ident": "p1: Garchomp",
                    "details": "Garchomp, L50, M",
                    "condition": "183/183",
                    "active": False,
                    "moves": ["tackle", "protect"],
                    "baseAbility": "roughskin",
                    "item": "lifeorb",
                },
            ],
        },
    }
    request.update(overrides)
    return request


def test_own_side_uses_exact_hp_from_the_request():
    tracker = _tracker()
    _request(tracker, _move_request())
    side = tracker.own_side()
    assert side.team[0].current_hp == 120
    assert side.team[0].max_hp == 153
    assert side.active_slots == (0, None)


def test_own_stat_spread_comes_from_the_declared_team():
    """The request never returns Stat Points, so they come from the team we submitted."""
    tracker = _tracker()
    _request(tracker, _move_request())
    assert tracker.own_side().team[0].pokemon_set.stats.hp == 32


def test_move_data_is_learned_from_the_request():
    tracker = _tracker()
    _request(tracker, _move_request())
    data = tracker.move_data
    assert data["tackle"].target == "normal"
    assert data["protect"].target == "self"


def test_disabled_moves_come_from_the_engine():
    request = _move_request()
    request["active"][0]["moves"][0]["disabled"] = True
    tracker = _tracker()
    _request(tracker, request)
    assert tracker.own_side().team[0].disabled_moves == frozenset({"tackle"})


def test_mega_availability_comes_from_the_engine():
    request = _move_request()
    request["active"][0]["canMegaEvo"] = True
    tracker = _tracker()
    _request(tracker, request)
    assert tracker.own_side().team[0].available_specials == frozenset({"mega"})


def test_max_hp_survives_fainting():
    """A fainted Pokemon reports `0 fnt` with no maximum; it must not be lost."""
    tracker = _tracker()
    _request(tracker, _move_request())
    fainted = _move_request()
    fainted["side"]["pokemon"][0]["condition"] = "0 fnt"
    _request(tracker, fainted)
    mon = tracker.own_side().team[0]
    assert mon.current_hp == 0
    assert mon.max_hp == 153


def test_force_switch_slots_are_reported():
    tracker = _tracker()
    _request(tracker, {"forceSwitch": [True, False], "side": _move_request()["side"]})
    assert tracker.force_switch_slots == (True, False)


def test_own_side_before_any_request_is_an_error_not_a_guess():
    with pytest.raises(RuntimeError):
        _tracker().own_side()


def test_rejects_invalid_player():
    with pytest.raises(ValueError):
        BattleTracker(REGULATION_M_B, player=2, own_team=_team())


# ------------------------------------------------------- field and side state


def test_terrain_is_actually_set_from_the_field_lines():
    """`terrain` was declared, read into every Observation and never assigned.

    It sat permanently None, so anything keyed off it -- Rising Voltage's
    doubled base power, the terrain damage bonuses -- could not fire.
    """
    tracker = _tracker()
    _sideline(tracker, "|-fieldstart|move: Electric Terrain|[of] p2a: Pincurchin")
    assert tracker.terrain == "electricterrain"

    _sideline(tracker, "|-fieldend|move: Electric Terrain")
    assert tracker.terrain is None


def test_trick_room_is_a_field_condition_but_not_a_terrain():
    """`-fieldstart` carries Trick Room and Gravity as well, so the tag alone
    does not mean a terrain went up."""
    tracker = _tracker()
    _sideline(tracker, "|-fieldstart|move: Trick Room|[of] p2a: Hatterene")
    assert tracker.terrain is None
    assert "trickroom" in tracker.field_conditions


def test_a_terrain_replacing_another_replaces_it():
    tracker = _tracker()
    _sideline(tracker, "|-fieldstart|move: Grassy Terrain")
    _sideline(tracker, "|-fieldstart|move: Psychic Terrain")
    assert tracker.terrain == "psychicterrain"


def test_a_terrain_ending_does_not_clear_a_different_one():
    """Grassy Terrain expiring after Psychic Terrain replaced it must not
    clear the one that is actually up."""
    tracker = _tracker()
    _sideline(tracker, "|-fieldstart|move: Psychic Terrain")
    _sideline(tracker, "|-fieldend|move: Grassy Terrain")
    assert tracker.terrain == "psychicterrain"


def test_our_own_side_conditions_are_tracked_too():
    """Only the opponent's were recorded, so our own Tailwind -- which doubles
    our Speed and decides the whole turn order -- was invisible to us."""
    tracker = _tracker()
    _sideline(tracker, "|-sidestart|p1: Player 1|move: Tailwind")
    _sideline(tracker, "|-sidestart|p2: Player 2|Reflect")

    assert "tailwind" in tracker._own_side_conditions
    assert "tailwind" not in tracker._opponent_side_conditions
    assert "reflect" in tracker._opponent_side_conditions
    assert "reflect" not in tracker._own_side_conditions


def test_our_own_side_conditions_reach_the_observation():
    tracker = _tracker()
    _sideline(tracker, "|-sidestart|p1: Player 1|move: Tailwind")
    _request(tracker, _move_request())
    assert "tailwind" in tracker.own_side().side_conditions

    _sideline(tracker, "|-sideend|p1: Player 1|move: Tailwind")
    assert "tailwind" not in tracker.own_side().side_conditions


# ------------------------------------------------------------- item knowledge


def test_an_item_that_leaves_is_remembered_as_gone():
    """`revealed_item = None` meant both "never seen one" and "watched it go",
    and only the second says they are empty-handed."""
    tracker = _tracker()
    _sideline(tracker, "|switch|p2a: Incineroar|Incineroar, L50, F|100/100")
    _sideline(tracker, "|-item|p2a: Incineroar|Sitrus Berry")
    seen = tracker.opponent_side().revealed[0]
    assert seen.revealed_item == "sitrusberry"
    assert seen.may_hold_item

    _sideline(tracker, "|-enditem|p2a: Incineroar|Sitrus Berry")
    spent = tracker.opponent_side().revealed[0]
    assert spent.revealed_item is None
    assert spent.item_consumed
    assert not spent.may_hold_item
    assert spent.consumed_item == "sitrusberry", "Recycle needs to know what went"


def test_an_opponent_we_know_nothing_about_may_still_hold_something():
    tracker = _tracker()
    _sideline(tracker, "|switch|p2a: Incineroar|Incineroar, L50, F|100/100")
    fresh = tracker.opponent_side().revealed[0]
    assert fresh.revealed_item is None
    assert not fresh.item_consumed
    assert fresh.may_hold_item


def test_getting_an_item_back_clears_the_consumed_flag():
    """Recycle and Trick both put one back."""
    tracker = _tracker()
    _sideline(tracker, "|switch|p2a: Incineroar|Incineroar, L50, F|100/100")
    _sideline(tracker, "|-enditem|p2a: Incineroar|Sitrus Berry")
    _sideline(tracker, "|-item|p2a: Incineroar|Life Orb")
    back = tracker.opponent_side().revealed[0]
    assert back.revealed_item == "lifeorb"
    assert back.may_hold_item


def test_our_own_single_turn_effects_are_tracked():
    """Recorded for the opponent since `-singleturn` was first handled and
    never for us -- the same shape as the own-boosts bug, and it matters for
    the same reason: our own Roost strips our own Flying type."""
    tracker = _tracker()
    _sideline(tracker, "|-singleturn|p1a: Charizard|move: Roost")
    _request(tracker, _move_request())
    ours = tracker.own_side().team[0]
    assert "roost" in ours.volatile_conditions


def test_our_own_single_turn_effects_expire_at_the_turn_boundary():
    tracker = _tracker()
    _sideline(tracker, "|-singleturn|p1a: Charizard|move: Roost")
    _sideline(tracker, "|turn|3")
    _request(tracker, _move_request())
    assert "roost" not in tracker.own_side().team[0].volatile_conditions


def test_the_last_move_is_recorded_for_the_opponent():
    tracker = _tracker()
    _sideline(
        tracker,
        "|switch|p2a: Landorus|Landorus-Therian, L50, M|100/100",
        "|move|p2a: Landorus|Earthquake|p1a: Charizard",
        "|move|p2a: Landorus|Rock Slide|p1a: Charizard",
    )
    seen = tracker.opponent_side().revealed[0]
    assert seen.revealed_moves == {"earthquake", "rockslide"}
    assert seen.last_move == "rockslide"


def test_the_last_move_is_recorded_for_our_own_side_too():
    """The fourth piece of state that was tracked on one side only, after
    boosts, side conditions and single-turn effects. Instruct repeats an
    *ally's* last move, so ours is not a view concern."""
    tracker = _tracker()
    _sideline(tracker, "|move|p1a: Charizard|Tackle|p2a: Landorus")
    _request(tracker, _move_request())
    assert tracker.own_side().team[0].last_move == "tackle"


def test_the_field_remembers_the_last_move_anyone_used():
    """What Copycat copies: the engine keeps one battle-wide `lastMove`, and
    it happily copies the opponent's."""
    tracker = _tracker()
    _sideline(
        tracker,
        "|move|p1a: Charizard|Tackle|p2a: Landorus",
        "|switch|p2a: Landorus|Landorus-Therian, L50, M|100/100",
        "|move|p2a: Landorus|Earthquake|p1a: Charizard",
    )
    _request(tracker, _move_request())
    assert tracker.observation().last_move_used == "earthquake"


def test_switching_out_forgets_the_last_move():
    tracker = _tracker()
    _sideline(
        tracker,
        "|switch|p2a: Landorus|Landorus-Therian, L50, M|100/100",
        "|move|p2a: Landorus|Earthquake|p1a: Charizard",
        "|switch|p2a: Landorus|Landorus-Therian, L50, M|100/100",
    )
    seen = tracker.opponent_side().revealed[0]
    assert seen.last_move is None
    # ...but we still know it has the move.
    assert "earthquake" in seen.revealed_moves
