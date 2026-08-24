"""Divide the replay corpus into train and test.

Two decisions here matter more than they look.

**Split by replay, never by decision.** Turns within one battle share a team, a
matchup and a player, so a decision-level split puts near-duplicates on both
sides and quietly inflates every test score.

**Assign by hash, never by shuffle.** A shuffled split reassigns every replay
the moment the corpus grows, so a model trained last week would be evaluated on
games it had trained on. Hashing the replay id fixes each game's side for good:
collecting more replays adds to both halves and moves nothing between them.

**Splitting by team is impossible here, and that is measured rather than
assumed.** A replay-level split does not separate *teams*: 80 rosters appear on
both sides, and 74.2% of test-side roster appearances also occur in train. The
obvious fix is to group replays so a roster lands wholly on one side -- but
every replay has two rosters, so replays chain. A brings X and Y, B brings Y
and Z, and now A and B must share a side. On this corpus that chaining runs
away:

    500 replays -> 46 components, the largest holding 427 (85.4%)
    a strict team-disjoint test set could reach 14.6% at most

and those 73 replays would be the *least* connected ones -- obscure teams and
one-off players -- so the test set would be small and unrepresentative at once.

So the leakage is reported rather than prevented, which is already the stance
this module takes on players. `unseen_team_test` is the subset of test replays
whose rosters never appear in train, and comparing agreement on it against
agreement on the whole test half says directly how much the leakage inflates a
figure. A number you can check beats a split you cannot build.
"""

import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from champions_ai.data.replay import Replay
from champions_ai.simulator.tracker import species_from_details, to_id

DEFAULT_TEST_FRACTION = 0.2
# Changing this reshuffles the whole corpus, which invalidates every result
# measured against the old split. It is a constant rather than a parameter for
# that reason.
SPLIT_SALT = "champions-ai/v1"


def declared_rosters(replay: Replay) -> tuple[frozenset[str], ...]:
    """Each side's declared six, from Team Preview.

    The `|poke|` lines carry it and every replay in the corpus has them for
    both sides, which makes this a clean team identity -- unlike the four
    actually brought, which is a choice made *within* the battle and differs
    between two games on the same team.
    """
    by_side: dict[str, set[str]] = {}
    for line in replay.log:
        if not line.startswith("|poke|"):
            continue
        parts = line.split("|")
        if len(parts) > 3:
            by_side.setdefault(parts[2], set()).add(
                to_id(species_from_details(parts[3]))
            )
    return tuple(frozenset(mons) for _, mons in sorted(by_side.items()) if mons)


def _bucket(replay_id: str) -> float:
    """A stable number in [0, 1) for one replay, independent of corpus order."""
    digest = hashlib.sha256(f"{SPLIT_SALT}:{replay_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def is_test(replay_id: str, *, test_fraction: float = DEFAULT_TEST_FRACTION) -> bool:
    return _bucket(replay_id) < test_fraction


@dataclass(frozen=True)
class CorpusSplit:
    """One deterministic division of the corpus."""

    train: tuple[Replay, ...]
    test: tuple[Replay, ...]
    test_fraction: float

    @property
    def shared_players(self) -> set[str]:
        """Players appearing on both sides.

        A replay-level split does not guarantee player-level separation, and a
        model can learn one strong player's habits and be graded on that same
        player elsewhere. Reported rather than prevented: excluding them costs
        real data, and the honest move is to know the number.
        """
        def names(replays: Iterable[Replay]) -> set[str]:
            return {name for r in replays for name in r.metadata.players if name}

        return names(self.train) & names(self.test)

    @property
    def shared_rosters(self) -> set[frozenset[str]]:
        """Teams appearing on both sides.

        The same argument as `shared_players`, and a stronger effect: a player
        can change teams, but a team is exactly what an agent could memorise.
        """
        def teams(replays: Iterable[Replay]) -> set[frozenset[str]]:
            return {roster for r in replays for roster in declared_rosters(r)}

        return teams(self.train) & teams(self.test)

    @property
    def unseen_team_test(self) -> tuple[Replay, ...]:
        """Test replays where *neither* team was ever seen in training.

        Two of them, on this corpus. Kept because the number itself is the
        finding: a whole-replay clean subset does not exist here, which is why
        `unseen_team_sides` exists and is the one to measure against.
        """
        seen = self._trained_rosters()
        return tuple(
            r for r in self.test
            if not any(roster in seen for roster in declared_rosters(r))
        )

    @property
    def unseen_team_sides(self) -> tuple[tuple[Replay, int], ...]:
        """(replay, player) pairs whose *own* team never appeared in training.

        The usable clean subset, and the reason it is per-player rather than
        per-replay: 55 test replays have both teams already seen and only two
        have neither, but **38 have exactly one**. Scoring just that player's
        decisions gives a real measurement where scoring whole replays gives
        almost nothing.

        The opponent's team may still be familiar, so this is not perfectly
        clean -- it isolates "we have never seen the team making these
        decisions", which is the half that matters for an agent meant to
        handle a variety of teams.
        """
        seen = self._trained_rosters()
        found = []
        for replay in self.test:
            for player, roster in enumerate(declared_rosters(replay)):
                if roster not in seen:
                    found.append((replay, player))
        return tuple(found)

    def _trained_rosters(self) -> set[frozenset[str]]:
        return {roster for r in self.train for roster in declared_rosters(r)}

    def summary(self) -> str:
        clean = len(self.unseen_team_test)
        return (
            f"train {len(self.train)} / test {len(self.test)} replays "
            f"({len(self.test) / max(1, len(self.train) + len(self.test)):.0%} test); "
            f"{len(self.shared_players)} players and {len(self.shared_rosters)} "
            f"teams appear on both sides; "
            f"{clean} test replays bring a team never seen in training, "
            f"and {len(self.unseen_team_sides)} player-sides do"
        )


def split_replays(
    replays: Sequence[Replay], *, test_fraction: float = DEFAULT_TEST_FRACTION
) -> CorpusSplit:
    """Divide by replay id hash, stably under corpus growth."""
    if not 0.0 < test_fraction < 1.0:
        raise ValueError(f"test_fraction must be between 0 and 1, got {test_fraction}")
    test = tuple(r for r in replays if is_test(r.metadata.replay_id, test_fraction=test_fraction))
    train = tuple(
        r for r in replays if not is_test(r.metadata.replay_id, test_fraction=test_fraction)
    )
    return CorpusSplit(train=train, test=test, test_fraction=test_fraction)
