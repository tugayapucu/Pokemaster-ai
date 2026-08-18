"""How often does an agent choose what a rated human chose?

The first measurement in this project that is not agents grading each other.
Every win rate so far compares our code against our own code, so a shared blind
spot is invisible; a human replay is an outside opinion.

What it is not: proof of strength. Agreement rewards *imitating* the reference
player, so a genuinely better move counts as a miss, and a human error counts
as the right answer. It is a signal about whether the agent's reasoning is in
the same neighbourhood as a competent player's, and it should be read that way.

Three things have to be reported alongside any figure here, because each can
move it more than the agent does:

- **the random baseline.** Agreement of 40% is strong against a 15% baseline
  and terrible against 38%. Computed exactly, as the mean probability that a
  uniform pick from the same action set matches, rather than by sampling.
- **the action-set size.** Reconstructed movesets are partial (see
  `data/reconstruct.py`), so the agent chooses from fewer options than the
  human did. That inflates agreement, and the baseline moves with it.
- **what could not be scored.** When reconstruction cannot express the human's
  action at all, the comparison is undefined rather than wrong. Those are
  excluded from the rate and counted separately; a large count means the
  headline is not trustworthy.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from champions_ai.agents.base import Agent
from champions_ai.data.choices import ObservedChoice
from champions_ai.data.reconstruct import ReconstructedDecision
from champions_ai.domain import (
    MoveAction,
    Observation,
    PassAction,
    SlotAction,
    SwitchAction,
)
from champions_ai.domain.legal_actions import legal_joint_actions, legal_slot_actions
from champions_ai.domain.move_data import MoveData
from champions_ai.evaluation.runner import wilson_interval
from champions_ai.simulator.tracker import split_ident, to_id

# A comparable form of an action: what was done, and to what. Deliberately
# ignores `special`, because a reconstructed observation never offers Mega (the
# item that enables it is not published), so scoring it would turn every turn a
# human Mega Evolved into an automatic miss.
Signature = tuple


def _target_key(
    ident: str | None, player: int, move: MoveData | None
) -> tuple[str, int] | None:
    """A human's target ident as a side-relative slot, or None when unchosen.

    Returns None for any move that does not take a chosen target. Showdown
    prints a target on spread moves too -- `|move|p1a: X|Heat Wave|p2a: Y|
    [spread] p2a,p2b` -- but the player never picked it, so comparing it would
    make every spread move disagree.
    """
    if ident is None or move is None or not move.requires_target_choice:
        return None
    side, slot, _ = split_ident(ident)
    if slot is None:
        return None
    return ("ally" if side == f"p{player + 1}" else "foe", slot)


def human_signature(
    choice: ObservedChoice, move_data: Mapping[str, MoveData]
) -> Signature | None:
    """The human's action in comparable form, or None if it cannot be expressed."""
    if choice.kind == "move":
        if not choice.move:
            return None
        move_id = to_id(choice.move)
        return ("move", move_id, _target_key(choice.target, choice.player, move_data.get(move_id)))
    if choice.kind == "switch" and choice.switched_to:
        return ("switch", to_id(choice.switched_to))
    return None


def action_signature(
    action: SlotAction,
    observation: Observation,
    slot: int,
    move_data: Mapping[str, MoveData],
) -> Signature | None:
    """An agent's action in the same comparable form."""
    own = observation.own_side
    if isinstance(action, SwitchAction):
        return ("switch", to_id(own.team[action.team_index].pokemon_set.species))
    if isinstance(action, PassAction):
        return ("pass",)
    if not isinstance(action, MoveAction):
        return None

    team_index = own.active_slots[slot]
    if team_index is None:
        return None
    moves = own.team[team_index].selectable_moves
    if not 0 <= action.move_index < len(moves):
        return None
    move_id = moves[action.move_index]
    move = move_data.get(move_id)
    if action.target is None or move is None or not move.requires_target_choice:
        key = None
    else:
        key = (action.target.side, action.target.slot)
    return ("move", move_id, key)


@dataclass(frozen=True)
class SlotComparison:
    """One slot on one turn: what the human did, and what the agent did."""

    turn: int
    player: int
    slot: int
    human: Signature
    agent: Signature | None
    legal_count: int
    # Probability a uniform pick from the same action set would have matched.
    random_chance: float

    @property
    def agrees(self) -> bool:
        return self.agent == self.human

    @property
    def agrees_on_move(self) -> bool:
        """Same move or switch target, ignoring which slot it was aimed at.

        Reported separately because aiming is a much finer judgement than
        choosing, and a policy that picks the right move but the wrong target
        is failing differently from one that picks the wrong move.
        """
        return self.agent is not None and self.agent[:2] == self.human[:2]


