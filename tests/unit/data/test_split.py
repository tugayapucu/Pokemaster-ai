"""Dividing the corpus.

The failures this guards against are both silent: a split that leaks
near-duplicate decisions across the boundary, and a split that reshuffles when
the corpus grows so that yesterday's model is graded on games it trained on.
"""

import pytest

from champions_ai.data.replay import Replay, ReplayMetadata
from champions_ai.data.split import is_test, split_replays


def _replay(replay_id, players=("alice", "bob")):
    return Replay(
        metadata=ReplayMetadata(
            replay_id=replay_id, format_id="gen9championsvgc2026regmb",
            players=players, ratings=(1600, 1600), upload_time=0, rated=True,
        ),
        log=("|turn|1",),
    )


CORPUS = [_replay(f"game-{i}") for i in range(500)]


def test_roughly_the_requested_fraction_lands_in_test():
    split = split_replays(CORPUS, test_fraction=0.2)
    assert 0.15 < len(split.test) / len(CORPUS) < 0.25


def test_every_replay_goes_to_exactly_one_side():
    split = split_replays(CORPUS, test_fraction=0.2)
    assert len(split.train) + len(split.test) == len(CORPUS)
    ids = {r.metadata.replay_id for r in split.train} & {
        r.metadata.replay_id for r in split.test
    }
    assert not ids


def test_the_split_is_stable_when_the_corpus_grows():
    """The property that matters most. A shuffled split would reassign
    everything, so a model trained last week would be evaluated on games it had
    already trained on."""
    small = split_replays(CORPUS[:100], test_fraction=0.2)
    large = split_replays(CORPUS, test_fraction=0.2)

    small_test = {r.metadata.replay_id for r in small.test}
    large_test = {r.metadata.replay_id for r in large.test}
    for replay in CORPUS[:100]:
        was_test = replay.metadata.replay_id in small_test
        still_test = replay.metadata.replay_id in large_test
        assert was_test == still_test, f"{replay.metadata.replay_id} changed sides"


def test_the_split_does_not_depend_on_input_order():
    forward = split_replays(CORPUS, test_fraction=0.2)
    backward = split_replays(list(reversed(CORPUS)), test_fraction=0.2)
    assert {r.metadata.replay_id for r in forward.test} == {
        r.metadata.replay_id for r in backward.test
    }


def test_assignment_is_reproducible_across_runs():
    assert is_test("game-1") == is_test("game-1")
    assert [is_test(f"game-{i}") for i in range(20)] == [
        is_test(f"game-{i}") for i in range(20)
    ]


def test_a_bigger_test_fraction_is_a_superset():
    """Widening the test share must only ever move replays into it."""
    narrow = {r.metadata.replay_id for r in split_replays(CORPUS, test_fraction=0.1).test}
    wide = {r.metadata.replay_id for r in split_replays(CORPUS, test_fraction=0.3).test}
    assert narrow < wide


def test_shared_players_are_reported_not_hidden():
    """A replay-level split does not separate players, and pretending otherwise
    would overstate how held-out the test set is."""
    corpus = [_replay(f"g{i}", players=("repeat", f"other{i}")) for i in range(200)]
    split = split_replays(corpus, test_fraction=0.2)
    assert "repeat" in split.shared_players
    assert "both sides" in split.summary()


def test_an_impossible_fraction_is_rejected():
    for bad in (0.0, 1.0, -0.1, 1.5):
        with pytest.raises(ValueError):
            split_replays(CORPUS, test_fraction=bad)
