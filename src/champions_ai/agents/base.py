"""The interface every agent implements.

Two decisions, because they genuinely differ: picking N of 6 happens before a
battle exists, so there is no `Observation` to reason from -- only a
`TeamPreview`. Conflating them would force one of the two to lie about what
information is available.

Agents receive an `Observation`, never a `BattleState` (AGENTS.md). They also
receive the legal actions rather than deriving them, so a subtle disagreement
about legality can only come from one place.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from champions_ai.domain import JointAction, Observation, TeamPreview, TeamPreviewAction


class Agent(ABC):
    """A battle policy."""

    name: str = "agent"

    @abstractmethod
    def select_action(
        self, observation: Observation, legal_actions: Sequence[JointAction]
    ) -> JointAction:
        """Choose one of `legal_actions`. Must return a member of that sequence."""

    def select_team_preview(
        self, preview: TeamPreview, picked_team_size: int
    ) -> TeamPreviewAction:
        """Choose which Pokemon to bring, in lead order.

        Defaults to the declared order, which is what a player who does not
        engage with team preview gets. Override to actually use the matchup.
        """
        return TeamPreviewAction(picks=tuple(range(picked_team_size)))

    def on_battle_start(self) -> None:
        """Reset any per-battle state. Called before each battle."""

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r})"
