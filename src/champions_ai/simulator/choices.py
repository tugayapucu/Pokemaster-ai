"""Render domain actions as Showdown choice strings.

The inverse of the tracker: the tracker turns protocol into domain objects,
this turns domain objects back into protocol. Keeping both in the simulator
package means Showdown's wire conventions -- 1-based indices, signed target
slots -- stay out of the domain layer entirely.
"""

from champions_ai.domain import (
    JointAction,
    MoveAction,
    PassAction,
    SlotAction,
    SwitchAction,
    TargetSlot,
    TeamPreviewAction,
)


def format_target(target: TargetSlot) -> str:
    """Showdown numbers foes +1/+2 and allies -1/-2; the domain uses side + 0-based slot."""
    number = target.slot + 1
    return str(number) if target.side == "foe" else str(-number)


def format_slot_action(action: SlotAction) -> str:
    if isinstance(action, PassAction):
        return "pass"
    if isinstance(action, SwitchAction):
        return f"switch {action.team_index + 1}"
    if isinstance(action, MoveAction):
        parts = [f"move {action.move_index + 1}"]
        if action.target is not None:
            parts.append(format_target(action.target))
        if action.special is not None:
            parts.append(action.special)
        return " ".join(parts)
    raise TypeError(f"unrecognised action: {action!r}")


def format_joint_action(action: JointAction) -> str:
    return ", ".join(format_slot_action(slot) for slot in action.slot_actions)


def format_team_preview(action: TeamPreviewAction) -> str:
    return "team " + ", ".join(str(index + 1) for index in action.picks)
