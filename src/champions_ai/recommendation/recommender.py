"""Rank the actions available to a player, with reasons.

The other half of the project: the same machinery that picks the agent's move
should be able to *advise* rather than act, which means ranking every option
and saying why -- not just returning the argmax.

Confidence is presented as a share of a softmax over scores. That is a
statement about how clearly this action leads the alternatives, **not** a win
probability and not a calibrated belief; Milestone 7's value model is where a
real probability comes from. The distinction matters, because a number shown
to a human will be read as a probability unless it is clearly labelled
otherwise.
"""

import math
from dataclasses import dataclass, field

from champions_ai.agents import HeuristicAgent
from champions_ai.dex import Dex
from champions_ai.domain import JointAction, Observation
from champions_ai.recommendation.calibration import Cost, cost_of_gap
from champions_ai.recommendation.describe import describe_joint_action

# Softmax temperature over heuristic scores. Tuned against real positions: at
# 40 a decisive knockout looked like an 11% suggestion because the score gaps
# in this scoring scheme are tens of points, not hundreds. Low enough to be
# decisive, high enough that genuinely close calls still read as close.
DEFAULT_TEMPERATURE = 12.0


@dataclass(frozen=True)
class Recommendation:
    """One candidate action, ranked and explained."""

    rank: int
    action: JointAction
    description: str
    score: float
    confidence: float
    reasons: tuple[str, ...] = field(default=())
    # What choosing this instead of the top recommendation looks like to cost,
    # in win-rate points, from the rollout calibration in 0041. None where the
    # gap falls outside what was measured -- see `calibration`. The top choice
    # is the baseline and carries None by definition.
    cost: Cost | None = None

    def __str__(self) -> str:
        return f"{self.rank}. {self.description}  {self.confidence:.0%}"


@dataclass(frozen=True)
class RecommendationSet:
    """A ranked shortlist for one decision."""

    recommendations: tuple[Recommendation, ...]
    considered: int
    remainder_confidence: float = 0.0

    @property
    def best(self) -> Recommendation:
        return self.recommendations[0]

    @property
    def is_clear(self) -> bool:
        """Whether the top choice stands clearly apart from the runner-up.

        A close call is worth surfacing: it usually means the position is
        genuinely delicate rather than that the recommender is confused.

        **Measured rather than guessed.** This used to be a 0.15 gap in
        softmax share -- a threshold on a number whose own temperature nobody
        swept. It now asks whether the runner-up falls outside the band where
        rollouts find no difference at all (0041, 0042), which is the same
        question with an answer behind it. On the real evaluation pool that
        makes about 30% of positions clear, since 70% have the runner-up
        inside the close band.

        An unmeasured gap reads as *not* clear, which is the conservative way
        round: it surfaces the position rather than asserting a distinction
        nothing has established.
        """
        if len(self.recommendations) < 2:
            return True
        runner_up = self.recommendations[1]
        return runner_up.cost is not None and runner_up.cost.points > 1

    def render(self) -> str:
        lines = ["Recommended actions", ""]
        lines.extend(str(entry) for entry in self.recommendations)
        if self.remainder_confidence > 0.005:
            lines.append(f"{len(self.recommendations) + 1}. Other  {self.remainder_confidence:.0%}")
        return "\n".join(lines)

    def explain_best(self) -> str:
        best = self.best
        reasons = "; ".join(best.reasons) if best.reasons else "no specific reason recorded"
        return f"{best.description} -- {reasons}"


class Recommender:
    """Ranks legal actions for a human, using an agent's own scoring."""

    def __init__(
        self,
        dex: Dex,
        *,
        agent: HeuristicAgent | None = None,
        temperature: float = DEFAULT_TEMPERATURE,
        top_k: int = 4,
    ) -> None:
        self.dex = dex
        # Sharing the agent's scorer keeps advice and play consistent: what it
        # recommends is what it would do.
        self.agent = agent or HeuristicAgent(dex)
        self.temperature = temperature
        self.top_k = top_k

    def recommend(
        self, observation: Observation, legal_actions: list[JointAction]
    ) -> RecommendationSet:
        if not legal_actions:
            raise ValueError("cannot recommend from an empty action list")

        scored = [
            (action, self._score(observation, action)) for action in legal_actions
        ]
        # Ties are broken toward the simpler action. Where the scorer cannot
        # tell two options apart, recommending the one with fewer commitments
        # is the safer advice.
        scored.sort(key=lambda pair: (-pair[1][0], _complexity(pair[0])))
        scored = _drop_indistinguishable(scored)

        confidences = _softmax([score for _, (score, _) in scored], self.temperature)

        top_action, (top_score, _) = scored[0]
        shortlist = []
        for rank, ((action, (score, reasons)), confidence) in enumerate(
            zip(scored[: self.top_k], confidences[: self.top_k], strict=False), start=1
        ):
            differing = sum(
                1
                for mine, theirs in zip(
                    top_action.slot_actions, action.slot_actions, strict=False
                )
                if mine != theirs
            )
            shortlist.append(
                Recommendation(
                    rank=rank,
                    action=action,
                    description=describe_joint_action(observation, action, dex=self.dex),
                    score=score,
                    confidence=confidence,
                    reasons=reasons,
                    cost=(
                        None
                        if rank == 1
                        else cost_of_gap(top_score - score, slots_differing=differing)
                    ),
                )
            )

        return RecommendationSet(
            recommendations=tuple(shortlist),
            considered=len(legal_actions),
            remainder_confidence=sum(confidences[self.top_k :]),
        )

    def _score(
        self, observation: Observation, action: JointAction
    ) -> tuple[float, tuple[str, ...]]:
        total = 0.0
        reasons: list[str] = []
        for slot, slot_action in enumerate(action.slot_actions):
            scored = self.agent.score_slot_action(observation, slot, slot_action)
            total += scored.score
            reasons.extend(scored.reasons)
        return total, tuple(reasons)


def _complexity(action: JointAction) -> int:
    """How much a joint action commits to, for breaking ties toward the simpler option."""
    return sum(
        1
        for slot_action in action.slot_actions
        if getattr(slot_action, "special", None) is not None
    )


def _drop_indistinguishable(scored: list) -> list:
    """Collapse runs of actions the scorer rates identically.

    Mega Evolution is the case that motivates this: the heuristic does not
    model the stat change, so `X` and `X (+mega)` score the same and both
    occupy space in a shortlist while saying nothing different. Showing one is
    honest about the scorer's resolution; showing both implies a distinction it
    did not make.

    This hides a real modelling gap rather than fixing it -- see
    `PROJECT_PLAN.md`.
    """
    kept = []
    seen_scores: set[float] = set()
    for action, (score, reasons) in scored:
        rounded = round(score, 6)
        if rounded in seen_scores:
            continue
        seen_scores.add(rounded)
        kept.append((action, (score, reasons)))
    return kept


def _softmax(scores: list[float], temperature: float) -> list[float]:
    """Turn scores into shares. Shifted by the maximum so large scores cannot overflow."""
    if not scores:
        return []
    if temperature <= 0:
        raise ValueError(f"temperature must be positive, got {temperature}")
    highest = max(scores)
    weights = [math.exp((score - highest) / temperature) for score in scores]
    total = sum(weights)
    return [weight / total for weight in weights]