@dataclass(frozen=True)
class AgreementResult:
    """Agreement over a set of reconstructed human decisions."""

    agent_name: str
    comparisons: tuple[SlotComparison, ...] = ()
    # Labels reconstruction could not express, or that no legal action matched.
    # Excluded from the rate because the comparison is undefined, not failed.
    unscorable: int = 0
    unscorable_examples: tuple[str, ...] = field(default=())

    @property
    def scored(self) -> int:
        return len(self.comparisons)

    @property
    def matches(self) -> int:
        return sum(1 for c in self.comparisons if c.agrees)

    @property
    def move_matches(self) -> int:
        return sum(1 for c in self.comparisons if c.agrees_on_move)

    @property
    def rate(self) -> float:
        return self.matches / self.scored if self.scored else 0.0

    @property
    def move_rate(self) -> float:
        return self.move_matches / self.scored if self.scored else 0.0

    @property
    def interval(self) -> tuple[float, float]:
        return wilson_interval(self.matches, self.scored)

    @property
    def random_baseline(self) -> float:
        """Exact expected agreement for a uniform random policy on the same sets."""
        if not self.comparisons:
            return 0.0
        return sum(c.random_chance for c in self.comparisons) / len(self.comparisons)

    @property
    def mean_actions(self) -> float:
        if not self.comparisons:
            return 0.0
        return sum(c.legal_count for c in self.comparisons) / len(self.comparisons)

    @property
    def beats_random(self) -> bool:
        """Whether the agreement interval clears the random baseline entirely.

        Conservative on purpose: a rate above the baseline whose interval still
        contains it is not evidence of anything.
        """
        return self.scored > 0 and self.interval[0] > self.random_baseline

    def summary(self) -> str:
        low, high = self.interval
        return (
            f"{self.agent_name}: {self.matches}/{self.scored} = {self.rate:.1%} "
            f"(95% CI {low:.1%}-{high:.1%}) "
            f"vs {self.random_baseline:.1%} random; "
            f"move-only {self.move_rate:.1%}; "
            f"{self.mean_actions:.1f} actions/slot; "
            f"{self.unscorable} unscorable"
        )


def measure_agreement(
    decisions: Iterable[ReconstructedDecision],
    agent: Agent,
    move_data: Mapping[str, MoveData],
    *,
    free_choices_only: bool = True,
) -> AgreementResult:
    """Score an agent against what humans actually did at each decision point.

    Only free choices count by default: a forced replacement after a faint and
    a Team Preview lead are real decisions, but different ones, and lumping
    them in measures a mixture of three policies (see `data/choices.py`).
    """
    comparisons: list[SlotComparison] = []
    unscorable = 0
    examples: list[str] = []

    for decision in decisions:
        observation = decision.observation
        scorable = [
            choice
            for choice in decision.choices
            if choice.is_free_choice or not free_choices_only
        ]
        if not scorable:
            continue

        try:
            joint = legal_joint_actions(observation, move_data)
        except KeyError as error:
            # A move the dex has never heard of, usually a stale cache. Fatal
            # for this decision but not for the run: a batch over thousands of
            # replays must not die on one, and the count below makes it visible
            # rather than silent.
            unscorable += len(scorable)
            if len(examples) < 10:
                examples.append(f"turn {decision.turn}: cannot enumerate actions ({error})")
            continue

        if not joint:
            continue
        chosen = agent.select_action(observation, joint)

        for choice in scorable:
            wanted = human_signature(choice, move_data)
            options = legal_slot_actions(observation, choice.slot, move_data)
            available = [
                action_signature(action, observation, choice.slot, move_data)
                for action in options
            ]
            if wanted is None or wanted not in available:
                unscorable += 1
                if len(examples) < 10:
                    examples.append(
                        f"turn {decision.turn} p{choice.player + 1} slot {choice.slot}: "
                        f"{choice.actor} {choice.move or choice.switched_to}"
                    )
                continue

            agent_action = (
                chosen.slot_actions[choice.slot]
                if choice.slot < len(chosen.slot_actions)
                else None
            )
            comparisons.append(
                SlotComparison(
                    turn=decision.turn,
                    player=choice.player,
                    slot=choice.slot,
                    human=wanted,
                    agent=(
                        action_signature(agent_action, observation, choice.slot, move_data)
                        if agent_action is not None
                        else None
                    ),
                    legal_count=len(options),
                    random_chance=available.count(wanted) / len(available),
                )
            )

    return AgreementResult(
        agent_name=agent.name,
        comparisons=tuple(comparisons),
        unscorable=unscorable,
        unscorable_examples=tuple(examples),
    )


def compare_agents(
    decisions: Sequence[ReconstructedDecision],
    agents: Sequence[Agent],
    move_data: Mapping[str, MoveData],
) -> list[AgreementResult]:
    """Score several agents on the same decisions, so the numbers are comparable."""
    return [measure_agreement(decisions, agent, move_data) for agent in agents]
