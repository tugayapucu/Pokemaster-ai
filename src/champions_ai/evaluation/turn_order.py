"""Check our turn-order rule against the engine, on inputs we fully control.

The same instrument as `differential.py` and for the same reason: the engine's
answer is readable directly, so a disagreement has exactly one possible cause.
Here it is even more direct than damage -- the order the engine resolved moves
in *is* the order the `|move|` lines appear in, so there is nothing to infer.

This tests the **rule**, not the prediction. The harness is omniscient and
knows what both sides picked, so it answers "given both moves, do we order
them the way the engine does". An agent choosing an action does not know the
opponent's move, and that uncertainty is a separate problem measured
separately -- conflating the two is what made the damage residual unreadable
for a whole session.

Samples come from the omniscient protocol stream, which is safe here and only
here: this is a referee measuring the game, not an agent playing it. Nothing
in this module may be used to build an `Observation`.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from champions_ai.dex import Dex
from champions_ai.domain import BattlePokemon
from champions_ai.mechanics import (
    PARALYSIS,
    TAILWIND,
    effective_speed,
    move_priority,
    moves_first,
)
from champions_ai.simulator.tracker import split_ident, to_id

# A `|move|` line carrying one of these was not the action its user chose:
# Metronome and Sleep Talk call another move, and the called move gets its own
# line. Ordering is decided by the *chosen* action, so these are skipped.
CALLED_MARKER = "[from]"


@dataclass(frozen=True)
class OrderSample:
    """Two Pokemon that both acted in one turn, and which went first."""

    first_ident: str
    first_move: str
    second_ident: str
    second_move: str
    first: BattlePokemon
    second: BattlePokemon
    trick_room: bool = False
    # Tailwind is per side, so each Pokemon carries its own.
    first_tailwind: bool = False
    second_tailwind: bool = False
    # Four abilities double Speed under their own weather, so the harness has
    # to know what is overhead -- it did not, which is why they could not be
    # measured before they were modelled.
    weather: str | None = None

    def predict(self, dex: Dex) -> float:
        """Our probability that the one who actually went first would.

        1.0 means we agreed, 0.0 means we had it backwards, and 0.5 means we
        called it a speed tie -- which the engine really does resolve at
        random, so it is neither right nor wrong.
        """
        return moves_first(
            move_priority(
                dex.get_move(self.first_move),
                self.first.current_ability,
                at_full_hp=self.first.hp_fraction >= 1.0,
            ),
            effective_speed(
                (self.first.computed_stats or {}).get("spe", 0),
                boost_stage=self.first.boosts.speed,
                tailwind=self.first_tailwind,
                paralysed=self.first.status == PARALYSIS,
                item=self.first.current_item,
                ability=self.first.current_ability,
                weather=self.weather,
                holds_item=self.first.current_item is not None,
            ),
            move_priority(
                dex.get_move(self.second_move),
                self.second.current_ability,
                at_full_hp=self.second.hp_fraction >= 1.0,
            ),
            effective_speed(
                (self.second.computed_stats or {}).get("spe", 0),
                boost_stage=self.second.boosts.speed,
                tailwind=self.second_tailwind,
                paralysed=self.second.status == PARALYSIS,
                item=self.second.current_item,
                ability=self.second.current_ability,
                weather=self.weather,
                holds_item=self.second.current_item is not None,
            ),
            trick_room=self.trick_room,
        )


@dataclass
class OrderReport:
    """How our ordering compared with the engine's."""

    pairs: int = 0
    correct: int = 0
    backwards: int = 0
    called_a_tie: int = 0
    mismatches: list[str] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        """Ties count as half, because the engine decides them by coin flip."""
        if not self.pairs:
            return 0.0
        return (self.correct + 0.5 * self.called_a_tie) / self.pairs

    def summary(self) -> str:
        return (
            f"{self.correct}/{self.pairs} ordered correctly "
            f"({self.accuracy:.1%} counting ties as half); "
            f"{self.backwards} backwards, {self.called_a_tie} called a tie"
        )


