from pydantic import BaseModel, model_validator

from champions_ai.domain.regulation import Regulation
from champions_ai.domain.revealed_pokemon import RevealedPokemon
from champions_ai.domain.team import Team


class TeamPreview(BaseModel, frozen=True):
    """Before a match starts: your full roster, and only what's actually visible of theirs."""

    regulation: Regulation
    own_team: Team
    opponent_team: tuple[RevealedPokemon, ...]

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

    @classmethod
    def from_teams(
        cls,
        regulation: Regulation,
        own_team: Team,
        opponent_team: Team,
        *,
        sheets_open: bool = False,
    ) -> "TeamPreview":
        revealed = tuple(
            RevealedPokemon.from_set(mon, sheets_open=sheets_open) for mon in opponent_team.pokemon
        )
        return cls(regulation=regulation, own_team=own_team, opponent_team=revealed)
