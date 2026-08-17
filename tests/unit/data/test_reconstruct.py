"""Rebuilding each player's view at each decision point of a replay.

The tests that matter most here are the ones about *time*: a replay contains
the whole battle, so the easy mistake is to let a later reveal reach backwards
into an earlier decision. Several of these exist purely to catch that.
"""

import pytest

from champions_ai.data.choices import ObservedChoice
from champions_ai.data.reconstruct import (
    move_data_from_dex,
    reconstruct_decisions,
)
from champions_ai.data.replay import Replay, ReplayMetadata
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_B
from champions_ai.domain.legal_actions import legal_joint_actions
from champions_ai.mechanics.stats import hp_stat


def _species(name, hp, atk, df, spa, spd, spe, types):
    return {
        "name": name,
        "types": list(types),
        "baseStats": {"hp": hp, "atk": atk, "def": df, "spa": spa, "spd": spd, "spe": spe},
        "abilities": [],
        "weightkg": 1.0,
        "baseSpecies": name,
    }


def _move(name, target, power=80, category="Physical"):
    return {
        "name": name,
        "type": "Normal",
        "category": category,
        "basePower": power,
        "accuracy": 100,
        "priority": 0,
        "target": target,
        "flags": [],
    }


TYPES = ["Normal", "Fire", "Flying", "Dragon", "Ground", "Dark"]

DEX = Dex.from_payload(
    {
        "species": {
            "charizard": _species("Charizard", 78, 84, 78, 109, 85, 100, ("Fire", "Flying")),
            "charizardmegay": _species(
                "Charizard-Mega-Y", 78, 104, 78, 159, 115, 100, ("Fire", "Flying")
            ),
            "garchomp": _species("Garchomp", 108, 130, 95, 80, 85, 102, ("Dragon", "Ground")),
            "dragonite": _species("Dragonite", 91, 134, 95, 100, 100, 80, ("Dragon", "Flying")),
            "incineroar": _species("Incineroar", 95, 115, 90, 80, 90, 60, ("Fire", "Dark")),
            "torkoal": _species("Torkoal", 70, 85, 140, 85, 70, 20, ("Fire",)),
        },
        "moves": {
            "heatwave": _move("Heat Wave", "allAdjacentFoes", category="Special"),
            "protect": _move("Protect", "self", power=0, category="Status"),
            "earthquake": _move("Earthquake", "allAdjacent"),
            "fakeout": _move("Fake Out", "normal"),
            "knockoff": _move("Knock Off", "normal"),
            "dragonclaw": _move("Dragon Claw", "normal"),
        },
        "types": TYPES,
        "chart": {a: dict.fromkeys(TYPES, 1.0) for a in TYPES},
    }
)

# Shaped after a real replay header: `|teamsize|` is emitted *after* Team
# Preview and reports the picked 4, not the declared 6. Verified against a live
# engine battle and against a published replay.
LOG = (
    "|player|p1|Alice|1|1600",
    "|player|p2|Bob|2|1580",
    "|gametype|doubles",
    "|teampreview|4",
    "|teamsize|p1|4",
    "|teamsize|p2|4",
    "|start",
    "|switch|p1a: Charizard|Charizard, L50, M|100/100",
    "|switch|p1b: Garchomp|Garchomp, L50, F|100/100",
    "|switch|p2a: Incineroar|Incineroar, L50, M|100/100",
    "|switch|p2b: Torkoal|Torkoal, L50, F|100/100",
    "|turn|1",
    "|move|p1a: Charizard|Heat Wave|p2a: Incineroar",
    "|-damage|p2a: Incineroar|70/100",
    "|move|p1b: Garchomp|Protect",
    "|move|p2a: Incineroar|Fake Out|p1a: Charizard",
    "|-damage|p1a: Charizard|82/100",
    "|turn|2",
    "|switch|p1a: Dragonite|Dragonite, L50, M|100/100",
    "|move|p1b: Garchomp|Earthquake",
    "|move|p2a: Incineroar|Knock Off|p1b: Garchomp",
    "|turn|3",
    "|move|p1a: Dragonite|Dragon Claw|p2a: Incineroar",
    "|move|p1b: Garchomp|Protect",
    "|move|p2b: Torkoal|Heat Wave",
    "|turn|4",
)


def _through(marker, log=LOG):
    """Everything up to and including `marker` -- sliced by content, not index,
    so inserting a line into LOG does not silently retarget a test."""
    return log[: log.index(marker) + 1]


def _replay(log=LOG):
    return Replay(
        metadata=ReplayMetadata(
            replay_id="test",
            format_id=REGULATION_M_B.format_id,
            players=("Alice", "Bob"),
            ratings=(1600, 1580),
            upload_time=0,
            rated=True,
        ),
        log=log,
    )


def _decisions(log=LOG):
    return reconstruct_decisions(_replay(log), REGULATION_M_B, DEX)


def _at(decisions, turn, player):
    found = [d for d in decisions if d.turn == turn and d.player == player]
    assert found, f"no decision for turn {turn}, player {player}"
    return found[0]


def _own(decision, species):
    for mon in decision.observation.own_side.team:
        if mon.pokemon_set.species == species:
            return mon
    raise AssertionError(f"{species} not on own side")


def _foe(decision, species):
    for mon in decision.observation.opponent_side.revealed:
        if mon.species == species:
            return mon
    raise AssertionError(f"{species} not revealed")


# ------------------------------------------------------------------ the shape


def test_one_decision_per_player_per_turn():
    decisions = _decisions()
    assert {(d.turn, d.player) for d in decisions} == {
        (1, 0), (1, 1), (2, 0), (2, 1), (3, 0), (3, 1)
    }


