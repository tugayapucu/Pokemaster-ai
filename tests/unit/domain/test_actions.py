import pytest
from pydantic import ValidationError

from champions_ai.domain import (
    JointAction,
    MoveAction,
    PassAction,
    SwitchAction,
    TargetSlot,
    TeamPreviewAction,
)


def test_move_action_defaults_to_no_target_and_no_mega():
    action = MoveAction(move_index=0)
    assert action.target is None
    assert action.mega is False


def test_move_action_can_target_a_foe_slot():
    action = MoveAction(move_index=2, target=TargetSlot(side="foe", slot=1))
    assert action.target.side == "foe"
    assert action.target.slot == 1


def test_move_action_rejects_out_of_range_move_index():
    with pytest.raises(ValidationError):
        MoveAction(move_index=4)
    with pytest.raises(ValidationError):
        MoveAction(move_index=-1)


def test_target_slot_rejects_negative_slot():
    with pytest.raises(ValidationError):
        TargetSlot(side="foe", slot=-1)


def test_switch_action_rejects_negative_index():
    with pytest.raises(ValidationError):
        SwitchAction(team_index=-1)


def test_joint_action_accepts_a_normal_doubles_turn():
    joint = JointAction(
        slot_actions=(
            MoveAction(move_index=0, target=TargetSlot(side="foe", slot=0)),
            SwitchAction(team_index=3),
        )
    )
    assert len(joint) == 2


def test_joint_action_rejects_two_slots_switching_to_the_same_pokemon():
    with pytest.raises(ValidationError):
        JointAction(slot_actions=(SwitchAction(team_index=2), SwitchAction(team_index=2)))


def test_joint_action_rejects_two_megas_in_one_turn():
    with pytest.raises(ValidationError):
        JointAction(
            slot_actions=(
                MoveAction(move_index=0, mega=True),
                MoveAction(move_index=1, mega=True),
            )
        )


def test_joint_action_allows_one_mega():
    joint = JointAction(
        slot_actions=(MoveAction(move_index=0, mega=True), MoveAction(move_index=1))
    )
    assert len(joint) == 2


def test_joint_action_rejects_empty():
    with pytest.raises(ValidationError):
        JointAction(slot_actions=())


def test_joint_action_allows_pass_for_an_empty_slot():
    joint = JointAction(slot_actions=(MoveAction(move_index=0), PassAction()))
    assert joint.slot_actions[1].kind == "pass"


def test_joint_action_round_trips_through_json():
    joint = JointAction(
        slot_actions=(
            MoveAction(move_index=1, target=TargetSlot(side="ally", slot=0), mega=True),
            PassAction(),
        )
    )
    restored = JointAction.model_validate_json(joint.model_dump_json())
    assert restored == joint


def test_team_preview_action_keeps_lead_order():
    action = TeamPreviewAction(picks=(3, 0, 5, 1))
    assert action.picks == (3, 0, 5, 1)


def test_team_preview_action_rejects_duplicate_picks():
    with pytest.raises(ValidationError):
        TeamPreviewAction(picks=(0, 1, 1, 2))


def test_team_preview_action_rejects_empty():
    with pytest.raises(ValidationError):
        TeamPreviewAction(picks=())
