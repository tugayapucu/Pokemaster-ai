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
    # The Showdown mod this regulation's dex comes from. A regulation is not a
    # rules difference -- M-A and M-B have identical rule tables, verified from
    # the engine -- it is a *dex* difference: M-B carries 38 species and 31
    # items M-A does not. So the mod is the thing that actually distinguishes
    # them, and anything loading reference data has to be told which one.
    mod: str = "champions"
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


# The base `champions` mod is not a fixed dex: it is whichever regulation is
# current, and its predecessor is frozen into `championsreg<x>` when a new one
# ships. Observed across the 2026-09-10 upgrade:
#
#     mod name          before (0.11.11)      after (d849b22)
#     champions         Reg M-B               Reg M-C
#     championsregma    Reg M-A               deleted upstream
#     championsregmb    -                     Reg M-B
#
# So a `mod` here is only correct for a pinned build, and
# `tests/integration/test_regulation_mods.py` asks the engine rather than
# trusting these strings. REGULATION_M_A is gone with the format: this build
# has no `gen9championsvgc2026regma`, so a constant for it could only produce
# battles the engine refuses. It is in the history if it ever returns.

REGULATION_M_C = Regulation(
    format_id="gen9championsvgc2026regmc",
    name="[Gen 9 Champions] VGC 2026 Reg M-C",
    mod="champions",
    game_type="doubles",
    # Every value read off the engine through `bridge.format_rules`, never
    # transcribed: a wrong picked team size still validates teams and a wrong
    # level still runs battles, so a mistake here would be silent.
    #   adjustLevel 50, minTeamSize 6, pickedTeamSize 4, evLimit 66 --
    #   identical to M-B's, which is the pattern: a regulation is a dex, not a
    #   rule change.
    #   32 per stat is hardcoded in the core team validator for any mod whose
    #   name starts with "champions", so it belongs to the family not the mod.
    #   Mega on and Tera off: the mod carries 81 Mega stones (M-B has 75) and
    #   its scripts set canTerastallize to null.
    level=50,
    min_team_size=6,
    picked_team_size=4,
    max_stat_points_per_stat=32,
    max_total_stat_points=66,
    special_mechanics=frozenset({"mega"}),
)

REGULATION_M_B = Regulation(
    format_id="gen9championsvgc2026regmb",
    name="[Gen 9 Champions] VGC 2026 Reg M-B",
    # Was "champions" until M-C took that name. `championsregmb` inherits from
    # `champions`, so M-B is now defined upstream as a diff from M-C.
    mod="championsregmb",
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
