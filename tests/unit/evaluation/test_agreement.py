"""Scoring an agent against what a human actually did.

The subtle failures here are all in the comparison itself: a translation bug
between the human's protocol vocabulary and our action types shows up as a
plausible-looking agreement rate, not as a crash.
"""

from champions_ai.agents.base import Agent
from champions_ai.data.choices import ObservedChoice
from champions_ai.data.reconstruct import move_data_from_dex
from champions_ai.domain import MoveAction, SwitchAction, TargetSlot
from champions_ai.evaluation.agreement import (
    action_signature,
    human_signature,
    measure_agreement,
)


class _FirstAction(Agent):
    """Always takes the first legal joint action -- a fixed, boring reference."""

    name = "first"

    def select_action(self, observation, legal_actions):
        return legal_actions[0]


class _Copycat(Agent):
    """Plays whatever the human played, by construction.

    Exists to prove the comparison can reach 100%: if a perfect imitator does
    not score 100%, the metric is broken rather than the agent.
    """

    name = "copycat"

    def __init__(self, decisions, move_data):
        self._wanted = {}
        self._move_data = move_data
        for decision in decisions:
            for choice in decision.choices:
                self._wanted[(decision.turn, choice.player, choice.slot)] = human_signature(
                    choice, move_data
                )

    def select_action(self, observation, legal_actions):
        best, score = legal_actions[0], -1
        for joint in legal_actions:
            matched = 0
            for slot, action in enumerate(joint.slot_actions):
                key = (observation.turn, observation.player, slot)
                signature = action_signature(action, observation, slot, self._move_data)
                if key in self._wanted and signature == self._wanted[key]:
                    matched += 1
            if matched > score:
                best, score = joint, matched
        return best


def _setup(battle):
    return battle.decisions(), move_data_from_dex(battle.dex)


# ------------------------------------------------------ translating the labels


def test_a_targeted_move_keeps_its_target(battle):
    _, move_data = _setup(battle)
    choice = ObservedChoice(
        turn=1, player=0, slot=0, kind="move", actor="Incineroar",
        move="Fake Out", target="p2a: Torkoal",
    )
    assert human_signature(choice, move_data) == ("move", "fakeout", ("foe", 0))


def test_a_target_on_the_acting_players_own_side_reads_as_an_ally(battle):
    _, move_data = _setup(battle)
    choice = ObservedChoice(
        turn=1, player=0, slot=0, kind="move", actor="X",
        move="Fake Out", target="p1b: Garchomp",
    )
    assert human_signature(choice, move_data) == ("move", "fakeout", ("ally", 1))


def test_a_spread_moves_printed_target_is_ignored(battle):
    """Showdown prints a target on spread moves, but the player never chose it.

    Comparing it would make every spread move disagree, since our own action
    for a spread move carries no target at all.
    """
    _, move_data = _setup(battle)
    choice = ObservedChoice(
        turn=1, player=0, slot=0, kind="move", actor="Charizard",
        move="Heat Wave", target="p2a: Incineroar",
    )
    assert human_signature(choice, move_data) == ("move", "heatwave", None)


def test_a_switch_reads_as_its_species(battle):
    _, move_data = _setup(battle)
    choice = ObservedChoice(
        turn=2, player=0, slot=0, kind="switch", actor="Charizard", switched_to="Dragonite",
    )
    assert human_signature(choice, move_data) == ("switch", "dragonite")


def test_an_agents_action_translates_to_the_same_vocabulary(battle):
    decisions, move_data = _setup(battle)
    observation = battle.at(decisions, 1, 0).observation
    charizard = observation.own_side.active_slots[0]
    index = observation.own_side.team[charizard].selectable_moves.index("heatwave")

    move = action_signature(MoveAction(move_index=index), observation, 0, move_data)
    assert move == ("move", "heatwave", None)

    dragonite = next(
        i for i, m in enumerate(observation.own_side.team)
        if m.pokemon_set.species == "Dragonite"
    )
    assert action_signature(
        SwitchAction(team_index=dragonite), observation, 0, move_data
    ) == ("switch", "dragonite")


