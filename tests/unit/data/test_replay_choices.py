"""Recovering human choices from a replay.

Most of these guard against counting something as a chosen action when it was
not one -- the failure mode that would quietly poison a training set.
"""

from champions_ai.data.choices import choices_by_decision, extract_choices


def _log(*lines: str) -> tuple[str, ...]:
    return tuple(lines)


def test_reads_a_move_with_its_target():
    choices = extract_choices(
        _log("|turn|1", "|move|p1a: Aerodactyl|Rock Slide|p2a: Charizard")
    )
    assert len(choices) == 1
    choice = choices[0]
    assert (choice.turn, choice.player, choice.slot) == (1, 0, 0)
    assert choice.kind == "move"
    assert choice.move == "Rock Slide"
    assert choice.target == "p2a: Charizard"
    assert choice.is_free_choice


def test_reads_the_second_slot_in_doubles():
    choices = extract_choices(_log("|turn|1", "|move|p2b: Garchomp|Earthquake|p1a: X"))
    assert (choices[0].player, choices[0].slot) == (1, 1)


def test_a_move_called_by_another_effect_is_not_a_choice():
    """Sleep Talk picked the move, not the player."""
    choices = extract_choices(
        _log("|turn|1", "|move|p1a: X|Tackle|p2a: Y|[from]Sleep Talk")
    )
    assert choices == []


def test_the_opening_leads_are_not_counted_as_switches():
    """Before turn 1 there is nothing to switch out of -- these came from Team
    Preview, and counting them would inflate how often players seem to switch."""
    choices = extract_choices(
        _log(
            "|start",
            "|switch|p1a: Aerodactyl|Aerodactyl, L50, M|100/100",
            "|switch|p1b: Annihilape|Annihilape, L50, F|100/100",
            "|turn|1",
        )
    )
    assert len(choices) == 2
    assert all(choice.lead for choice in choices)
    assert not any(choice.is_free_choice for choice in choices)


def test_a_switch_after_turn_one_is_a_real_switch():
    choices = extract_choices(
        _log("|turn|2", "|switch|p1a: Incineroar|Incineroar, L50, F|100/100")
    )
    assert not choices[0].lead
    assert choices[0].is_free_choice


def test_a_normal_switch_is_a_free_choice():
    choices = extract_choices(
        _log("|turn|3", "|switch|p1a: Incineroar|Incineroar, L50, F|100/100")
    )
    assert choices[0].kind == "switch"
    assert choices[0].switched_to == "Incineroar"
    assert choices[0].is_free_choice


def test_replacing_a_fainted_pokemon_is_marked_forced():
    """Choosing who comes in is a different question from choosing to switch."""
    choices = extract_choices(
        _log(
            "|turn|3",
            "|faint|p1a: Aerodactyl",
            "|switch|p1a: Incineroar|Incineroar, L50, F|100/100",
        )
    )
    assert choices[0].forced
    assert not choices[0].is_free_choice


def test_a_faint_in_the_other_slot_does_not_mark_this_switch_forced():
    choices = extract_choices(
        _log(
            "|turn|3",
            "|faint|p1b: Garchomp",
            "|switch|p1a: Incineroar|Incineroar, L50, F|100/100",
        )
    )
    assert not choices[0].forced


def test_faint_state_does_not_leak_across_turns():
    choices = extract_choices(
        _log(
            "|turn|1",
            "|faint|p1a: Aerodactyl",
            "|turn|2",
            "|switch|p1a: Incineroar|Incineroar, L50, F|100/100",
        )
    )
    assert not choices[0].forced


def test_being_dragged_out_is_not_a_choice():
    """Roar and Whirlwind move a Pokemon its owner did not choose to move."""
    choices = extract_choices(
        _log("|turn|2", "|drag|p1a: Gholdengo|Gholdengo, L50|100/100")
    )
    assert choices == []


def test_a_turn_the_pokemon_could_not_act_is_dropped_entirely():
    """`|cant|` records the failure; the chosen action is unrecoverable."""
    choices = extract_choices(
        _log(
            "|turn|1",
            "|move|p1a: X|Tackle|p2a: Y",
            "|turn|2",
            "|cant|p1a: X|par",
            "|move|p2a: Y|Tackle|p1a: X",
        )
    )
    turns = {(choice.turn, choice.player) for choice in choices}
    assert (2, 0) not in turns, "the blocked player's turn must be dropped"
    assert (2, 1) in turns, "the opponent still made a real choice"
    assert (1, 0) in turns


def test_grouping_produces_one_entry_per_player_per_turn():
    choices = extract_choices(
        _log(
            "|turn|1",
            "|move|p1a: A|Rock Slide|p2a: X",
            "|move|p1b: B|Protect",
            "|move|p2a: X|Heat Wave",
        )
    )
    grouped = choices_by_decision(choices)
    assert len(grouped[(1, 0)]) == 2, "both of our slots acted"
    assert len(grouped[(1, 1)]) == 1


def test_a_move_with_no_target_has_none():
    choices = extract_choices(_log("|turn|1", "|move|p1a: X|Protect"))
    assert choices[0].move == "Protect"
    assert choices[0].target is None


def test_an_empty_log_yields_nothing():
    assert extract_choices(()) == []
