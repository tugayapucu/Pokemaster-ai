"""The learned policy: a conditional softmax over the legal actions in a slot.

The candidate set changes from decision to decision, so this ranks actions
against each other rather than classifying into fixed categories. Most of the
risk lives in that shape rather than in the arithmetic.
"""

import json
import math

import pytest

from champions_ai.ml.features import FEATURE_NAMES
from champions_ai.ml.policy import LinearPolicy, TrainingExample, softmax, train


def test_softmax_is_a_distribution():
    for scores in ([1.0, 2.0, 3.0], [0.0], [-5.0, 5.0]):
        p = softmax(scores)
        assert math.isclose(sum(p), 1.0)
        assert all(0.0 <= x <= 1.0 for x in p)


def test_softmax_survives_scores_that_would_overflow_exp():
    """exp(1000) is inf; subtracting the max is what stops that."""
    p = softmax([1000.0, 1001.0])
    assert math.isclose(sum(p), 1.0)
    assert p[1] > p[0]


def test_an_example_must_point_at_one_of_its_own_candidates():
    """A softmax needs its target inside its candidate set; without this the
    gradient pushes mass away from every option indiscriminately."""
    with pytest.raises(ValueError):
        TrainingExample(features=[[1.0], [2.0]], chosen=5)


def test_training_learns_a_feature_that_separates_the_answer():
    examples = [
        TrainingExample(features=[[1.0, 0.0], [1.0, 1.0]], chosen=1) for _ in range(200)
    ]
    policy = train(examples, epochs=30, learning_rate=0.2, l2=0.0)
    assert policy.score([1.0, 1.0]) > policy.score([1.0, 0.0])
    assert policy.probabilities([[1.0, 0.0], [1.0, 1.0]])[1] > 0.9


def test_training_stays_neutral_when_the_feature_says_nothing():
    """Alternating labels on identical features must not produce a preference."""
    examples = [
        TrainingExample(features=[[1.0, 0.0], [1.0, 1.0]], chosen=i % 2)
        for i in range(200)
    ]
    policy = train(examples, epochs=30, learning_rate=0.2, l2=0.0)
    probabilities = policy.probabilities([[1.0, 0.0], [1.0, 1.0]])
    assert abs(probabilities[0] - probabilities[1]) < 0.25


def test_loss_falls_over_training():
    examples = [
        TrainingExample(features=[[1.0, 0.0], [1.0, 1.0]], chosen=1) for _ in range(100)
    ]
    seen = []
    train(examples, epochs=15, learning_rate=0.2, l2=0.0,
          on_epoch=lambda epoch, loss: seen.append(loss))
    assert seen[-1] < seen[0]


def test_candidate_sets_may_differ_in_size_between_examples():
    """The real data does this constantly -- a slot with three options and one
    with nine are both single training examples."""
    examples = [
        TrainingExample(features=[[1.0, 0.0], [1.0, 1.0]], chosen=1),
        TrainingExample(features=[[1.0, 0.0], [1.0, 0.0], [1.0, 1.0]], chosen=2),
    ] * 100
    policy = train(examples, epochs=20, learning_rate=0.2, l2=0.0)
    assert policy.score([1.0, 1.0]) > policy.score([1.0, 0.0])


def test_weights_round_trip_through_disk(tmp_path):
    policy = LinearPolicy(weights=[float(i) for i in range(len(FEATURE_NAMES))])
    path = tmp_path / "p.json"
    policy.save(path)
    assert LinearPolicy.load(path).weights == policy.weights


def test_weights_saved_under_a_different_feature_set_are_rejected(tmp_path):
    """Reusing them silently would apply each weight to the wrong input and
    produce a plausible-looking model rather than an error."""
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"feature_names": ["a", "b"], "weights": [1.0, 2.0]}))
    with pytest.raises(ValueError, match="retrain"):
        LinearPolicy.load(path)


# ------------------------------------------------------------- the agent itself


class _Constant:
    """A stand-in extractor: one feature, its value read off the action index."""

    def __call__(self, observation, slot, action):
        index = getattr(action, "move_index", 0)
        return [float(index)]


def test_the_agent_picks_the_highest_scoring_joint_action(battle):
    from champions_ai.data.reconstruct import move_data_from_dex
    from champions_ai.domain.legal_actions import legal_joint_actions
    from champions_ai.ml.policy import LinearPolicy, LinearPolicyAgent

    decision = battle.at(battle.decisions(), 1, 0)
    move_data = move_data_from_dex(battle.dex)
    legal = legal_joint_actions(decision.observation, move_data)

    # Positive weight prefers higher move indices; negative prefers lower.
    high = LinearPolicyAgent(LinearPolicy(weights=[1.0], feature_names=("f0",)), _Constant())
    low = LinearPolicyAgent(LinearPolicy(weights=[-1.0], feature_names=("f0",)), _Constant())

    def total(agent, chosen):
        return sum(agent.slot_score(decision.observation, slot, action)
                   for slot, action in enumerate(chosen.slot_actions))

    picked_high = high.select_action(decision.observation, legal)
    picked_low = low.select_action(decision.observation, legal)
    assert total(high, picked_high) >= total(high, picked_low)
    assert total(low, picked_low) >= total(low, picked_high)


def test_the_agent_always_returns_one_of_the_legal_actions(battle):
    """The Agent contract. Returning anything else is rejected by the engine."""
    from champions_ai.data.reconstruct import move_data_from_dex
    from champions_ai.domain.legal_actions import legal_joint_actions
    from champions_ai.ml.policy import LinearPolicy, LinearPolicyAgent

    move_data = move_data_from_dex(battle.dex)
    agent = LinearPolicyAgent(LinearPolicy(weights=[0.5], feature_names=("f0",)), _Constant())
    for decision in battle.decisions():
        legal = legal_joint_actions(decision.observation, move_data)
        assert agent.select_action(decision.observation, legal) in legal


def test_named_weights_pair_each_value_with_its_feature():
    from champions_ai.ml.policy import LinearPolicy

    policy = LinearPolicy(weights=[1.0, 2.0], feature_names=("a", "b"))
    assert policy.named_weights() == {"a": 1.0, "b": 2.0}
