"""Uniform random over legal actions -- the floor every other agent must beat."""

import random
from collections.abc import Sequence

from champions_ai.agents.base import Agent
from champions_ai.domain import JointAction, Observation, TeamPreview, TeamPreviewAction


class RandomAgent(Agent):
    """Picks uniformly at random.

    Takes its own generator rather than using the global one, so an evaluation
    run is reproducible from its seed regardless of what else draws randomness.
    """

    def __init__(self, seed: int | None = None, name: str = "random") -> None:
        self.name = name
        self._rng = random.Random(seed)

    def select_action(
        self, observation: Observation, legal_actions: Sequence[JointAction]
    ) -> JointAction:
        return self._rng.choice(list(legal_actions))

    def select_team_preview(
        self, preview: TeamPreview, picked_team_size: int
    ) -> TeamPreviewAction:
        roster = range(len(preview.own_team))
        return TeamPreviewAction(picks=tuple(self._rng.sample(list(roster), picked_team_size)))
