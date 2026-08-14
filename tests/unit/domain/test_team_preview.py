import pytest
from pydantic import ValidationError

from champions_ai.domain import REGULATION_M_B, PokemonSet, RevealedPokemon, Team, TeamPreview


def _team(n: int) -> Team:
    return Team(
        pokemon=tuple(
            PokemonSet(
                species=f"species{i}",
                level=50,
                ability="someability",
                moves=("tackle",),
                item="leftovers",
                nature="jolly",
            )
            for i in range(n)
        )
    )


def test_from_teams_defaults_to_masked_opponent_view():
    preview = TeamPreview.from_teams(REGULATION_M_B, own_team=_team(6), opponent_team=_team(6))
    assert len(preview.own_team) == 6
    assert len(preview.opponent_team) == 6
    for revealed in preview.opponent_team:
        assert revealed.ability is None
        assert revealed.item is None
        assert revealed.moves is None
    for own_mon in preview.own_team.pokemon:
        assert own_mon.ability == "someability"


def test_from_teams_with_sheets_open_reveals_opponent_non_stat_fields():
    preview = TeamPreview.from_teams(
        REGULATION_M_B, own_team=_team(6), opponent_team=_team(6), sheets_open=True
    )
    for revealed in preview.opponent_team:
        assert revealed.ability == "someability"
        assert revealed.item == "leftovers"
        assert revealed.moves == ("tackle",)


def test_rejects_own_team_with_fewer_than_six():
    with pytest.raises(ValidationError):
        TeamPreview.from_teams(REGULATION_M_B, own_team=_team(4), opponent_team=_team(6))


def test_rejects_opponent_team_with_fewer_than_six():
    with pytest.raises(ValidationError):
        TeamPreview.from_teams(REGULATION_M_B, own_team=_team(6), opponent_team=_team(3))


def test_can_construct_directly_from_already_masked_opponent_data():
    opponent = tuple(RevealedPokemon(species=f"species{i}", level=50) for i in range(6))
    preview = TeamPreview(regulation=REGULATION_M_B, own_team=_team(6), opponent_team=opponent)
    assert preview.opponent_team[0].ability is None
