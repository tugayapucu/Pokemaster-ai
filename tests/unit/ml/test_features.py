"""Action features. Their job is to describe what the heuristic already sees,
so a learned mapping can be compared against a hand-written one on identical
information (experiment 0005)."""

from champions_ai.data.reconstruct import move_data_from_dex
from champions_ai.domain import MoveAction, SwitchAction
from champions_ai.ml.features import FEATURE_NAMES, FeatureExtractor


def _extractor(battle):
    return FeatureExtractor(battle.dex, move_data_from_dex(battle.dex))


def test_every_vector_has_the_declared_length(battle):
    decision = battle.at(battle.decisions(), 1, 0)
    vector = _extractor(battle)(decision.observation, 0, MoveAction(move_index=0))
    assert len(vector) == len(FEATURE_NAMES)
    assert all(isinstance(v, float) for v in vector)


def test_the_bias_term_is_always_one(battle):
    decision = battle.at(battle.decisions(), 1, 0)
    vector = _extractor(battle)(decision.observation, 0, MoveAction(move_index=0))
    assert vector[FEATURE_NAMES.index("bias")] == 1.0


def test_a_move_and_a_switch_are_distinguishable(battle):
    decision = battle.at(battle.decisions(), 1, 0)
    extractor = _extractor(battle)
    move = extractor(decision.observation, 0, MoveAction(move_index=0))
    switch = extractor(decision.observation, 0, SwitchAction(team_index=2))
    assert move[FEATURE_NAMES.index("is_move")] == 1.0
    assert move[FEATURE_NAMES.index("is_switch")] == 0.0
    assert switch[FEATURE_NAMES.index("is_switch")] == 1.0
    assert switch[FEATURE_NAMES.index("is_move")] == 0.0


def test_the_heuristic_score_is_carried_as_a_feature(battle):
    """It is what lets a linear model reproduce the heuristic exactly, so any
    gain is a gain *over* it rather than a rediscovery of it."""
    from champions_ai.agents import HeuristicAgent
    from champions_ai.ml.features import HEURISTIC_SCALE

    decision = battle.at(battle.decisions(), 1, 0)
    action = MoveAction(move_index=0)
    vector = _extractor(battle)(decision.observation, 0, action)
    expected = HeuristicAgent(battle.dex, name="x").score_slot_action(
        decision.observation, 0, action
    ).score
    assert vector[FEATURE_NAMES.index("heuristic_score")] == expected / HEURISTIC_SCALE


def test_features_are_finite_for_every_legal_action(battle):
    """A NaN or infinity anywhere poisons the whole softmax silently."""
    import math

    from champions_ai.domain.legal_actions import legal_slot_actions

    move_data = move_data_from_dex(battle.dex)
    extractor = FeatureExtractor(battle.dex, move_data)
    for decision in battle.decisions():
        for slot in range(2):
            for action in legal_slot_actions(decision.observation, slot, move_data):
                for value in extractor(decision.observation, slot, action):
                    assert math.isfinite(value)
