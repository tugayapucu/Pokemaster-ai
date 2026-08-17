"""Turn actions into something a player can read.

`move 1 -1` is meaningful to the engine and useless to a human. A
recommendation that cannot be read cannot be judged, so this resolves indices
against the observation and the dex: which move, aimed at which Pokemon, and
which Pokemon is being switched in.
"""

from champions_ai.dex import Dex
from champions_ai.domain import (
    JointAction,
    Observation,
    PassAction,
    SlotAction,
    SwitchAction,
    TargetSlot,
)


def describe_target(
    observation: Observation, target: TargetSlot | None, *, dex: Dex | None = None
) -> str:
    """Name the Pokemon in a targeted slot, saying whose it is.

    The side prefix is not decoration: mirror matches are common, and
    "Flamethrower -> Charizard" is unreadable when both players field one.
    """
    if target is None:
        return ""

    if target.side == "ally":
        side = observation.own_side
        if target.slot < len(side.active_slots):
            index = side.active_slots[target.slot]
            if index is not None:
                return f"your {side.team[index].pokemon_set.species}"
        return f"your slot {target.slot + 1}"

    opponent = observation.opponent_side
    if target.slot < len(opponent.active_slots):
        index = opponent.active_slots[target.slot]
        if index is not None:
            return f"the opposing {opponent.revealed[index].species}"
    return f"opposing slot {target.slot + 1}"


def describe_slot_action(
    observation: Observation, slot: int, action: SlotAction, *, dex: Dex | None = None
) -> str:
    """One slot's choice in words."""
    if isinstance(action, PassAction):
        return "pass"

    index = observation.own_side.active_slots[slot]

    if isinstance(action, SwitchAction):
        if action.team_index < len(observation.own_side.team):
            incoming = observation.own_side.team[action.team_index]
            return f"switch to {incoming.pokemon_set.species}"
        return f"switch to slot {action.team_index + 1}"

    if index is None:
        return f"move {action.move_index + 1}"

    moves = observation.own_side.team[index].selectable_moves
    move_id = moves[action.move_index] if action.move_index < len(moves) else None
    name = move_id or f"move {action.move_index + 1}"
    if dex is not None and move_id is not None:
        try:
            name = dex.get_move(move_id).name
        except KeyError:
            pass

    target = describe_target(observation, action.target, dex=dex)
    if target:
        name = f"{name} -> {target}"
    if action.special is not None:
        name = f"{name} (+{action.special})"
    return name


def describe_joint_action(
    observation: Observation, action: JointAction, *, dex: Dex | None = None
) -> str:
    """A whole turn's choice, one clause per slot, each naming its Pokemon."""
    parts = []
    for slot, slot_action in enumerate(action.slot_actions):
        index = observation.own_side.active_slots[slot]
        actor = (
            observation.own_side.team[index].pokemon_set.species
            if index is not None
            else f"slot {slot + 1}"
        )
        parts.append(f"{actor}: {describe_slot_action(observation, slot, slot_action, dex=dex)}")
    return " | ".join(parts)
