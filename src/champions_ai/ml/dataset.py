"""Turn reconstructed decisions into training examples.

The same exclusions the benchmark applies are applied here, and for the same
reason: a label the agent could not have produced teaches it nothing. In
particular a decision is dropped when the human's action is not among the legal
candidates, because a softmax needs a target inside its own candidate set --
training on a decision whose right answer is absent would push probability mass
away from every option indiscriminately.
"""

from collections.abc import Iterable, Mapping

from champions_ai.data.reconstruct import ReconstructedDecision
from champions_ai.domain.legal_actions import legal_slot_actions
from champions_ai.domain.move_data import MoveData
from champions_ai.evaluation.agreement import (
    action_signature,
    human_signature,
    target_unobservable,
)
from champions_ai.ml.features import FeatureExtractor
from champions_ai.ml.policy import TrainingExample


def build_examples(
    decisions: Iterable[ReconstructedDecision],
    extractor: FeatureExtractor,
    move_data: Mapping[str, MoveData],
    *,
    free_choices_only: bool = True,
) -> list[TrainingExample]:
    """One example per scorable slot decision."""
    examples: list[TrainingExample] = []

    for decision in decisions:
        observation = decision.observation
        for choice in decision.choices:
            if free_choices_only and not choice.is_free_choice:
                continue

            wanted = human_signature(choice, move_data)
            if wanted is None:
                continue
            hidden = target_unobservable(choice, move_data)
            if hidden:
                wanted = wanted[:2]

            try:
                actions = legal_slot_actions(observation, choice.slot, move_data)
            except KeyError:
                # A move the dex has never heard of; skip rather than abort a
                # whole training run over one stale entry.
                continue
            if len(actions) < 2:
                # Nothing was actually decided, so there is nothing to learn.
                continue

            signatures = [
                action_signature(a, observation, choice.slot, move_data) for a in actions
            ]
            if hidden:
                signatures = [None if s is None else s[:2] for s in signatures]
            if wanted not in signatures:
                continue

            examples.append(
                TrainingExample(
                    features=[
                        extractor(observation, choice.slot, action) for action in actions
                    ],
                    chosen=signatures.index(wanted),
                )
            )
    return examples
