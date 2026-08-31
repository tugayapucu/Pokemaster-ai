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

from collections.abc import Iterator, Mapping, Sequence
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
from champions_ai.domain.move_data import TARGETS_REQUIRING_CHOICE, MoveData
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
    observation: Observation, acting_slot: int, target_type: str | None
) -> tuple[TargetSlot | None, ...]:
    """Slots a move with this target type may be aimed at, or (None,) when it takes none."""
    if target_type is None or target_type not in TARGETS_REQUIRING_CHOICE:
        return (None,)

    foes = tuple(TargetSlot(side="foe", slot=s) for s in _live_foe_slots(observation))

    if target_type in ("normal", "any"):
        # In doubles every slot is adjacent, so a "normal" move may also be
        # aimed at your own partner -- occasionally correct (Beat Up, Helping
        # Hand redirection plays), and legal regardless.
        allies = tuple(
            TargetSlot(side="ally", slot=s)
            for s in _live_own_slots(observation, acting_slot, include_self=False)
        )
        return foes + allies
    if target_type == "adjacentFoe":
        return foes
    if target_type == "adjacentAlly":
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

    engine_targets = pokemon.choosable_move_targets

    def move_actions(*, relax_targets: bool) -> list[SlotAction]:
        return list(
            _move_actions(
                observation,
                acting_slot,
                pokemon,
                move_data,
                engine_targets,
                specials,
                relax_targets=relax_targets,
            )
        )

    actions.extend(move_actions(relax_targets=False))

    if TRAPPED not in pokemon.volatile_conditions:
        actions.extend(_switch_actions(observation, exclude=team_index))

    if actions:
        return actions

    # Nothing survived, and **a pass is not legal for a slot the engine expects
    # to act**. Two different situations reach here and they want opposite
    # answers, so they are separated rather than relaxed together -- lumping
    # them offered disabled moves and the engine refused those too.
    #
    # First: the move is usable and we simply could not name a target, because
    # our view of who is still standing lags the engine's mid-turn. Keep the
    # availability filters and aim at the first foe slot.
    relaxed = move_actions(relax_targets=True)
    if relaxed:
        return relaxed

    # Otherwise every move really is spent or disabled, and the engine answers
    # that itself -- `Side.chooseMove`: "Override action and use Struggle if
    # there are no enabled moves with PP". It substitutes Struggle for whatever
    # is chosen, and Struggle needs no target.
    #
    # Unless there is no move to name. A reconstructed replay knows only the
    # moves it actually saw used, so a Pokemon can legitimately have an empty
    # list -- and `MoveAction(move_index=0)` then points at nothing. Passing is
    # wrong against a live engine and is the only thing left here.
    if not pokemon.selectable_moves:
        return [PassAction()]

    # Prefer a move the *engine* has not flagged disabled. Reaching here means
    # our own filters rejected every move, and of the two filters PP is the one
    # that can be stale: `disabled` arrives on the request and is authoritative
    # per ADR 0003, while a PP count we believe to be spent may not be. Choosing
    # blindly here sent the engine a disabled Protect once, which it refused
    # outright rather than substituting Struggle for -- Showdown only does that
    # when the request itself carries no usable move, and in that case the
    # request already offers Struggle and the normal path returns it.
    #
    # Narrowing only: when everything really is disabled this still falls
    # through to index 0, which is the Struggle case it was written for.
    for index, move_id in enumerate(pokemon.selectable_moves):
        if move_id not in pokemon.disabled_moves:
            return [MoveAction(move_index=index, target=None)]
    return [MoveAction(move_index=0, target=None)]


def _move_actions(
    observation: Observation,
    acting_slot: int,
    pokemon,
    move_data: Mapping[str, MoveData],
    engine_targets,
    specials: tuple[str | None, ...],
    *,
    relax_targets: bool,
) -> Iterator[SlotAction]:
    """The move half of `legal_slot_actions`.

    PP and disabled moves are *always* honoured -- that is ADR 0003, and
    ignoring it just produces choices the engine rejects as unavailable.
    `relax_targets` loosens only the targeting, for the last-resort pass where
    we could not name a live target and a pass would be refused.
    """
    for move_index, move_id in enumerate(pokemon.selectable_moves):
        if move_id in pokemon.disabled_moves:
            continue
        if pokemon.move_pp is not None and pokemon.move_pp[move_index] <= 0:
            continue

        if engine_targets is not None:
            # What the engine says about *this* Pokemon *this* turn beats the
            # move's usual behaviour, which is stale for a locked move.
            target_type = engine_targets[move_index]
        else:
            move = move_data.get(move_id)
            if move is None:
                raise KeyError(
                    f"no MoveData for move {move_id!r} on {pokemon.pokemon_set.species!r}"
                )
            target_type = move.target

        candidates = _candidate_targets(observation, acting_slot, target_type)
        if not candidates and relax_targets:
            # Last resort only. We believe nothing is alive to aim at, and the
            # engine disagrees -- it rejected a targetless choice with "Ice
            # Beam needs a target". Our view of who is still standing can lag
            # the engine's mid-turn, so name the first foe slot rather than
            # submit a choice that is certain to be refused.
            candidates = (TargetSlot(side="foe", slot=0),)
        for target in candidates:
            if target_type in TARGETS_REQUIRING_CHOICE and target is None:
                continue
            for special in specials:
                yield MoveAction(
                    move_index=move_index, target=target, special=special
                )


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
