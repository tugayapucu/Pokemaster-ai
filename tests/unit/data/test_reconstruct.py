"""Rebuilding each player's view at each decision point of a replay.

The tests that matter most here are the ones about *time*: a replay contains
the whole battle, so the easy mistake is to let a later reveal reach backwards
into an earlier decision. Several of these exist purely to catch that.

The sample battle lives in `tests/conftest.py`, shared with the agreement
benchmark.
"""

import pytest

from champions_ai.data.choices import ObservedChoice
from champions_ai.data.reconstruct import move_data_from_dex, reconstruct_decisions
from champions_ai.domain import REGULATION_M_B
from champions_ai.domain.legal_actions import legal_joint_actions
from champions_ai.mechanics.stats import hp_stat

# ------------------------------------------------------------------ the shape


def test_one_decision_per_player_per_turn(battle):
    decisions = battle.decisions()
    assert {(d.turn, d.player) for d in decisions} == {
        (1, 0), (1, 1), (2, 0), (2, 1), (3, 0), (3, 1)
    }


def test_the_choices_made_are_carried_alongside_the_view(battle):
    decision = battle.at(battle.decisions(), 1, 0)
    assert [c.move for c in decision.choices] == ["Heat Wave", "Protect"]
    assert all(isinstance(c, ObservedChoice) for c in decision.choices)
    assert decision.is_free_choice


# ------------------------------------------------------- own knowledge is fair


def test_own_moveset_may_come_from_later_in_the_battle(battle):
    """The player knew their own moves from the start; recovering them is not a leak."""
    turn_one = battle.at(battle.decisions(), 1, 0)
    # Earthquake is not used until turn 2, but it was always on the team sheet.
    assert "earthquake" in battle.own(turn_one, "Garchomp").pokemon_set.moves


def test_own_bench_is_known_before_it_is_ever_sent_out(battle):
    turn_one = battle.at(battle.decisions(), 1, 0)
    dragonite = battle.own(turn_one, "Dragonite")
    assert not dragonite.has_been_active
    assert dragonite.current_hp == dragonite.max_hp


# ------------------------------------------------- opponent knowledge is timed


def test_an_opponent_move_is_hidden_until_the_turn_it_is_used(battle):
    decisions = battle.decisions()
    assert battle.foe(battle.at(decisions, 1, 0), "Incineroar").revealed_moves == frozenset()
    # Fake Out was used during turn 1, so it is known when turn 2 is decided.
    assert "fakeout" in battle.foe(battle.at(decisions, 2, 0), "Incineroar").revealed_moves
    # Knock Off is used *during* turn 2 and must not be visible when deciding it.
    assert "knockoff" not in battle.foe(battle.at(decisions, 2, 0), "Incineroar").revealed_moves
    assert "knockoff" in battle.foe(battle.at(decisions, 3, 0), "Incineroar").revealed_moves


def test_an_opponent_switch_in_is_not_known_early(battle):
    """Dragonite appears for p1 on turn 2; p2 must not see it when deciding turn 1."""
    decisions = battle.decisions()
    with pytest.raises(AssertionError):
        battle.foe(battle.at(decisions, 1, 1), "Dragonite")
    assert battle.foe(battle.at(decisions, 3, 1), "Dragonite").species == "Dragonite"


def test_unseen_opponents_are_only_a_count(battle):
    turn_one = battle.at(battle.decisions(), 1, 0)
    opponent = turn_one.observation.opponent_side
    assert len(opponent.revealed) == 2
    assert opponent.unrevealed_count == REGULATION_M_B.picked_team_size - 2


def test_opponent_damage_is_a_percentage(battle):
    assert battle.foe(battle.at(battle.decisions(), 2, 0), "Incineroar").hp_percent == 70


# --------------------------------------------------------- estimated statistics


def test_own_hp_is_estimated_from_base_stats_and_the_percentage(battle):
    points = REGULATION_M_B.max_total_stat_points // 6
    charizard = battle.own(battle.at(battle.decisions(), 2, 0), "Charizard")
    assert charizard.max_hp == hp_stat(battle.dex.get_species("Charizard").base_stats.hp, points)
    assert charizard.current_hp == round(charizard.max_hp * 82 / 100)


def test_no_stat_point_allocation_is_claimed(battle):
    """Stat Points are never published, so the spread stays empty and the
    estimate lives in computed_stats where it is visibly an estimate."""
    garchomp = battle.own(battle.at(battle.decisions(), 1, 0), "Garchomp")
    assert garchomp.pokemon_set.stats.total == 0
    assert garchomp.computed_stats is not None
    assert "hp" not in garchomp.computed_stats


def test_known_move_counts_expose_how_partial_the_moveset_is(battle):
    turn_one = battle.at(battle.decisions(), 1, 0)
    # Charizard used one move all battle, Garchomp two, Dragonite one.
    assert sorted(turn_one.known_move_counts) == [1, 1, 2]
    assert len(turn_one.known_move_counts) == len(turn_one.observation.own_side.team)


# ------------------------------------------------------------------ edge cases


def test_a_mega_evolution_changes_the_base_stats_used(battle):
    """A Mega'd Pokemon is a different forme with different base stats.

    Keeping the base forme would misestimate every damage figure involving it,
    silently and for the rest of the battle.
    """
    log = (
        *battle.through("|turn|2"),
        "|detailschange|p1a: Charizard|Charizard-Mega-Y, L50, M",
        "|move|p1a: Charizard|Heat Wave|p2a: Incineroar|[spread] p2a,p2b",
        "|turn|3",
        "|move|p1a: Charizard|Heat Wave|p2a: Incineroar|[spread] p2a,p2b",
        "|turn|4",
    )
    decisions = battle.decisions(log)
    base = battle.own(battle.at(decisions, 2, 0), "Charizard")
    mega = battle.own(battle.at(decisions, 3, 0), "Charizard-Mega-Y")
    assert base.computed_stats["spa"] < mega.computed_stats["spa"]


def test_a_turn_nobody_could_act_on_produces_no_decision(battle):
    log = (
        *battle.through("|turn|1"),
        "|cant|p1a: Charizard|par",
        "|move|p2a: Incineroar|Fake Out|p1a: Charizard",
        "|turn|2",
    )
    decisions = battle.decisions(log)
    assert (1, 0) not in {(d.turn, d.player) for d in decisions}
    assert (1, 1) in {(d.turn, d.player) for d in decisions}


def test_a_replay_with_no_turns_yields_nothing(battle):
    assert battle.decisions(("|player|p1|Alice|1|1600", "|start")) == []


def test_reconstruction_accepts_an_explicit_stat_budget(battle):
    """The default budget is a modelling choice, so it has to be overridable."""
    generous = reconstruct_decisions(
        battle.replay(), REGULATION_M_B, battle.dex, points_per_stat=32
    )
    default = battle.decisions()
    assert (
        battle.own(battle.at(generous, 1, 0), "Garchomp").max_hp
        > battle.own(battle.at(default, 1, 0), "Garchomp").max_hp
    )


# ------------------------------------------------- usable by the rest of the system


def test_legal_actions_can_be_generated_from_a_reconstructed_observation(battle):
    """The point of all this: the result has to be something an agent can act on."""
    decision = battle.at(battle.decisions(), 1, 0)
    actions = legal_joint_actions(decision.observation, move_data_from_dex(battle.dex))
    assert actions, "a reconstructed observation must offer at least one legal action"


def test_move_data_covers_every_move_in_the_dex(battle):
    data = move_data_from_dex(battle.dex)
    assert data["heatwave"].target == "allAdjacentFoes"
    assert set(data) == set(battle.dex.moves)
