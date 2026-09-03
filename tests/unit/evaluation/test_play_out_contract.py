"""What `play_out` promises about agent state, pinned rather than assumed.

Every fork-based measurement (0038, 0039) finishes a reproduced position with
freshly built agents and never calls `on_battle_start`. That is only sound
while the agent carries nothing between turns. `HeuristicAgent` carries the
previous observation, and it is read solely by `_learn_from`, which returns
immediately while `belief` is None -- so the agent is stateless at its shipped
settings and a fresh one plays the same as one that saw the prefix.

These tests hold both halves of that in place: the lifecycle contract, and the
statelessness it relies on. If `infer_spreads` were ever turned on by default,
the second one fails and says why.
"""

from tests.conftest import DEX

from champions_ai.agents.base import Agent
from champions_ai.agents.heuristic import HeuristicAgent
from champions_ai.evaluation import play_out


class _Recorder(Agent):
    """Counts lifecycle calls; never asked to choose, because nothing is waiting."""

    def __init__(self) -> None:
        self.name = "recorder"
        self.starts = 0

    def on_battle_start(self) -> None:
        self.starts += 1

    def select_action(self, observation, legal_actions):  # pragma: no cover
        raise AssertionError("a finished battle should never ask for an action")


class _FinishedEnv:
    """The smallest thing `play_out` will accept: a battle already over."""

    terminal = True
    winner = 0
    turn = 7
    protocol = ("|win|P1",)

    def awaiting(self):  # pragma: no cover - terminal short-circuits first
        return ()


def test_play_out_does_not_start_a_battle_the_agent_is_joining_midway():
    agents = (_Recorder(), _Recorder())

    play_out(_FinishedEnv(), agents)

    assert [a.starts for a in agents] == [0, 0], (
        "play_out reset the agents; a fork continues a battle rather than starting one"
    )


def test_play_out_reports_the_env_state_it_found():
    result = play_out(_FinishedEnv(), (_Recorder(), _Recorder()))

    assert result.terminal
    assert result.winner == 0
    assert result.turn == 7


def test_the_shipped_heuristic_carries_nothing_between_turns():
    """The assumption every fork-based rollout rests on.

    If this fails, `infer_spreads` has been turned on by default and rollouts
    from a fork are no longer measuring the agent that played the prefix --
    a fresh agent would start blank where the real one had learned.
    """
    agent = HeuristicAgent(DEX)

    assert agent.belief is None
    assert agent.infer_spreads is False
