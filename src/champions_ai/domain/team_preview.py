from pydantic import BaseModel, model_validator

from champions_ai.domain.regulation import Regulation
from champions_ai.domain.team import Team


class TeamPreview(BaseModel, frozen=True):
    """Both full rosters as seen before a match starts (Open Team Sheets reveals both)."""

    regulation: Regulation
    own_team: Team
    opponent_team: Team

    @model_validator(mode="after")
    def _check_team_sizes(self) -> "TeamPreview":
        expected = self.regulation.min_team_size
        if len(self.own_team) != expected:
            raise ValueError(
                f"own_team must have exactly {expected} Pokemon, got {len(self.own_team)}"
            )
        if len(self.opponent_team) != expected:
            raise ValueError(
                f"opponent_team must have exactly {expected} Pokemon, got {len(self.opponent_team)}"
            )
        return self
