from pydantic import BaseModel, Field, model_validator

from champions_ai.domain.regulation import Regulation
from champions_ai.domain.side import Side


class BattleState(BaseModel, frozen=True):
    """Complete simulator truth for a battle in progress -- NOT what a player is allowed to see.

    Player-facing code must consume `Observation.from_battle_state(self, player)`,
    never this type directly (see AGENTS.md, "Hidden information must remain hidden").
    """

    regulation: Regulation
    turn: int
    sides: tuple[Side, Side]
    weather: str | None = None
    terrain: str | None = None
    field_conditions: dict[str, int] = Field(default_factory=dict)
    # The last move executed by either side. Not a property of either side, so
    # it lives here -- and Copycat needs it.
    last_move_used: str | None = None

    @model_validator(mode="after")
    def _check_shape(self) -> "BattleState":
        if self.turn < 0:
            raise ValueError(f"turn must be non-negative, got {self.turn}")
        expected_slots = self.regulation.active_slots_per_side
        expected_team = self.regulation.picked_team_size
        for player, side in enumerate(self.sides):
            if len(side.active_slots) != expected_slots:
                raise ValueError(
                    f"side {player} has {len(side.active_slots)} slots, "
                    f"but {self.regulation.game_type} expects {expected_slots}"
                )
            if len(side.team) != expected_team:
                raise ValueError(
                    f"side {player} brought {len(side.team)} Pokemon, "
                    f"but this regulation picks {expected_team}"
                )
        return self

    @property
    def is_terminal(self) -> bool:
        return not all(side.has_usable_pokemon for side in self.sides)

    @property
    def winner(self) -> int | None:
        """Index of the winning side, or None if the battle is ongoing or drawn."""
        alive = [i for i, side in enumerate(self.sides) if side.has_usable_pokemon]
        return alive[0] if len(alive) == 1 else None

    def with_side(self, player: int, side: Side) -> "BattleState":
        updated = list(self.sides)
        updated[player] = side
        return self.model_copy(update={"sides": (updated[0], updated[1])})

    def with_turn(self, turn: int) -> "BattleState":
        return self.model_copy(update={"turn": turn})
