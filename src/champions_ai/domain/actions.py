from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from champions_ai.domain.regulation import SpecialMechanic

MAX_MOVES = 4


class TargetSlot(BaseModel, frozen=True):
    """A targeted position on the field, relative to the acting Pokemon's own side.

    `side="ally"` covers the acting Pokemon itself; slots are 0-indexed, unlike
    Showdown's signed 1-based convention (+1/+2 foes, -1/-2 allies), which is
    translated at the simulator boundary rather than leaking into the domain.
    """

    side: Literal["ally", "foe"]
    slot: int

    @model_validator(mode="after")
    def _check_slot(self) -> "TargetSlot":
        if self.slot < 0:
            raise ValueError(f"slot must be non-negative, got {self.slot}")
        return self


class MoveAction(BaseModel, frozen=True):
    """Use one of the active Pokemon's moves.

    `target` is None for moves that don't take one (spread moves, self-targeting
    moves, field effects). Whether a given move *requires* a target depends on
    move data this type deliberately doesn't carry -- that check belongs to the
    legal-action generator, not here.

    `special` names a once-per-battle form change to activate alongside the
    move. It is a mechanic name rather than a `mega` flag so that a regulation
    enabling Terastallization (or anything else) is a data change on
    `Regulation.special_mechanics`, not a schema change here.
    """

    kind: Literal["move"] = "move"
    move_index: int
    target: TargetSlot | None = None
    special: SpecialMechanic | None = None

    @model_validator(mode="after")
    def _check_move_index(self) -> "MoveAction":
        if not 0 <= self.move_index < MAX_MOVES:
            raise ValueError(
                f"move_index must be between 0 and {MAX_MOVES - 1}, got {self.move_index}"
            )
        return self


class SwitchAction(BaseModel, frozen=True):
    """Switch this slot's Pokemon out for a benched one, by index into the brought team."""

    kind: Literal["switch"] = "switch"
    team_index: int

    @model_validator(mode="after")
    def _check_index(self) -> "SwitchAction":
        if self.team_index < 0:
            raise ValueError(f"team_index must be non-negative, got {self.team_index}")
        return self


class PassAction(BaseModel, frozen=True):
    """This slot does nothing -- empty after a faint, or otherwise unable to act."""

    kind: Literal["pass"] = "pass"


SlotAction = Annotated[MoveAction | SwitchAction | PassAction, Field(discriminator="kind")]


class JointAction(BaseModel, frozen=True):
    """Every slot's choice for one turn, submitted together as doubles requires."""

    slot_actions: tuple[SlotAction, ...]

    @model_validator(mode="after")
    def _check_joint_consistency(self) -> "JointAction":
        if not self.slot_actions:
            raise ValueError("a joint action must cover at least one slot")

        switch_targets = [a.team_index for a in self.slot_actions if isinstance(a, SwitchAction)]
        if len(set(switch_targets)) != len(switch_targets):
            raise ValueError(
                f"two slots cannot switch to the same benched Pokemon: {switch_targets}"
            )

        # Mega, Tera and Dynamax are all once per battle per side, so at most
        # one slot may activate any of them on a given turn.
        specials = [a.special for a in self.slot_actions if isinstance(a, MoveAction) and a.special]
        if len(specials) > 1:
            raise ValueError(f"only one special mechanic may be used per turn, got {specials}")
        return self

    def __len__(self) -> int:
        return len(self.slot_actions)


class TeamPreviewAction(BaseModel, frozen=True):
    """The pick-N-of-6 choice made at Team Preview, in lead order.

    Order is meaningful: the first `active_slots_per_side` picks start the
    battle on the field.
    """

    picks: tuple[int, ...]

    @model_validator(mode="after")
    def _check_picks(self) -> "TeamPreviewAction":
        if not self.picks:
            raise ValueError("must pick at least one Pokemon")
        if len(set(self.picks)) != len(self.picks):
            raise ValueError(f"cannot pick the same Pokemon twice: {self.picks}")
        for index in self.picks:
            if index < 0:
                raise ValueError(f"pick indices must be non-negative, got {index}")
        return self
