"""Not every engine error is a rejection.

Showdown distinguishes two failures in `Side.emitChoiceError`:

    const updated = update ? this.updateRequestForPokemon(...) : null;
    const type = `[${updated ? 'Unavailable' : 'Invalid'} choice]`;
    if (updated) this.emitRequest(this.activeRequest!, true);

**Invalid** means the choice was never legal, which is our bug. **Unavailable**
means it was legal for the request we were given, and the engine has since
corrected that request and re-emitted it -- so the answer is to choose again,
not to fail. Showdown's own reference agent ignores Unavailable errors for
exactly this reason.

This was seen three times as

    [Unavailable choice] Can't move: <X>'s Protect is disabled

and misread as a legality bug, because `updateDisabledRequest` is one of the
two things that triggers it. Two fixes aimed at legality did not cure it, and
an invariant check over 425,008 joint actions found `legal_actions` had never
once offered a disabled move.
"""

import pytest

from champions_ai.domain import REGULATION_M_B
from champions_ai.env import BattleEnv
from champions_ai.simulator.bridge import BridgeError


@pytest.fixture
def env() -> BattleEnv:
    # No battle is started, so no subprocess is spawned; `_absorb` only reads
    # the events it is handed.
    return BattleEnv(REGULATION_M_B)


def _error(message: str) -> dict:
    return {"type": "error", "message": message}


def _request(player: str) -> dict:
    return {"type": "request", "player": player, "request": {}}


class TestUnavailableIsNotARejection:
    def test_a_superseded_request_does_not_raise(self, env):
        env._absorb([_error("[Unavailable choice] Can't move: Protect is disabled")])
        assert env.stale_requests == 1

    def test_the_corrected_request_puts_the_player_back_in_pending(self, env):
        """The engine re-emits the request in the same batch, so the caller
        chooses again against the fixed view rather than losing the turn."""
        env._absorb(
            [
                _error("[Unavailable choice] Can't move: Protect is disabled"),
                _request("p1"),
            ]
        )
        # `awaiting()` needs a started battle; the pending set is the state
        # it reports, and is what decides whether the caller re-chooses.
        assert env._pending == {0}

    def test_they_are_counted_rather_than_swallowed(self, env):
        for _ in range(3):
            env._absorb([_error("[Unavailable choice] Can't move: X is disabled")])
        assert env.stale_requests == 3


class TestInvalidStillFailsLoudly:
    def test_an_invalid_choice_raises(self, env):
        with pytest.raises(BridgeError, match="Invalid choice"):
            env._absorb([_error("[Invalid choice] Can't move: Invalid target for Helping Hand")])

    def test_an_unrecognised_error_raises(self, env):
        """Anything not explicitly marked Unavailable keeps the old behaviour:
        a disagreement with the engine stays visible."""
        with pytest.raises(BridgeError):
            env._absorb([_error("something else went wrong")])

    def test_invalid_is_not_counted_as_stale(self, env):
        with pytest.raises(BridgeError):
            env._absorb([_error("[Invalid choice] nope")])
        assert env.stale_requests == 0
