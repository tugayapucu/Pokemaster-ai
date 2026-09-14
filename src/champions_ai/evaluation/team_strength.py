"""How does one team do against the field?

`evaluate` answers a different question: it swaps *agents* over fixed teams, so
the teams cancel and what is left is the policy. This is the inverse. One team
is held fixed, the agent is the same on both sides, and what is left is the
**team**.

That inversion is what makes the measurement readable. 0031 put **93% of the
variance in outcomes on the matchup** rather than on play, which is a problem
when the matchup is a confound and the whole signal when the matchup is the
question. With identical agents an even matchup must tie; every deviation from
50% is the two teams disagreeing about who wins.

Two consequences for how this is run:

- **Seats are swapped, teams are not.** Each opponent is played twice, once
  from each side, on the same battle seed. Anything that follows the seat --
  who moves first on a speed tie, who acts on the last turn -- lands on both
  teams equally.
- **Breadth beats depth.** Since almost all the variance is *which* opponent
  was drawn, forty opponents played twice says far more than four opponents
  played twenty times. The sample counts distinct opponents, and reports it.

What it cannot tell you is whether the team is good *at a tournament*. The
opponents come from a harvested ladder pool and are played by our heuristic,
which picks the best of four candidate actions 57% of the time (0038). It
measures how a team fares against the field it was harvested from, played the
way this project plays. That is real information about matchup structure and it
is not a metagame verdict.
"""

from dataclasses import dataclass, field

from champions_ai.agents.base import Agent
from champions_ai.data import BattleTeam, TeamPool
from champions_ai.env import BattleEnv
from champions_ai.evaluation.runner import play_battle, wilson_interval


@dataclass(frozen=True)
class Matchup:
    """One opponent team, played from both seats."""

    opponent: str
    roster: tuple[str, ...]
    wins: int
    battles: int

    @property
    def rate(self) -> float:
        return self.wins / self.battles if self.battles else 0.0


@dataclass(frozen=True)
class MatchupGroup:
    """Every matchup sharing something: one roster, or one opposing species.

    The unit a losing matchup should be read at. One matchup is two battles,
    and the same roster drawn three times went 0/2 and 2/2 on the battle seed
    alone; a group pools enough opponents that its interval can say something.
    """

    label: tuple[str, ...]
    opponents: int
    wins: int
    battles: int

    @property
    def rate(self) -> float:
        return self.wins / self.battles if self.battles else 0.0

    @property
    def interval(self) -> tuple[float, float]:
        return wilson_interval(self.wins, self.battles)


def _grouped(matchups, keys_of, min_opponents: int) -> tuple[MatchupGroup, ...]:
    totals: dict[tuple[str, ...], list[int]] = {}
    for matchup in matchups:
        for key in keys_of(matchup):
            entry = totals.setdefault(key, [0, 0, 0])
            entry[0] += 1
            entry[1] += matchup.wins
            entry[2] += matchup.battles
    groups = [
        MatchupGroup(label=key, opponents=n, wins=wins, battles=battles)
        for key, (n, wins, battles) in totals.items()
        if n >= min_opponents
    ]
    return tuple(sorted(groups, key=lambda g: (g.rate, -g.battles, g.label)))


@dataclass(frozen=True)
class TeamReport:
    """How the team did, and against whom."""

    team: str
    battles: int
    wins: int
    draws: int
    opponents: int
    matchups: tuple[Matchup, ...] = field(default=(), repr=False)

    @property
    def win_rate(self) -> float:
        return self.wins / self.battles if self.battles else 0.0

    @property
    def interval(self) -> tuple[float, float]:
        return wilson_interval(self.wins, self.battles)

    def worst(self, count: int = 5) -> tuple[Matchup, ...]:
        """The matchups that beat it, hardest first.

        The most useful half of the output. A win rate says whether to keep
        looking; the losing matchups say what to change.
        """
        return tuple(sorted(self.matchups, key=lambda m: (m.rate, m.opponent))[:count])

    def best(self, count: int = 5) -> tuple[Matchup, ...]:
        return tuple(
            sorted(self.matchups, key=lambda m: (-m.rate, m.opponent))[:count]
        )

    def by_roster(self, min_opponents: int = 2) -> tuple[MatchupGroup, ...]:
        """Rosters drawn at least `min_opponents` times, hardest first.

        The pool holds many near-copies -- one player's team reconstructed from
        several replays -- so a roster drawn four times is one eight-battle
        matchup, not four two-battle ones. Order-insensitive: the same six in a
        different order are the same roster.
        """
        return _grouped(self.matchups, lambda m: [tuple(sorted(m.roster))], min_opponents)

    def by_species(self, min_opponents: int = 15) -> tuple[MatchupGroup, ...]:
        """One group per opposing species, over every opponent that brought it,
        hardest first.

        Screening every species at once will turn up a few low ones by chance;
        a group is a suspect to re-test on fresh seeds, not a finding.
        """
        return _grouped(
            self.matchups, lambda m: [(species,) for species in sorted(set(m.roster))],
            min_opponents,
        )

    def even(self) -> int:
        """Matchups split one-all. With identical agents these are the ones the
        two teams genuinely cannot separate, rather than the ones we got lucky
        in."""
        return sum(1 for m in self.matchups if m.battles == 2 and m.wins == 1)


def scout_team(
    env: BattleEnv,
    agent: Agent,
    team: BattleTeam,
    pool: TeamPool,
    *,
    opponents: int = 40,
    seed: int = 0,
    on_progress=None,
) -> TeamReport:
    """Play `team` against a sample of the pool, from both seats.

    The same agent plays both sides on purpose. A different agent on the far
    side would measure the team *and* the policy gap together, and there would
    be no way to say which moved.
    """
    import random

    rng = random.Random(seed)
    indices = list(range(len(pool.teams)))
    rng.shuffle(indices)
    chosen = indices[:opponents]

    matchups: list[Matchup] = []
    wins = draws = battles = 0

    for number, index in enumerate(chosen):
        other = pool.teams[index]
        name = other.name or f"team-{index}"
        won = 0
        for seat in (0, 1):
            # Same seed for both seats, so the pair differs in nothing but
            # which side of the field each team started on.
            battle_seed = f"sodium,{(seed * 1000 + number):032x}"
            teams = (team, other) if seat == 0 else (other, team)
            result = play_battle(env, (agent, agent), teams, seed=battle_seed)
            battles += 1
            if result.winner is None:
                draws += 1
            elif result.winner == seat:
                won += 1
                wins += 1
        matchups.append(
            Matchup(
                opponent=name,
                roster=tuple(e.species for e in other.team.pokemon),
                wins=won,
                battles=2,
            )
        )
        if on_progress is not None:
            on_progress(number + 1, len(chosen), wins, battles)

    return TeamReport(
        team=team.name or "your team",
        battles=battles,
        wins=wins,
        draws=draws,
        opponents=len(chosen),
        matchups=tuple(matchups),
    )
