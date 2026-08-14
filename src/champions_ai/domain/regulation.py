from typing import Literal

from pydantic import BaseModel

from champions_ai.domain.stats import STAT_NAMES, StatSpread

GameType = Literal["singles", "doubles"]

# Showdown's choice-string suffixes for once-per-battle form changes. Reg M-B
# enables only Mega, but the vocabulary is kept open so a future regulation
# turning Tera back on is a data change, not a schema change.
SpecialMechanic = Literal["mega", "terastallize", "dynamax", "zmove", "ultraburst"]


class Regulation(BaseModel, frozen=True):
    """Structural facts only; legality is enforced by Showdown's sim (ADR 0001), not here.

    Everything a regulation can vary lives here as data, so supporting a new
    one means adding an instance rather than editing domain classes.
    """

    format_id: str
    name: str
    game_type: GameType
    level: int
    min_team_size: int
    picked_team_size: int
    max_stat_points_per_stat: int
    max_total_stat_points: int
    special_mechanics: frozenset[SpecialMechanic] = frozenset()

    @property
    def active_slots_per_side(self) -> int:
        return 2 if self.game_type == "doubles" else 1

    def allows(self, mechanic: SpecialMechanic) -> bool:
        return mechanic in self.special_mechanics

    def stat_spread_problems(self, spread: StatSpread) -> list[str]:
        """This regulation's objections to a spread, empty if it's fine.

        Returns problems rather than raising so callers can report all of them
        at once, matching how Showdown's own TeamValidator behaves.
        """
        problems = []
        for name in STAT_NAMES:
            value = getattr(spread, name)
            if value > self.max_stat_points_per_stat:
                problems.append(
                    f"{name} has {value} stat points, over this format's "
                    f"limit of {self.max_stat_points_per_stat}"
                )
        if spread.total > self.max_total_stat_points:
            problems.append(
                f"{spread.total} total stat points, over this format's "
                f"limit of {self.max_total_stat_points}"
            )
        return problems


REGULATION_M_B = Regulation(
    format_id="gen9championsvgc2026regmb",
    name="[Gen 9 Champions] VGC 2026 Reg M-B",
    game_type="doubles",
    level=50,
    min_team_size=6,
    picked_team_size=4,
    max_stat_points_per_stat=32,
    max_total_stat_points=66,
    # Mega only: Terastallization is disabled under this ruleset, confirmed in
    # the champions mod's scripts.ts (canTerastallize returns null).
    special_mechanics=frozenset({"mega"}),
)
