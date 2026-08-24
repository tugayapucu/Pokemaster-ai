"""Teams to evaluate on, and how matchups are drawn from them.

A result measured on one team pair describes that pair, not the agents. The
pool exists so a win rate generalises -- and so a heuristic tuned on a single
Charizard/Garchomp mirror cannot look better than it is (AGENTS.md: "optimize
only against one opponent" is listed as a thing agents must not do).
"""

import random
from collections.abc import Sequence
from dataclasses import dataclass

from champions_ai.data.team_text import parse_showdown_team
from champions_ai.domain import Team


# Showdown seeds look like `sodium,<64 hex>`; a pool derives one per team from
# its own so that growing `size` leaves earlier teams untouched.
def _derived(seed: str, index: int) -> str:
    prefix, _, hex_part = seed.partition(",")
    if not hex_part:
        return seed
    bumped = format(
        (int(hex_part, 16) + index * 0x9E3779B97F4A7C15) % (1 << (4 * len(hex_part))),
        f"0{len(hex_part)}x",
    )
    return f"{prefix},{bumped}"



@dataclass(frozen=True)
class BattleTeam:
    """A team in both forms it is needed in.

    `team` is the domain view, used by trackers to recover the Stat Points the
    engine never sends back. `packed` is what the simulator is started with.
    They are carried together because one cannot be derived from the other
    without Showdown.
    """

    team: Team
    packed: str
    name: str = ""

    @property
    def species(self) -> tuple[str, ...]:
        return tuple(mon.species for mon in self.team.pokemon)

    def __str__(self) -> str:
        return self.name or "/".join(self.species[:3]) + "..."


@dataclass(frozen=True)
class Matchup:
    """One team pair, identified so results can be grouped by it."""

    index: int
    teams: tuple[BattleTeam, BattleTeam]

    @property
    def label(self) -> str:
        return f"{self.teams[0]} vs {self.teams[1]}"


class TeamPool:
    """Validated teams to sample matchups from."""

    def __init__(self, teams: Sequence[BattleTeam]) -> None:
        if len(teams) < 2:
            raise ValueError(f"a pool needs at least 2 teams to form a matchup, got {len(teams)}")
        self.teams = tuple(teams)

    def __len__(self) -> int:
        return len(self.teams)

    def matchups(self, count: int, *, seed: int = 0) -> tuple[Matchup, ...]:
        """Draw `count` distinct team pairings, reproducibly.

        Pairs are drawn without replacement within a pass over the pool, so a
        short run still spreads across teams instead of repeatedly sampling the
        same lucky pair.
        """
        if count < 1:
            raise ValueError(f"count must be positive, got {count}")
        rng = random.Random(seed)
        drawn: list[Matchup] = []
        while len(drawn) < count:
            first, second = rng.sample(range(len(self.teams)), 2)
            drawn.append(
                Matchup(index=len(drawn), teams=(self.teams[first], self.teams[second]))
            )
        return tuple(drawn)

    @classmethod
    def from_texts(cls, bridge, battle_format: str, texts: Sequence[str]) -> "TeamPool":
        """Build from Showdown export text, validating each against the format."""
        prepared = []
        for index, text in enumerate(texts):
            packed = bridge.validate_team(battle_format, text)
            prepared.append(
                BattleTeam(
                    team=parse_showdown_team(text),
                    packed=packed,
                    name=f"team{index}",
                )
            )
        return cls(prepared)

    @classmethod
    def generated(
        cls,
        bridge,
        battle_format: str,
        *,
        size: int,
        generator: str | None = None,
        seed: str | None = None,
    ) -> "TeamPool":
        """Sample legal teams from Showdown's generator.

        Slow -- the generator is not regulation-aware and the validator rejects
        most attempts -- so build a pool once and reuse it across an evaluation
        run rather than generating per battle.

        **Pass a `seed` for anything whose number gets reported.** Without one
        the pool is redrawn every run, so re-running a comparison changes the
        teams underneath it. Two 90-battle runs of the Mega comparison
        disagreed in direction because of exactly this, and the swing was
        larger than the effect being measured.
        """
        prepared = []
        for index in range(size):
            packed, exported = bridge.random_team_pair(
                battle_format,
                generator,
                # One seed per team, derived from the pool's, so a pool stays
                # stable when `size` grows: team 3 is the same team either way.
                seed=None if seed is None else _derived(seed, index),
            )
            prepared.append(
                BattleTeam(
                    team=parse_showdown_team(exported),
                    packed=packed,
                    name=f"gen{index}",
                )
            )
        return cls(prepared)
