"""Score a whole position, rather than a single action.

An action scorer answers "what does this move accomplish"; a position evaluator
answers "how good is the board". Search needs the latter, because the point of
looking ahead is to compare the *situations* different actions lead to.

Deliberately simple and hand-written. Milestone 7 replaces this with a learned
win-probability model; until then it is a baseline, and having it separate
means swapping it does not touch the search that consumes it.
"""

from dataclasses import dataclass

from champions_ai.domain import Observation

# A Pokemon still standing is worth much more than the HP it happens to have:
# fainting loses a slot, an attacker, and a switch option at once.
POKEMON_WEIGHT = 100.0
HP_WEIGHT = 40.0
# An empty slot cannot act at all, which is worse than merely being hurt.
EMPTY_SLOT_PENALTY = 25.0


@dataclass(frozen=True)
class PositionValue:
    """A position's value from one player's point of view, and its parts."""

    own_score: float
    opponent_score: float

    @property
    def advantage(self) -> float:
        """Positive means winning. Zero is an even board, not a 50% win rate."""
        return self.own_score - self.opponent_score


def evaluate_position(observation: Observation) -> PositionValue:
    """Score the board from the observing player's perspective.

    Uses only what the player can see: exact HP for their own side, and the
    percentages and fainted flags visible for the opponent's.
    """
    own = 0.0
    for index, mon in enumerate(observation.own_side.team):
        if mon.fainted:
            continue
        own += POKEMON_WEIGHT + HP_WEIGHT * mon.hp_fraction
        if index in observation.own_side.active_slots and mon.hp_fraction < 0.25:
            # A weakened Pokemon on the field is a liability, not just a number.
            own -= HP_WEIGHT * 0.25
    own -= EMPTY_SLOT_PENALTY * sum(
        1 for slot in observation.own_side.active_slots if slot is None
    )

    opponent_side = observation.opponent_side
    opponent = 0.0
    for observed in opponent_side.revealed:
        if observed.fainted:
            continue
        opponent += POKEMON_WEIGHT + HP_WEIGHT * (observed.hp_percent / 100)
    # Pokemon they have not sent out are still alive and still count, even
    # though nothing is known about them beyond their existence.
    opponent += POKEMON_WEIGHT * opponent_side.unrevealed_count
    opponent -= EMPTY_SLOT_PENALTY * sum(
        1 for slot in opponent_side.active_slots if slot is None
    )

    return PositionValue(own_score=own, opponent_score=opponent)