def test_a_target_is_compared_for_moves_that_actually_take_one(battle):
    """The other half of the spread-move rule: a `normal` move's target counts."""
    decisions, move_data = _setup(battle)
    observation = battle.at(decisions, 3, 0).observation
    slot = observation.own_side.active_slots[0]
    index = observation.own_side.team[slot].selectable_moves.index("dragonclaw")
    signature = action_signature(
        MoveAction(move_index=index, target=TargetSlot(side="foe", slot=1)),
        observation, 0, move_data,
    )
    assert signature == ("move", "dragonclaw", ("foe", 1))


# ------------------------------------------------------------- the measurement


def test_a_perfect_imitator_agrees_completely(battle):
    decisions, move_data = _setup(battle)
    result = measure_agreement(decisions, _Copycat(decisions, move_data), move_data)
    assert result.scored > 0
    assert result.rate == 1.0, result.summary()
    assert result.unscorable == 0


def test_the_random_baseline_is_the_exact_chance_not_a_sample(battle):
    decisions, move_data = _setup(battle)
    result = measure_agreement(decisions, _FirstAction(), move_data)
    # Each comparison's chance is 1/(size of its action set), so the mean must
    # sit strictly inside (0, 1) and never exceed any individual chance of 1.
    assert 0.0 < result.random_baseline < 1.0
    for comparison in result.comparisons:
        assert comparison.random_chance == 1 / comparison.legal_count or comparison.legal_count == 1


def test_agreement_beating_random_requires_the_interval_to_clear_it(battle):
    """A rate above the baseline whose interval still contains it proves nothing."""
    decisions, move_data = _setup(battle)
    result = measure_agreement(decisions, _Copycat(decisions, move_data), move_data)
    assert result.rate > result.random_baseline
    assert result.beats_random == (result.interval[0] > result.random_baseline)


def test_move_only_agreement_is_at_least_full_agreement(battle):
    decisions, move_data = _setup(battle)
    result = measure_agreement(decisions, _FirstAction(), move_data)
    assert result.move_matches >= result.matches


def test_forced_choices_are_excluded_by_default(battle):
    """A replacement after a faint is a decision, but a different one."""
    log = (
        *battle.through("|turn|2"),
        "|move|p2a: Incineroar|Knock Off|p1b: Garchomp",
        "|faint|p1b: Garchomp",
        "|switch|p1b: Dragonite|Dragonite, L50, M|100/100",
        "|turn|3",
    )
    decisions = battle.decisions(log)
    move_data = move_data_from_dex(battle.dex)
    forced = [c for d in decisions for c in d.choices if not c.is_free_choice]
    assert forced, "the fixture must actually contain a forced replacement"

    default = measure_agreement(decisions, _FirstAction(), move_data)
    included = measure_agreement(
        decisions, _FirstAction(), move_data, free_choices_only=False
    )
    assert included.scored + included.unscorable > default.scored + default.unscorable


def test_a_move_missing_from_the_dex_is_counted_not_fatal(battle):
    """Usually a stale dex cache. One bad replay must not kill a batch run.

    Counting it as a miss would blame the agent for a gap in the data, and
    crashing would lose every other replay in the job -- so it is counted and
    named instead.
    """
    log = (
        *battle.through("|turn|1"),
        "|move|p1a: Charizard|Hyper Beam|p2a: Incineroar",
        "|move|p1b: Garchomp|Protect",
        "|turn|2",
    )
    decisions = battle.decisions(log)
    move_data = move_data_from_dex(battle.dex)
    result = measure_agreement(decisions, _FirstAction(), move_data)
    assert result.unscorable >= 1
    assert any("hyperbeam" in example for example in result.unscorable_examples)


def test_an_empty_run_reports_nothing_rather_than_dividing_by_zero(battle):
    move_data = move_data_from_dex(battle.dex)
    result = measure_agreement([], _FirstAction(), move_data)
    assert result.scored == 0
    assert result.rate == 0.0
    assert result.random_baseline == 0.0
    assert not result.beats_random
    assert "0/0" in result.summary()
