from typing import Literal

from pydantic import BaseModel

GameType = Literal["singles", "doubles"]


class Regulation(BaseModel, frozen=True):
    """Structural facts only; legality is enforced by Showdown's sim (ADR 0001), not here."""

    format_id: str
    name: str
    game_type: GameType
    level: int
    min_team_size: int
    picked_team_size: int
    max_stat_points_per_stat: int
    max_total_stat_points: int


REGULATION_M_B = Regulation(
    format_id="gen9championsvgc2026regmb",
    name="[Gen 9 Champions] VGC 2026 Reg M-B",
    game_type="doubles",
    level=50,
    min_team_size=6,
    picked_team_size=4,
    max_stat_points_per_stat=32,
    max_total_stat_points=66,
)
