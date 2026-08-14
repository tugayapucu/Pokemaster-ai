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
