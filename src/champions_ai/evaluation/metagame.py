"""What is the field actually bringing?

`scout` grades a team that already exists. This is the half before it: a player
choosing what to build has 5,858 harvested exports and no way to look at them.

Counted from the **replays**, not the harvested pool, because a replay carries
two things the pool cannot. Both sides' declared six come from the `|poke|`
lines, which every replay has and which no player can hide -- so usage here is
what people *brought to Team Preview*, not what happened to be revealed in
play. And the replay records who won, which turns usage into a win rate.

## What the numbers are worth

**Usage is solid.** The `|poke|` lines are complete for both sides in every
replay in this corpus, so a species' usage share is a fact about the sample.

**Win rate is not a verdict, for three reasons stated here rather than
discovered later.**

- It is confounded. A species that strong players favour will show a high win
  rate whether or not it causes any of those wins. 0044 found agreement flat
  across 800 Elo, which makes the confound smaller on this ladder than it
  would be on a settled one -- smaller, not gone.
- The interval is wide for anything uncommon. A species in forty games says
  much less than one in four hundred, and the Wilson interval is reported for
  exactly that reason.
- The corpus is what it is: Reg M-C, days old, rated 1000-1400. This describes
  a young ladder, not a Regional.

Pairing counts are lift, not raw frequency: two popular species appear together
often simply by being popular, so the useful question is whether they appear
together *more* than that.
"""

from collections import Counter
from dataclasses import dataclass, field

from champions_ai.data.replay import Replay
from champions_ai.data.split import declared_rosters
from champions_ai.evaluation.runner import wilson_interval


@dataclass(frozen=True)
class SpeciesUsage:
    """One species, across the corpus."""

    species: str
    teams: int
    wins: int
    decided: int

    @property
    def win_rate(self) -> float:
        return self.wins / self.decided if self.decided else 0.0

    @property
    def interval(self) -> tuple[float, float]:
        return wilson_interval(self.wins, self.decided)


@dataclass(frozen=True)
class MetagameReport:
    replays: int
    teams: int
    usage: tuple[SpeciesUsage, ...] = field(default=(), repr=False)
    pairs: dict[tuple[str, str], int] = field(default_factory=dict, repr=False)

    def share(self, entry: SpeciesUsage) -> float:
        return entry.teams / self.teams if self.teams else 0.0

    def most_used(self, count: int = 20) -> tuple[SpeciesUsage, ...]:
        return tuple(sorted(self.usage, key=lambda u: -u.teams)[:count])

    def by_win_rate(self, count: int = 15, minimum: int = 60) -> tuple[SpeciesUsage, ...]:
        """Best win rate, ranked by the **lower bound** of the interval.

        Ranking by the rate itself is a trap, and a loud one in this corpus:
        there are several hundred species, so taking the top ten by point
        estimate selects whichever handful got lucky in sixty games. The first
        run of this report put Empoleon (62 games), Oranguru (65) and Vanilluxe
        (62) above Camerupt (219) -- the three smallest samples on the page.

        The lower bound asks a better question: *how good is this species at
        worst, given how often it was seen?* A species needs both a high rate
        and enough games to clear it, which is exactly the pairing a team
        builder wants and the point estimate cannot express.

        `minimum` is a floor on **decided** games rather than on teams: a
        species that keeps appearing in unfinished replays has not been
        measured.
        """
        eligible = [u for u in self.usage if u.decided >= minimum]
        return tuple(
            sorted(eligible, key=lambda u: (-u.interval[0], -u.decided))[:count]
        )

    def partners(self, species: str, count: int = 10) -> tuple[tuple[str, int, float], ...]:
        """Who this species is brought with, by **lift** over chance.

        Raw co-occurrence just re-lists the popular species. Lift asks whether
        the pair appears more often than two independent picks of that
        popularity would produce, which is the question a team builder has.
        """
        by_name = {u.species: u for u in self.usage}
        target = by_name.get(species)
        if target is None or not self.teams:
            return ()
        found: list[tuple[str, int, float]] = []
        for (a, b), together in self.pairs.items():
            if species not in (a, b):
                continue
            other = b if a == species else a
            partner = by_name.get(other)
            if partner is None:
                continue
            expected = target.teams * partner.teams / self.teams
            if expected <= 0:
                continue
            found.append((other, together, together / expected))
        return tuple(sorted(found, key=lambda row: (-row[2], -row[1]))[:count])


def survey(replays: list[Replay], *, pair_minimum: int = 40) -> MetagameReport:
    """Count species, wins and pairings across a corpus of replays.

    `pair_minimum` drops pairs seen too rarely for their lift to mean anything.
    It is the same trap as ranking win rate by point estimate, one level down:
    at a floor of 8 this report put Florges (18 co-occurrences) and
    Persian-Alola (11) at the top of Rillaboom's partners, above Incineroar at
    1,200. A ratio computed from eleven observations is noise wearing a
    decimal point.
    """
    teams = 0
    brought: Counter = Counter()
    won: Counter = Counter()
    decided: Counter = Counter()
    pairs: Counter = Counter()

    for replay in replays:
        rosters = declared_rosters(replay)
        if len(rosters) != 2:
            continue
        winner = replay.winner
        names = replay.metadata.players
        # Which side won, if either. A replay with no `|win|` line, or a winner
        # whose name matches neither player, contributes usage but no outcome:
        # counting it as a loss for both sides would drag every win rate down.
        winning_side = None
        if winner and winner in names:
            winning_side = names.index(winner)

        for side, roster in enumerate(rosters):
            teams += 1
            for species in roster:
                brought[species] += 1
                if winning_side is not None:
                    decided[species] += 1
                    if side == winning_side:
                        won[species] += 1
            ordered = sorted(roster)
            for i, a in enumerate(ordered):
                for b in ordered[i + 1:]:
                    pairs[(a, b)] += 1

    usage = tuple(
        SpeciesUsage(species=s, teams=n, wins=won[s], decided=decided[s])
        for s, n in brought.items()
    )
    return MetagameReport(
        replays=len(replays),
        teams=teams,
        usage=usage,
        pairs={pair: n for pair, n in pairs.items() if n >= pair_minimum},
    )
