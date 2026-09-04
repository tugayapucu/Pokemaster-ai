"""A policy that scores a whole turn, not two slots added together.

`LinearPolicyAgent` in `ml/` scores each slot and sums, which is the natural
shape for imitation -- 0006 compared against one human choice per slot. It is
the wrong shape here, and measurably so.

The heuristic's own `select_action` adds `_combined_targets` on top of the slot
scores: the focus-fire correction from 0011, which stops both slots piling
damage onto one target because a Pokemon can only faint once. That term is
joint by nature and cannot be expressed per slot.

Measured over 120 real decisions before this was written:

```
  argmax of summed slot scores       matches the heuristic    84.2%
  ...plus the combined-targets term  matches the heuristic   100.0%
```

So a per-slot policy disagrees with the heuristic on about one decision in six,
and that is worth roughly eight points: a warm-started per-slot policy plays
the heuristic to 42.3% over 2,100 battles (CI 37.9%-46.8%), which excludes
parity. Training from there would have to climb back to the bar before it could
clear it.

With the term as a feature, the warm start is an exact clone instead, and any
movement is movement over the shipped agent rather than a recovery.
"""

from collections.abc import Sequence

from champions_ai.agents.base import Agent
from champions_ai.agents.heuristic import HeuristicAgent, _combined_targets
from champions_ai.domain import JointAction, Observation
from champions_ai.ml.features import FEATURE_NAMES, HEURISTIC_SCALE, FeatureExtractor

# The per-slot features, plus the one term that only exists for a whole turn.
JOINT_FEATURE_NAMES: tuple[str, ...] = (*FEATURE_NAMES, "combined_targets")
COMBINED_INDEX = len(JOINT_FEATURE_NAMES) - 1
HEURISTIC_INDEX = JOINT_FEATURE_NAMES.index("heuristic_score")


def warm_start_weights(strength: float = 10.0) -> list[float]:
    """Weights that reproduce the heuristic's ranking exactly.

    Both terms carry the same weight because the heuristic adds them at the
    same scale: its joint score is `sum(slot scores) + combined_targets`, and
    both are divided by `HEURISTIC_SCALE` on the way into a feature. Any
    positive `strength` gives the same greedy policy -- argmax is scale
    invariant -- so it sets exploration during training and nothing else.
    """
    weights = [0.0] * len(JOINT_FEATURE_NAMES)
    weights[HEURISTIC_INDEX] = strength
    weights[COMBINED_INDEX] = strength
    return weights


class JointFeatures:
    """One vector per joint action, cached per slot within a decision."""

    def __init__(self, dex, move_data, heuristic: HeuristicAgent | None = None) -> None:
        self.extractor = FeatureExtractor(dex, move_data)
        self.heuristic = heuristic or HeuristicAgent(dex)

    def __call__(self, observation: Observation, joint: JointAction) -> list[float]:
        return self.batch(observation, [joint])[0]

    def batch(
        self, observation: Observation, joints: Sequence[JointAction]
    ) -> list[list[float]]:
        """Vectors for every candidate, with the per-slot work done once.

        Joint actions are a product of per-slot choices, so the same slot
        action appears in many of them -- about eight times each at a typical
        decision, where roughly ten distinct choices per slot combine into
        sixty-odd turns. Scoring it once per *turn* did that work eight times
        over, and the heuristic call inside is the expensive part.
        """
        cache: dict[tuple[int, object], tuple[list[float], object]] = {}
        vectors = []
        for joint in joints:
            total = [0.0] * len(JOINT_FEATURE_NAMES)
            scored = []
            for slot, action in enumerate(joint.slot_actions):
                key = (slot, action)
                if key not in cache:
                    cache[key] = (
                        list(self.extractor(observation, slot, action)),
                        self.heuristic.score_slot_action(observation, slot, action),
                    )
                features, slot_score = cache[key]
                for index, value in enumerate(features):
                    total[index] += value
                scored.append(slot_score)
            total[COMBINED_INDEX] = _combined_targets(scored) / HEURISTIC_SCALE
            vectors.append(total)
        return vectors


class JointPolicyAgent(Agent):
    """Greedy over the joint score. What the trained weights are judged as."""

    def __init__(self, weights: Sequence[float], features: JointFeatures, *, name: str) -> None:
        self.weights = list(weights)
        self.features = features
        self.name = name

    def select_action(
        self, observation: Observation, legal_actions: Sequence[JointAction]
    ) -> JointAction:
        best, best_score = None, float("-inf")
        for joint, vector in zip(
            legal_actions, self.features.batch(observation, legal_actions), strict=True
        ):
            score = sum(w * f for w, f in zip(self.weights, vector, strict=True))
            if score > best_score:
                best, best_score = joint, score
        assert best is not None, "legal_actions must not be empty"
        return best

    def select_team_preview(self, preview, picked_team_size):
        # Team preview is a different action space and is not what this is
        # learning; the heuristic makes it so the comparison is about turns.
        return self.features.heuristic.select_team_preview(preview, picked_team_size)
