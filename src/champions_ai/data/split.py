"""Divide the replay corpus into train and test.

Two decisions here matter more than they look.

**Split by replay, never by decision.** Turns within one battle share a team, a
matchup and a player, so a decision-level split puts near-duplicates on both
sides and quietly inflates every test score.

**Assign by hash, never by shuffle.** A shuffled split reassigns every replay
the moment the corpus grows, so a model trained last week would be evaluated on
games it had trained on. Hashing the replay id fixes each game's side for good:
collecting more replays adds to both halves and moves nothing between them.
"""

import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from champions_ai.data.replay import Replay

DEFAULT_TEST_FRACTION = 0.2
# Changing this reshuffles the whole corpus, which invalidates every result
# measured against the old split. It is a constant rather than a parameter for
# that reason.
SPLIT_SALT = "champions-ai/v1"


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

    def summary(self) -> str:
        return (
            f"train {len(self.train)} / test {len(self.test)} replays "
            f"({len(self.test) / max(1, len(self.train) + len(self.test)):.0%} test); "
            f"{len(self.shared_players)} players appear on both sides"
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