class OrderCollector:
    """Pairs up the Pokemon that acted in each turn, in the order they acted.

    Stateful for the same reason `DamageCollector` is: Trick Room and Tailwind
    are set by one chunk of protocol and matter in every chunk after it.
    """

    def __init__(self) -> None:
        self.trick_room = False
        self.tailwind: dict[str, bool] = {"p1": False, "p2": False}
        self.weather: str | None = None

    def feed(
        self,
        protocol: Sequence[str],
        active_lookup: Callable[[str], BattlePokemon | None],
    ) -> list[OrderSample]:
        acted: list[tuple[str, str]] = []
        samples: list[OrderSample] = []
        # The engine sorts every action once, at the start of the turn, so the
        # field state that decides the order is the state *before* any of these
        # lines ran. Reading it at the end got the last turn of a Trick Room
        # backwards every time: the moves were ordered under it, then it
        # expired in the residual phase before the `|turn|` line arrived.
        at_turn_start = self._field_state()

        for line in protocol:
            parts = line.split("|")
            if len(parts) < 3:
                continue
            tag, args = parts[1], parts[2:]

            if tag == "move":
                if any(part.startswith(CALLED_MARKER) for part in args):
                    continue
                acted.append((args[0], to_id(args[1])))
            elif tag == "-fieldstart" and to_id(args[0].split(":")[-1]) == "trickroom":
                self.trick_room = True
            elif tag == "-fieldend" and to_id(args[0].split(":")[-1]) == "trickroom":
                self.trick_room = False
            elif tag == "-weather":
                self.weather = None if args[0] == "none" else to_id(args[0])
            elif tag in ("-sidestart", "-sideend"):
                side = args[0].split(":")[0]
                if to_id(args[1].split(": ")[-1]) == TAILWIND and side in self.tailwind:
                    self.tailwind[side] = tag == "-sidestart"
            elif tag == "turn":
                samples.extend(self._pairs(acted, active_lookup, at_turn_start))
                acted = []
                at_turn_start = self._field_state()

        samples.extend(self._pairs(acted, active_lookup, at_turn_start))
        return samples

    def _field_state(self) -> tuple[bool, dict[str, bool], str | None]:
        return self.trick_room, dict(self.tailwind), self.weather

    def _pairs(self, acted, active_lookup, field_state) -> list[OrderSample]:
        """Every ordered pair from one turn's actions.

        Pairwise rather than a single ranking, because a Pokemon that fainted
        before its turn came never appears -- so the list is the actions that
        happened, not the actions that were chosen.
        """
        trick_room, tailwind, weather = field_state
        samples = []
        for position, (ident, move_id) in enumerate(acted):
            for later_ident, later_move in acted[position + 1 :]:
                if later_ident == ident:
                    continue  # the same Pokemon acting twice, not a race
                first, second = active_lookup(ident), active_lookup(later_ident)
                if first is None or second is None:
                    continue
                samples.append(
                    OrderSample(
                        first_ident=ident,
                        first_move=move_id,
                        second_ident=later_ident,
                        second_move=later_move,
                        first=first,
                        second=second,
                        trick_room=trick_room,
                        first_tailwind=tailwind.get(split_ident(ident)[0], False),
                        second_tailwind=tailwind.get(split_ident(later_ident)[0], False),
                        weather=weather,
                    )
                )
        return samples


def compare(samples: Sequence[OrderSample], dex: Dex) -> OrderReport:
    """Score our ordering against the order the engine actually resolved."""
    report = OrderReport()
    for sample in samples:
        try:
            predicted = sample.predict(dex)
        except KeyError:
            continue
        report.pairs += 1
        if predicted == 1.0:
            report.correct += 1
            continue
        if predicted == 0.5:
            report.called_a_tie += 1
            continue
        report.backwards += 1
        if len(report.mismatches) < 25:
            report.mismatches.append(
                f"{sample.first.pokemon_set.species} {sample.first_move} "
                f"went before {sample.second.pokemon_set.species} "
                f"{sample.second_move}, we said the reverse"
                + (" (trick room)" if sample.trick_room else "")
            )
    return report
