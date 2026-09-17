"""The shipped agent, with our own Team Preview pinned to a chosen four.

Scouting measures a team by playing it, and the agent picks the four it brings
-- so a scout of a team is partly a scout of the picker. Measured on one
candidate: the agent's own picks went 133/240 where the player's usual four,
on the same opponents and seeds, went 175/240. A 42-battle gap in the thing
being measured, from a choice the player makes themselves in a real game.

This forces *our* four and leaves the opponent's to the agent, so what changes
between two runs is the team, not the picker. The counters exist to prove that:
a run reports how many previews it forced and how many it left alone, and they
should be one each per battle.

Matched by roster rather than by seat, because `scout_team` plays each opponent
from both seats with the same agent object. A mirror -- an opposing team whose
six are exactly ours -- would match too, so it is counted separately rather
than assumed away.
"""

from champions_ai.agents.heuristic import HeuristicAgent
from champions_ai.dex.reference import to_id
from champions_ai.domain import TeamPreview, TeamPreviewAction


class FixedPreviewAgent(HeuristicAgent):
    """`HeuristicAgent`, except that our own Team Preview is decided in advance."""

    def __init__(self, dex, *, own_species, picks, **kwargs) -> None:
        super().__init__(dex, **kwargs)
        self.own_species = tuple(to_id(species) for species in own_species)
        self.picks = tuple(picks)
        if len(set(self.picks)) != len(self.picks):
            raise ValueError(f"the same Pokemon twice in {self.picks}")
        for index in self.picks:
            if not 0 <= index < len(self.own_species):
                raise ValueError(
                    f"pick {index + 1} is not one of our {len(self.own_species)} Pokemon"
                )
        self.forced = 0
        self.left_to_the_agent = 0
        self.forced_on_a_mirror = 0

    def select_team_preview(self, preview: TeamPreview, picked_team_size: int):
        roster = tuple(to_id(mon.species) for mon in preview.own_team.pokemon)
        if roster != self.own_species:
            self.left_to_the_agent += 1
            return super().select_team_preview(preview, picked_team_size)
        if len(self.picks) != picked_team_size:
            raise ValueError(
                f"this regulation brings {picked_team_size}, and {len(self.picks)} were chosen"
            )
        self.forced += 1
        if tuple(to_id(mon.species) for mon in preview.opponent_team) == self.own_species:
            self.forced_on_a_mirror += 1
        return TeamPreviewAction(picks=self.picks)
