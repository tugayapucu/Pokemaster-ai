"""Turning reconstructed decisions into training examples.

The rule that matters is the one that drops a decision when the human's action
is not among the candidates. A softmax needs its target inside its own candidate
set; training on a decision whose right answer is absent pushes probability mass
away from every option indiscriminately, which is a silent corruption of the
model rather than an error.
"""

from champions_ai.data.reconstruct import move_data_from_dex
from champions_ai.ml import FeatureExtractor, build_examples
from champions_ai.ml.features import FEATURE_NAMES


def _setup(battle):
    move_data = move_data_from_dex(battle.dex)
    return battle.decisions(), FeatureExtractor(battle.dex, move_data), move_data


def test_examples_are_built_from_real_decisions(battle):
    decisions, extractor, move_data = _setup(battle)
    examples = build_examples(decisions, extractor, move_data)
    assert examples


def test_every_example_points_at_one_of_its_own_candidates(battle):
    """The invariant the softmax depends on."""
    decisions, extractor, move_data = _setup(battle)
    for example in build_examples(decisions, extractor, move_data):
        assert 0 <= example.chosen < len(example.features)


def test_every_candidate_has_the_declared_feature_width(battle):
    decisions, extractor, move_data = _setup(battle)
    for example in build_examples(decisions, extractor, move_data):
        for vector in example.features:
            assert len(vector) == len(FEATURE_NAMES)


def test_a_decision_with_one_option_is_not_an_example(battle):
    """Nothing was decided, so there is nothing to learn from it."""
    decisions, extractor, move_data = _setup(battle)
    for example in build_examples(decisions, extractor, move_data):
        assert len(example.features) >= 2


def test_forced_choices_are_excluded_by_default(battle):
    """A replacement after a faint is a decision, but a different one."""
    log = (
        *battle.through("|turn|2"),
        "|move|p2a: Incineroar|Knock Off|p1b: Garchomp",
        "|faint|p1b: Garchomp",
        "|switch|p1b: Dragonite|Dragonite, L50, M|100/100",
        "|turn|3",
    )
    decisions = battle.decisions(log)
    move_data = move_data_from_dex(battle.dex)
    extractor = FeatureExtractor(battle.dex, move_data)
    default = build_examples(decisions, extractor, move_data)
    included = build_examples(decisions, extractor, move_data, free_choices_only=False)
    assert len(included) >= len(default)


def test_a_move_missing_from_the_dex_is_skipped_not_fatal(battle):
    """A stale dex must not abort a whole training run."""
    log = (
        *battle.through("|turn|1"),
        "|move|p1a: Charizard|Hyper Beam|p2a: Incineroar",
        "|move|p1b: Garchomp|Protect",
        "|turn|2",
    )
    decisions = battle.decisions(log)
    move_data = move_data_from_dex(battle.dex)
    extractor = FeatureExtractor(battle.dex, move_data)
    assert isinstance(build_examples(decisions, extractor, move_data), list)


def test_nothing_to_learn_from_yields_nothing(battle):
    _, extractor, move_data = _setup(battle)
    assert build_examples([], extractor, move_data) == []
