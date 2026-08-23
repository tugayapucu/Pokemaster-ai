"""Who acts first.

In a five-turn format this decides whether damage happens at all, and the
heuristic's own version of it carried a docstring admitting it was incomplete:
priority was consulted for *our* move and never for theirs, so a Fake Out into
a Fake Out read as guaranteed rather than as a coin flip.

Priority is not a modelling choice. It is a static field on every move, dumped
straight from the engine, and it runs from +5 (Helping Hand) to -7 (Trick
Room) in this dex. We had the number the whole time and only ever asked whether
it was greater than zero -- which also meant every *negative* priority move
read as an ordinary one, so Focus Punch and Dragon Tail were scored as though
they went first whenever their user was faster.

The rule is transcribed from `comparePriority` and `getActionSpeed` in the
engine: priority descending, then Speed descending, ties broken at random.
Trick Room reverses the Speed half by ordering on `10000 - speed`, which
leaves the priority half untouched -- a Fake Out still moves before an
Extreme Speed under Trick Room.
"""

from champions_ai.dex import MoveInfo
from champions_ai.mechanics.stats import apply_boost

# Field and side conditions that change the ordering rather than the stat.
TRICK_ROOM = "trickroom"
TAILWIND = "tailwind"

# Abilities that change a move's priority rather than its Speed. Prankster is
# the one that matters here: seven Pokemon in this dex have it, including
# Grimmsnarl, Whimsicott, Klefki and Sableye, and it made up seventy-four of
# the eighty-three orderings the harness got backwards before it was denied
# from the control team.
PRANKSTER = "prankster"
GALE_WINGS = "galewings"
STALL_ABILITY = "stall"

# Stall moves last inside its own bracket. The engine spells that as a
# fractional priority rather than a bracket change, so it loses to an ordinary
# move of the same priority and still beats anything a whole bracket below.
STALL_FRACTION = -0.1

TAILWIND_MULTIPLIER = 2
# Paralysis is halved in this generation, not quartered as it was before gen 7.
PARALYSIS_MULTIPLIER = 0.5
PARALYSIS = "par"


def effective_speed(
    speed: int,
    *,
    boost_stage: int = 0,
    tailwind: bool = False,
    paralysed: bool = False,
) -> int:
    """Speed as the engine actually orders on it.

    `speed` is the value the request reports, which has no stat stage applied
    to it -- the same gap that made our own Swords Dance raise nothing.

    Paralysis is applied last on purpose. The engine's own comment says so and
    sets `onModifySpePriority: -101` to guarantee it: it halves the total after
    Tailwind and the stages, not the raw stat.
    """
    value = apply_boost(speed, boost_stage)
    if tailwind:
        value *= TAILWIND_MULTIPLIER
    if paralysed:
        value = int(value * PARALYSIS_MULTIPLIER)
    return value


def move_priority(
    move: MoveInfo,
    ability: str | None = None,
    *,
    at_full_hp: bool = True,
) -> float:
    """A move's priority once the user's ability has had its say.

    Fractional because the engine's is: Stall shifts a move within its bracket
    rather than out of it.

    Quick Draw is deliberately absent. It is a 30% chance of +0.1 rather than
    a certainty, so folding it in here would report a coin flip as a fact --
    and only Slowbro-Galar carries it in this dex.
    """
    if ability == PRANKSTER and move.category == "Status":
        return move.priority + 1
    if ability == GALE_WINGS and move.type == "Flying" and at_full_hp:
        return move.priority + 1
    if ability == STALL_ABILITY:
        return move.priority + STALL_FRACTION
    return float(move.priority)


def moves_first(
    our_priority: float,
    our_speed: int,
    their_priority: float,
    their_speed: int,
    *,
    trick_room: bool = False,
) -> float:
    """Probability we act before them: 1.0, 0.5 on a tie, or 0.0.

    A speed tie really is a coin flip -- the engine gathers every action that
    compares equal and shuffles them -- so 0.5 is the honest answer rather
    than a hedge.
    """
    if our_priority != their_priority:
        return 1.0 if our_priority > their_priority else 0.0
    if our_speed == their_speed:
        return 0.5
    if trick_room:
        return 1.0 if our_speed < their_speed else 0.0
    return 1.0 if our_speed > their_speed else 0.0
