import pytest
from pydantic import ValidationError

from champions_ai.domain import REGULATION_M_B, PokemonSet, Team, TeamPreview


def _team(n: int) -> Team:
    return Team(
        pokemon=tuple(
            PokemonSet(
                species=f"species{i}",
                level=50,
                ability="someability",
                moves=("tackle",),
            )
            for i in range(n)
        )
    )


def test_valid_team_preview_with_two_full_rosters():
    preview = TeamPreview(
        regulation=REGULATION_M_B,
        own_team=_team(6),
        opponent_team=_team(6),
    )
    assert len(preview.own_team) == 6
    assert len(preview.opponent_team) == 6


def test_rejects_own_team_with_fewer_than_six():
    with pytest.raises(ValidationError):
        TeamPreview(
            regulation=REGULATION_M_B,
            own_team=_team(4),
            opponent_team=_team(6),
        )


def test_rejects_opponent_team_with_fewer_than_six():
    with pytest.raises(ValidationError):
        TeamPreview(
            regulation=REGULATION_M_B,
            own_team=_team(6),
            opponent_team=_team(3),
        )
