"""A linear policy learned from human decisions.

Deliberately the smallest thing that could work: one weight per feature, a
softmax over the legal actions in a slot, and cross-entropy against the action
a rated human actually chose. No dependency beyond the standard library, which
keeps `pip install -e ".[dev]"` exactly as documented and matches the project's
"baselines before deep learning" rule.

It is a *conditional* softmax -- the candidate set differs from decision to
decision, so this ranks actions against each other within one slot rather than
classifying into fixed categories. That is the right shape for the problem and
it is also why a plain classifier would not fit.

Because `heuristic_score` is one of the features, the model can reproduce the
hand-written heuristic exactly by putting all its weight there. Any improvement
is therefore an improvement *over* the heuristic on identical information, which
is the question experiment 0005 left open.

**Do not wire `LinearPolicyAgent` in as the project's agent.** It beats
`HeuristicAgent` by 4.2 points of human agreement on held-out data and loses to
it 520-1080 over 1,600 battles, because it learned to decline a guaranteed
knockout one time in four -- humans decline apparent knockouts often enough, and
some of ours are not real, that imitation absorbed our own estimation error as a
policy bias. Kept as a reproducible research result, not as a player. See
docs/experiments/0006.
"""

import json
import math
import random
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from champions_ai.agents.base import Agent
from champions_ai.domain import JointAction, Observation, SlotAction
from champions_ai.ml.features import FEATURE_NAMES, FeatureExtractor


@dataclass
class TrainingExample:
    """One slot's decision: the candidates, and which one the human picked."""

    features: list[list[float]]
    chosen: int

    def __post_init__(self) -> None:
        if not 0 <= self.chosen < len(self.features):
            raise ValueError(
                f"chosen index {self.chosen} outside {len(self.features)} candidates"
            )


def softmax(scores: Sequence[float]) -> list[float]:
    """Numerically stable: subtracting the max stops exp() overflowing."""
    highest = max(scores)
    exponentials = [math.exp(s - highest) for s in scores]
    total = sum(exponentials)
    return [e / total for e in exponentials]


@dataclass
class LinearPolicy:
    """Scores an action as a weighted sum of its features."""

    weights: list[float] = field(default_factory=lambda: [0.0] * len(FEATURE_NAMES))
    feature_names: tuple[str, ...] = FEATURE_NAMES

    def score(self, features: Sequence[float]) -> float:
        return sum(w * f for w, f in zip(self.weights, features, strict=True))

    def probabilities(self, candidates: Sequence[Sequence[float]]) -> list[float]:
        return softmax([self.score(f) for f in candidates])

    def named_weights(self) -> dict[str, float]:
        return dict(zip(self.feature_names, self.weights, strict=True))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {"feature_names": list(self.feature_names), "weights": self.weights},
                indent=2,
            ),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> "LinearPolicy":
        """Rejects weights trained on a different feature set.

        Silently reusing them would apply each weight to the wrong input, which
        produces a plausible-looking model rather than an error.
        """
        payload = json.loads(path.read_text(encoding="utf-8"))
        names = tuple(payload["feature_names"])
        if names != FEATURE_NAMES:
            raise ValueError(
                "saved weights were trained on a different feature set; retrain"
            )
        return cls(weights=list(payload["weights"]), feature_names=names)


def train(
    examples: Sequence[TrainingExample],
    *,
    epochs: int = 40,
    learning_rate: float = 0.1,
    l2: float = 1e-4,
    seed: int = 0,
    on_epoch=None,
) -> LinearPolicy:
    """Fit by stochastic gradient descent on the cross-entropy loss.

    The gradient of a softmax cross-entropy is simply (probability − target)
    times the features, summed over candidates, which is why this needs no
    autodiff and no matrix library.
    """
    if not examples:
        raise ValueError("cannot train on an empty example set")
    # Sized from the data rather than from FEATURE_NAMES: the trainer should
    # work for any feature set, and assuming the production one turns a
    # mismatch into a confusing zip error deep inside scoring.
    width = len(examples[0].features[0])
    names = (
        FEATURE_NAMES
        if width == len(FEATURE_NAMES)
        else tuple(f"f{i}" for i in range(width))
    )
    policy = LinearPolicy(weights=[0.0] * width, feature_names=names)
    rng = random.Random(seed)
    order = list(range(len(examples)))

    for epoch in range(epochs):
        rng.shuffle(order)
        loss = 0.0
        for index in order:
            example = examples[index]
            probabilities = policy.probabilities(example.features)
            loss -= math.log(max(probabilities[example.chosen], 1e-12))

            for candidate, probability in enumerate(probabilities):
                error = probability - (1.0 if candidate == example.chosen else 0.0)
                if error == 0.0:
                    continue
                features = example.features[candidate]
                for j, value in enumerate(features):
                    if value:
                        policy.weights[j] -= learning_rate * error * value

        # Weight decay once per epoch rather than per step: cheaper, and at this
        # model size the difference is immaterial.
        if l2:
            for j in range(len(policy.weights)):
                policy.weights[j] *= 1.0 - l2
        if on_epoch is not None:
            on_epoch(epoch, loss / max(1, len(examples)))

    return policy


class LinearPolicyAgent(Agent):
    """Plays the highest-scoring legal action under a learned policy.

    Picks the joint action maximising the summed per-slot score, the same way
    `HeuristicAgent` does, so the two are comparable on more than their weights.
    """

    def __init__(
        self,
        policy: LinearPolicy,
        extractor: FeatureExtractor,
        *,
        name: str = "linear-policy",
    ) -> None:
        self.policy = policy
        self.extractor = extractor
        self.name = name

    def slot_score(self, observation: Observation, slot: int, action: SlotAction) -> float:
        return self.policy.score(self.extractor(observation, slot, action))

    def select_action(
        self, observation: Observation, legal_actions: Sequence[JointAction]
    ) -> JointAction:
        best, best_score = None, float("-inf")
        cache: dict[tuple[int, SlotAction], float] = {}
        for joint in legal_actions:
            total = 0.0
            for slot, action in enumerate(joint.slot_actions):
                key = (slot, action)
                if key not in cache:
                    cache[key] = self.slot_score(observation, slot, action)
                total += cache[key]
            if total > best_score:
                best, best_score = joint, total
        assert best is not None, "legal_actions must not be empty"
        return best
