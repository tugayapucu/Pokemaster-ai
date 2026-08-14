from champions_ai.domain import (
    JointAction,
    MoveAction,
    PassAction,
    SwitchAction,
    TargetSlot,
    TeamPreviewAction,
)
from champions_ai.simulator import format_joint_action, format_slot_action, format_team_preview


def test_move_without_target():
    assert format_slot_action(MoveAction(move_index=0)) == "move 1"


def test_move_indices_become_one_based():
    assert format_slot_action(MoveAction(move_index=3)) == "move 4"


def test_foe_targets_are_positive_and_one_based():
    action = MoveAction(move_index=0, target=TargetSlot(side="foe", slot=1))
    assert format_slot_action(action) == "move 1 2"


def test_ally_targets_are_negative():
    action = MoveAction(move_index=0, target=TargetSlot(side="ally", slot=0))
    assert format_slot_action(action) == "move 1 -1"


def test_special_mechanic_is_appended():
    action = MoveAction(move_index=1, special="mega")
    assert format_slot_action(action) == "move 2 mega"


def test_special_mechanic_follows_the_target():
    action = MoveAction(move_index=0, target=TargetSlot(side="foe", slot=0), special="mega")
    assert format_slot_action(action) == "move 1 1 mega"


def test_switch_and_pass():
    assert format_slot_action(SwitchAction(team_index=2)) == "switch 3"
    assert format_slot_action(PassAction()) == "pass"


def test_joint_action_joins_slots_with_commas():
    joint = JointAction(
        slot_actions=(
            MoveAction(move_index=0, target=TargetSlot(side="foe", slot=0)),
            SwitchAction(team_index=3),
        )
    )
    assert format_joint_action(joint) == "move 1 1, switch 4"


def test_team_preview_uses_one_based_picks_in_order():
    assert format_team_preview(TeamPreviewAction(picks=(3, 0, 5, 1))) == "team 4, 1, 6, 2"
