"""Which way a tie between Mega Evolving and not is broken.

The scorer prices a Mega only through this turn's move, so on a Protect turn --
or with a move the forme does not strengthen -- `X` and `X + Mega` score exactly
the same. `select_action` kept the first of equal totals and the enumeration
lists the non-Mega first, so the tie always went against the Mega, while players
Mega on a Pokemon's first turn out 88.9% of the time (Reg M-C corpus).

`mega_on_ties` breaks those ties toward the Mega, and only those. When the
non-Mega action scores strictly higher -- a move this turn is genuinely better
thrown by the base forme -- the scorer's answer stands.
"""

from champions_ai.agents import HeuristicAgent
from champions_ai.agents.heuristic import ScoredAction
from champions_ai.dex import Dex, TypeChart
from champions_ai.domain import JointAction, MoveAction, PassAction
from champions_ai.recommendation.recommender import _drop_indistinguishable, _ranked

DEX = Dex(species={}, moves={}, types=("Normal",),
          type_chart=TypeChart(multipliers={"Normal": {"Normal": 1.0}}), items={})

PLAIN = JointAction(slot_actions=(MoveAction(move_index=0), PassAction()))
MEGA = JointAction(slot_actions=(MoveAction(move_index=0, special="mega"), PassAction()))


def _agent(scores: dict, **kwargs) -> HeuristicAgent:
    """An agent whose per-slot scores are fixed, so only the tie-break is under test."""
    agent = HeuristicAgent(DEX, **kwargs)

    def score_slot_action(observation, slot, action):
        if isinstance(action, PassAction):
            return ScoredAction(action, 0.0)
        return ScoredAction(action, scores[action.special])

    agent.score_slot_action = score_slot_action
    return agent


def test_by_default_a_tie_still_goes_to_the_action_listed_first():
    agent = _agent({None: 10.0, "mega": 10.0})
    assert agent.select_action(None, [PLAIN, MEGA]) == PLAIN


def test_with_mega_on_ties_a_tie_goes_to_the_mega():
    agent = _agent({None: 10.0, "mega": 10.0}, mega_on_ties=True)
    assert agent.select_action(None, [PLAIN, MEGA]) == MEGA


def test_the_order_actions_are_listed_in_does_not_matter_once_it_is_on():
    agent = _agent({None: 10.0, "mega": 10.0}, mega_on_ties=True)
    assert agent.select_action(None, [MEGA, PLAIN]) == MEGA


def test_a_strictly_better_non_mega_action_still_wins():
    """Only ties move. A turn where the scorer says Mega Evolving is worse keeps
    its answer, even with the setting on."""
    agent = _agent({None: 10.5, "mega": 10.0}, mega_on_ties=True)
    assert agent.select_action(None, [PLAIN, MEGA]) == PLAIN


def test_a_strictly_better_mega_wins_either_way():
    for setting in (False, True):
        agent = _agent({None: 10.0, "mega": 12.0}, mega_on_ties=setting)
        assert agent.select_action(None, [PLAIN, MEGA]) == MEGA


def _scored(*rows):
    return [(action, (score, ())) for action, score in rows]


def test_advice_keeps_the_simpler_action_on_a_tie_by_default():
    ranked = _drop_indistinguishable(_ranked(_scored((MEGA, 10.0), (PLAIN, 10.0))))
    assert [action for action, _ in ranked] == [PLAIN]


def test_advice_keeps_the_mega_on_a_tie_when_preferred():
    ranked = _drop_indistinguishable(
        _ranked(_scored((PLAIN, 10.0), (MEGA, 10.0)), prefer_mega=True)
    )
    assert [action for action, _ in ranked] == [MEGA]


def test_advice_still_ranks_by_score_first():
    ranked = _ranked(_scored((MEGA, 9.0), (PLAIN, 10.0)), prefer_mega=True)
    assert [action for action, _ in ranked] == [PLAIN, MEGA]
