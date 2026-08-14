"""Enumerate the actions a player may legally submit, from their own Observation.

Operates on `Observation`, never `BattleState` -- a player picks actions from
what they can see, so generating from omniscient truth would be a hidden-
information leak by construction.

Per ADR 0003 this reads availability the engine reports rather than
recomputing it: `BattlePokemon.disabled_moves` covers Choice lock, Encore,
Taunt, Disable and Torment; `available_specials` covers Mega and anything a
future regulation enables; trapping is a `"trapped"` volatile. All of these are
populated by the simulator adapter, so nothing here reimplements a game rule.

Remaining gap: Struggle is unmodelled -- a Pokemon with no usable move and no
switch yields a pass instead.
"""

from collections.abc import Mapping, Sequence
from itertools import product

from pydantic import ValidationError

from champions_ai.domain.actions import (
    JointAction,
    MoveAction,
    PassAction,
    SlotAction,
    SwitchAction,
    TargetSlot,
)
from champions_ai.domain.move_data import MoveData
from champions_ai.domain.observation import Observation

TRAPPED = "trapped"


def _live_foe_slots(observation: Observation) -> tuple[int, ...]:
    opponent = observation.opponent_side
    return tuple(
        slot
        for slot, index in enumerate(opponent.active_slots)
        if index is not None and not opponent.revealed[index].fainted
    )


def _live_own_slots(
    observation: Observation, acting_slot: int, *, include_self: bool
) -> tuple[int, ...]:
    own = observation.own_side
    return tuple(
        slot
        for slot, index in enumerate(own.active_slots)
        if index is not None
        and not own.team[index].fainted
        and (include_self or slot != acting_slot)
    )


def _candidate_targets(
    observation: Observation, acting_slot: int, move: MoveData
) -> tuple[TargetSlot | None, ...]:
    """Slots this move may be aimed at, or (None,) when the engine picks."""
    if not move.requires_target_choice:
        return (None,)

    foes = tuple(TargetSlot(side="foe", slot=s) for s in _live_foe_slots(observation))

    if move.target in ("normal", "any"):
        # In doubles every slot is adjacent, so a "normal" move may also be
        # aimed at your own partner -- occasionally correct (Beat Up, Helping
        # Hand redirection plays), and legal regardless.
        allies = tuple(
            TargetSlot(side="ally", slot=s)
            for s in _live_own_slots(observation, acting_slot, include_self=False)
        )
        return foes + allies
    if move.target == "adjacentFoe":
        return foes
    if move.target == "adjacentAlly":
        return tuple(
            TargetSlot(side="ally", slot=s)
            for s in _live_own_slots(observation, acting_slot, include_self=False)
        )
    # adjacentAllyOrSelf
    return tuple(
        TargetSlot(side="ally", slot=s)
        for s in _live_own_slots(observation, acting_slot, include_self=True)
    )


def _switch_actions(observation: Observation, exclude: int | None = None) -> list[SlotAction]:
    return [
        SwitchAction(team_index=index)
        for index in observation.own_side.switchable_indices()
        if index != exclude
    ]


def legal_slot_actions(
    observation: Observation,
    acting_slot: int,
    move_data: Mapping[str, MoveData],
) -> list[SlotAction]:
    """Every action the Pokemon in `acting_slot` could take, ignoring other slots."""
    own = observation.own_side
    team_index = own.active_slots[acting_slot]

    # An empty or fainted slot must be refilled; it has no move options.
    if team_index is None or own.team[team_index].fainted:
        switches = _switch_actions(observation)
        return switches or [PassAction()]

    pokemon = own.team[team_index]
    actions: list[SlotAction] = []

    # Activating a special mechanic is a genuine extra choice, not a variant of
    # the move, so each usable move appears both with and without it.
    specials: tuple[str | None, ...] = (None, *sorted(pokemon.available_specials))

    for move_index, move_id in enumerate(pokemon.pokemon_set.moves):
        if move_id in pokemon.disabled_moves:
            continue
        if pokemon.move_pp is not None and pokemon.move_pp[move_index] <= 0:
            continue
        move = move_data.get(move_id)
        if move is None:
            raise KeyError(f"no MoveData for move {move_id!r} on {pokemon.pokemon_set.species!r}")
        for target in _candidate_targets(observation, acting_slot, move):
            if move.requires_target_choice and target is None:
                continue
            for special in specials:
                actions.append(
                    MoveAction(move_index=move_index, target=target, special=special)
                )

    if TRAPPED not in pokemon.volatile_conditions:
        actions.extend(_switch_actions(observation, exclude=team_index))

    return actions or [PassAction()]


def legal_joint_actions(
    observation: Observation,
    move_data: Mapping[str, MoveData],
) -> list[JointAction]:
    """Every legal combination across slots, with cross-slot conflicts removed."""
    per_slot: Sequence[list[SlotAction]] = [
        legal_slot_actions(observation, slot, move_data)
        for slot in range(len(observation.own_side.active_slots))
    ]

    joint: list[JointAction] = []
    for combination in product(*per_slot):
        try:
            # JointAction owns the cross-slot rules (no shared switch target,
            # one Mega per turn), so invalid combinations are rejected here
            # rather than duplicating that logic.
            joint.append(JointAction(slot_actions=combination))
        except ValidationError:
            continue
    return joint
