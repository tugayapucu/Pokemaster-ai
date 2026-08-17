"""Recover what each player actually chose, from a replay log.

The label half of a human-agreement benchmark: for every decision point, what
did the player in front of it do?

Harder than reading `|move|` lines, because several things that *look* like
choices are not:

- a move used `[from]` another effect -- Sleep Talk, Copycat, Dancer -- was
  selected by the game, not the player;
- `|drag|` is a Pokemon forced out by Roar or Whirlwind, which its owner did
  not ask for;
- a switch replacing something that just fainted is a *replacement* decision,
  a different question from choosing to switch a healthy Pokemon out;
- `|cant|` means the player's choice never executed and is unrecoverable
  entirely.

Counting any of these as a freely chosen action trains a model on labels the
player never produced.
"""

import re
from dataclasses import dataclass
from typing import Literal

ChoiceKind = Literal["move", "switch"]

_TURN = re.compile(r"^\|turn\|(\d+)")


@dataclass(frozen=True)
class ObservedChoice:
    """One slot's action on one turn, as visible in the log."""

    turn: int
    player: int
    slot: int
    kind: ChoiceKind
    actor: str
    move: str | None = None
    target: str | None = None
    switched_to: str | None = None
    forced: bool = False
    lead: bool = False

    @property
    def is_free_choice(self) -> bool:
        """Whether this was a normal in-battle turn decision.

        Excludes two things that are decisions but different ones, and would
        distort any statistic that lumped them in:

        - **leads** appear as switches before turn 1, but they are the outcome
          of Team Preview -- counting them as mid-battle switches would inflate
          how often players appear to switch;
        - **forced replacements** are a choice of who comes in after a faint,
          not a choice to give up momentum.
        """
        return not self.forced and not self.lead


def _side_and_slot(ident: str) -> tuple[int, int]:
    """`p2b: Chomper` -> (player 1, slot 1)."""
    position = ident.split(":")[0].strip()
    player = int(position[1]) - 1
    slot = "abcdef".index(position[2]) if len(position) > 2 else 0
    return player, slot


def extract_choices(log: tuple[str, ...]) -> list[ObservedChoice]:
    """Every recoverable action, in order.

    Turns containing `|cant|` are dropped for the affected player: the log
    records that a Pokemon could not act and never the action its player
    chose.
    """
    choices: list[ObservedChoice] = []
    turn = 0
    fainted_slots: set[tuple[int, int]] = set()
    blocked: set[tuple[int, int]] = set()

    for line in log:
        turn_match = _TURN.match(line)
        if turn_match:
            turn = int(turn_match.group(1))
            fainted_slots.clear()
            continue

        parts = line.split("|")
        if len(parts) < 3:
            continue
        kind, args = parts[1], parts[2:]

        if kind == "faint":
            fainted_slots.add(_side_and_slot(args[0]))

        elif kind == "cant":
            blocked.add((turn, _side_and_slot(args[0])[0]))

        elif kind == "move":
            # `[from]` means another effect chose this move, not the player.
            if any(part.startswith("[from]") for part in args):
                continue
            player, slot = _side_and_slot(args[0])
            choices.append(
                ObservedChoice(
                    turn=turn,
                    player=player,
                    slot=slot,
                    kind="move",
                    actor=args[0].split(": ", 1)[-1],
                    move=args[1] if len(args) > 1 else None,
                    target=args[2] if len(args) > 2 and args[2].startswith("p") else None,
                )
            )

        elif kind == "switch":
            player, slot = _side_and_slot(args[0])
            choices.append(
                ObservedChoice(
                    turn=turn,
                    player=player,
                    slot=slot,
                    kind="switch",
                    actor=args[0].split(": ", 1)[-1],
                    switched_to=args[1].split(",")[0].strip() if len(args) > 1 else None,
                    # Replacing something that just fainted is a replacement,
                    # not a decision to give up momentum.
                    forced=(player, slot) in fainted_slots,
                    # Before turn 1 there is nothing to switch out of: these
                    # are the leads Team Preview produced.
                    lead=turn == 0,
                )
            )

        # `|drag|` is deliberately absent: Roar and Whirlwind move a Pokemon
        # its owner did not choose to move.

    return [choice for choice in choices if (choice.turn, choice.player) not in blocked]


def choices_by_decision(
    choices: list[ObservedChoice],
) -> dict[tuple[int, int], list[ObservedChoice]]:
    """Group into one entry per (turn, player) -- a doubles turn is a joint decision."""
    grouped: dict[tuple[int, int], list[ObservedChoice]] = {}
    for choice in choices:
        grouped.setdefault((choice.turn, choice.player), []).append(choice)
    return grouped