def test_the_choices_made_are_carried_alongside_the_view():
    decision = _at(_decisions(), 1, 0)
    assert [c.move for c in decision.choices] == ["Heat Wave", "Protect"]
    assert all(isinstance(c, ObservedChoice) for c in decision.choices)
    assert decision.is_free_choice


# ------------------------------------------------------- own knowledge is fair


def test_own_moveset_may_come_from_later_in_the_battle():
    """The player knew their own moves from the start; recovering them is not a leak."""
    turn_one = _at(_decisions(), 1, 0)
    # Earthquake is not used until turn 2, but it was always on the team sheet.
    assert "earthquake" in _own(turn_one, "Garchomp").pokemon_set.moves


def test_own_bench_is_known_before_it_is_ever_sent_out():
    turn_one = _at(_decisions(), 1, 0)
    dragonite = _own(turn_one, "Dragonite")
    assert not dragonite.has_been_active
    assert dragonite.current_hp == dragonite.max_hp


# ------------------------------------------------- opponent knowledge is timed


def test_an_opponent_move_is_hidden_until_the_turn_it_is_used():
    decisions = _decisions()
    assert _foe(_at(decisions, 1, 0), "Incineroar").revealed_moves == frozenset()
    # Fake Out was used during turn 1, so it is known when turn 2 is decided.
    assert "fakeout" in _foe(_at(decisions, 2, 0), "Incineroar").revealed_moves
    # Knock Off is used *during* turn 2 and must not be visible when deciding it.
    assert "knockoff" not in _foe(_at(decisions, 2, 0), "Incineroar").revealed_moves
    assert "knockoff" in _foe(_at(decisions, 3, 0), "Incineroar").revealed_moves


def test_an_opponent_switch_in_is_not_known_early():
    """Dragonite appears for p1 on turn 2; p2 must not see it when deciding turn 1."""
    decisions = _decisions()
    with pytest.raises(AssertionError):
        _foe(_at(decisions, 1, 1), "Dragonite")
    assert _foe(_at(decisions, 3, 1), "Dragonite").species == "Dragonite"


def test_unseen_opponents_are_only_a_count():
    turn_one = _at(_decisions(), 1, 0)
    opponent = turn_one.observation.opponent_side
    assert len(opponent.revealed) == 2
    assert opponent.unrevealed_count == REGULATION_M_B.picked_team_size - 2


def test_opponent_damage_is_a_percentage():
    assert _foe(_at(_decisions(), 2, 0), "Incineroar").hp_percent == 70


# --------------------------------------------------------- estimated statistics


def test_own_hp_is_estimated_from_base_stats_and_the_percentage():
    points = REGULATION_M_B.max_total_stat_points // 6
    charizard = _own(_at(_decisions(), 2, 0), "Charizard")
    assert charizard.max_hp == hp_stat(DEX.get_species("Charizard").base_stats.hp, points)
    assert charizard.current_hp == round(charizard.max_hp * 82 / 100)


def test_no_stat_point_allocation_is_claimed():
    """Stat Points are never published, so the spread stays empty and the
    estimate lives in computed_stats where it is visibly an estimate."""
    garchomp = _own(_at(_decisions(), 1, 0), "Garchomp")
    assert garchomp.pokemon_set.stats.total == 0
    assert garchomp.computed_stats is not None
    assert "hp" not in garchomp.computed_stats


def test_known_move_counts_expose_how_partial_the_moveset_is():
    turn_one = _at(_decisions(), 1, 0)
    # Charizard used one move all battle, Garchomp two, Dragonite one.
    assert sorted(turn_one.known_move_counts) == [1, 1, 2]
    assert len(turn_one.known_move_counts) == len(turn_one.observation.own_side.team)


# ------------------------------------------------------------------ edge cases


def test_a_mega_evolution_changes_the_base_stats_used():
    """A Mega'd Pokemon is a different forme with different base stats.

    Keeping the base forme would misestimate every damage figure involving it,
    silently and for the rest of the battle.
    """
    log = (
        *_through("|turn|2"),
        "|detailschange|p1a: Charizard|Charizard-Mega-Y, L50, M",
        "|move|p1a: Charizard|Heat Wave|p2a: Incineroar",
        "|turn|3",
        "|move|p1a: Charizard|Heat Wave|p2a: Incineroar",
        "|turn|4",
    )
    decisions = reconstruct_decisions(_replay(log), REGULATION_M_B, DEX)
    base = _own(_at(decisions, 2, 0), "Charizard")
    mega = _own(_at(decisions, 3, 0), "Charizard-Mega-Y")
    assert base.computed_stats["spa"] < mega.computed_stats["spa"]


def test_a_turn_nobody_could_act_on_produces_no_decision():
    log = (
        *_through("|turn|1"),
        "|cant|p1a: Charizard|par",
        "|move|p2a: Incineroar|Fake Out|p1a: Charizard",
        "|turn|2",
    )
    decisions = reconstruct_decisions(_replay(log), REGULATION_M_B, DEX)
    assert (1, 0) not in {(d.turn, d.player) for d in decisions}
    assert (1, 1) in {(d.turn, d.player) for d in decisions}


def test_a_replay_with_no_turns_yields_nothing():
    assert _decisions(log=("|player|p1|Alice|1|1600", "|start")) == []


# ------------------------------------------------- usable by the rest of the system


def test_legal_actions_can_be_generated_from_a_reconstructed_observation():
    """The point of all this: the result has to be something an agent can act on."""
    decision = _at(_decisions(), 1, 0)
    actions = legal_joint_actions(decision.observation, move_data_from_dex(DEX))
    assert actions, "a reconstructed observation must offer at least one legal action"


def test_move_data_covers_every_move_in_the_dex():
    data = move_data_from_dex(DEX)
    assert data["heatwave"].target == "allAdjacentFoes"
    assert set(data) == set(DEX.moves)
