"""The little language a player types a turn into.

Designed around the constraint that actually binds: about forty seconds a turn,
while reading a screen. So the common edits are two tokens -- `char 55` for HP,
`gambit ko` for a knockout -- names resolve from fragments, and several edits
can share a line separated by semicolons.

Nothing here mutates. `apply` returns a new position, so a line that turns out
to be illegal leaves the position it came from untouched and the player retypes
one command rather than rebuilding the board.

The refusals are the useful part. A fragment matching two Pokemon is refused
rather than guessed at, an unknown weather word is refused rather than stored,
and every id this module can produce is checked by its tests against the tables
the scorer actually reads -- a weather the scorer has never heard of would be
accepted, displayed, and then ignored by everything that matters.
"""

from typing import Literal

from pydantic import BaseModel

from champions_ai.dex import Dex
from champions_ai.dex.reference import to_id
from champions_ai.position.names import (
    AmbiguousName,
    UnknownName,
    resolve_item,
    resolve_move,
    resolve_species,
)
from champions_ai.position.state import (
    STATUSES,
    THEM,
    US,
    OpenSheet,
    Position,
    SideName,
    Target,
)

Control = Literal["", "show", "help", "undo", "quit"]

# Weather and terrain as the engine ids them, reachable by what a person says.
# Every value is checked against the scorer's own tables in
# `tests/unit/position/test_commands.py`: an id nothing reacts to would be
# stored, printed back, and silently ignored by every calculation.
WEATHER = {
    "sun": "sunnyday", "sunny": "sunnyday", "sunnyday": "sunnyday", "harsh": "sunnyday",
    "rain": "raindance", "raindance": "raindance",
    "sand": "sandstorm", "sandstorm": "sandstorm",
    "snow": "snowscape", "snowscape": "snowscape", "hail": "snowscape",
}
TERRAIN = {
    "electric": "electricterrain", "electricterrain": "electricterrain",
    "grassy": "grassyterrain", "grass": "grassyterrain", "grassyterrain": "grassyterrain",
    "psychic": "psychicterrain", "psychicterrain": "psychicterrain",
    "misty": "mistyterrain", "mist": "mistyterrain", "mistyterrain": "mistyterrain",
}
CLEARED = {"none", "off", "clear", "gone", "no"}
SIDE_CONDITIONS = ("tailwind", "reflect", "lightscreen", "auroraveil", "safeguard", "mist")
# Default durations, so `tailwind them` is enough mid-game. Four turns of
# Tailwind and five of a screen are the format's own numbers; a player who
# knows better can say `tailwind them 2`.
DEFAULT_TURNS = {"tailwind": 4, "reflect": 5, "lightscreen": 5, "auroraveil": 5}
FIELD_CONDITIONS = {"trickroom": "trickroom", "room": "trickroom", "tr": "trickroom",
                    "gravity": "gravity"}
STATS = {"atk": "atk", "attack": "atk", "def": "def", "defense": "def", "defence": "def",
         "spa": "spa", "spatk": "spa", "spd": "spd", "spdef": "spd",
         "spe": "spe", "speed": "spe", "acc": "accuracy", "accuracy": "accuracy",
         "eva": "evasion", "evasion": "evasion"}
CLEAR_STATUS = {"ok", "healthy", "cured", "none", "clear"}
# Choice lock and Encore restrict a Pokemon to one move. Different rules,
# identical consequence for what may legally be submitted.
LOCKING = ("locked", "lock", "encore", "encored", "choiced")
RESTRICTING = (*LOCKING, "taunt", "disable", "disabled", "free", "unlocked", "released")
# Spending and setting PP. Ours only: nothing on screen reports theirs.
COUNTING = ("used", "use", "pp")

OURS = {"my", "our", "we", "us"}
THEIRS = {"their", "theirs", "them", "they", "opp", "opponent"}

HELP = """
  Editing a Pokemon -- name first, and a fragment is enough:

    char 55            HP, as the percentage the bar shows
    char ko            knocked out
    char +2 atk        a stat stage, set to what the arrows show
    char par           status: brn par psn tox slp frz, or ok to clear
    char saw earthquake      a move you watched it use
    char item sitrus / char item gone
    char ability intimidate

  Yours only -- what you may legally pick:

    char locked flare blitz  Choice-locked, or Encored, into one move
    char taunt               every status move off
    char disable protect     one move off
    char free                the lock ended, the Taunt wore off
    char used protect        one PP off -- Champions gives Protect only 8
    char pp protect 3        set what is left directly

    my char 55         say which side when both have one

  Open team sheets -- all six are public before game one at a tournament,
  so they can be typed in before it starts and apply as each one appears:

    sheet kingambit, black glasses, defiant, sucker punch, iron head, protect
                       species, item, ability, then its moves
    sheet gambit, none, defiant, sucker punch      holds nothing

  The field:

    they gambit charizard    who they have out (in slot order)
    we blaziken torkoal      who you have out
    weather sun        sun rain sand snow, or none
    terrain grassy     electric grassy psychic misty, or none
    room               trick room on; room none to clear
    tailwind them      also reflect lightscreen auroraveil; add turns to override
    mega us            record a Mega Evolution as spent
    turn 7             set it directly
    n                  next turn: Tailwind, screens and Trick Room tick down

  Several at once:  char 55; gambit ko; +1 atk blaziken

  Then:  enter to see the board and the recommendation, u to undo,
         ? for this, q to stop.
"""


class Outcome(BaseModel, frozen=True):
    """What a typed line did. `control` is for the loop above, not the model."""

    position: Position
    message: str = ""
    control: Control = ""


def _target(position: Position, dex: Dex, token: str, side: SideName | None) -> Target:
    """Find the Pokemon a fragment names, on one side or either.

    Searched among Pokemon that are actually in the game: our four, and the
    opposing ones that have been seen. A fragment matching one on each side is
    refused rather than resolved by preference -- mirror matchups happen, and
    silently editing the wrong Charizard is not recoverable by looking at it.
    """
    pools = {
        US: [mon.pokemon_set.species for mon in position.own.team],
        THEM: [mon.species for mon in position.their_seen],
    }

    found: list[Target] = []
    for name in (US, THEM):
        if side not in (None, name):
            continue
        try:
            species = resolve_species(dex, token, within=pools[name])
        except AmbiguousName:
            # Two of our own match. Falling through to the other side would
            # then edit the opponent's Pokemon instead, which is both wrong and
            # invisible -- so an ambiguity anywhere is reported, not routed
            # around.
            raise
        except UnknownName:
            if side == name:
                raise
            continue
        found.append(Target(side=name, index=[to_id(s) for s in pools[name]].index(species)))
    if not found:
        raise ValueError(
            f"no Pokemon in this battle matches {token!r}. For one of theirs that has "
            "not been out yet, put it on the field first: they <name> <name>."
        )
    if len(found) == 2:
        raise ValueError(
            f"both sides have a {token!r}. Say which: my {token} ... or their {token} ..."
        )
    return found[0]


def _stage(tokens: list[str]) -> tuple[str, int] | None:
    """`+2 atk` or `atk +2`, in either order. None if this is not a stage."""
    for signed, named in ((0, 1), (1, 0)):
        if len(tokens) != 2:
            return None
        value, stat = tokens[signed], tokens[named]
        if stat not in STATS:
            continue
        if value.lstrip("+-").isdigit() and (value[0] in "+-" or value.isdigit()):
            return STATS[stat], int(value)
    return None


def _is_status(dex: Dex, move_id: str) -> bool:
    """Whether a Taunt would stop this move. Asked of the dex, never guessed --
    a move miscategorised here is one silently left available or silently
    removed, and neither shows on screen."""
    try:
        return dex.get_move(move_id).category == "Status"
    except KeyError:
        return False


def _is_stalling(dex: Dex, move_id: str) -> bool:
    """Whether this move drives the engine's shared stall counter.

    Wider than "blocks damage": Endure shares the counter while letting the hit
    land, which is why the dex carries the flag instead of anyone listing the
    protection moves by hand.
    """
    try:
        return dex.get_move(move_id).stalling
    except (KeyError, AttributeError):
        return False


def _own_move(position: Position, dex: Dex, target: Target, text: str) -> str:
    """A move id, resolved against *this Pokemon's own four*.

    Narrowed on purpose. A Pokemon cannot be locked into a move it does not
    have, and resolving against the whole dex would accept one -- disabling
    nothing while reading on screen as though it had worked.
    """
    if target.side == THEM:
        raise ValueError("restrictions are only tracked for your side")
    known = position.own.team[target.index].selectable_moves
    return resolve_move(dex, text, within=known)


def _edit(position: Position, dex: Dex, target: Target, rest: list[str]) -> Outcome:
    """Everything that changes one Pokemon."""
    name = position.species_at(target)
    if not rest:
        raise ValueError(f"what about {name}? Try `55`, `ko`, `+2 atk`, `par`.")

    head = rest[0]

    if head.isdigit():
        return Outcome(position=position.with_hp(target, int(head)), message=f"{name} at {head}%")

    if head == "ko":
        return Outcome(position=position.with_fainted(target), message=f"{name} is down")

    stage = _stage(rest)
    if stage is not None:
        stat, value = stage
        return Outcome(
            position=position.with_boost(target, stat, value),
            message=f"{name} at {value:+d} {stat}",
        )

    if head in CLEAR_STATUS:
        return Outcome(position=position.with_status(target, None), message=f"{name} is clear")

    if head in STATUSES:
        return Outcome(position=position.with_status(target, head), message=f"{name} is {head}")

    if head == "saw":
        if len(rest) < 2:
            raise ValueError("saw what? `char saw heat wave`")
        move = resolve_move(dex, " ".join(rest[1:]))
        return Outcome(
            position=position.with_revealed_move(target, move, stalling=_is_stalling(dex, move)),
            message=f"{name} has {dex.get_move(move).name}",
        )

    if head == "item":
        if len(rest) < 2:
            raise ValueError("which item? `char item sitrus`, or `char item gone`")
        if rest[1] in CLEARED:
            return Outcome(
                position=position.with_their_item(target, None),
                message=f"{name} has used its item",
            )
        item = resolve_item(dex, " ".join(rest[1:]))
        return Outcome(
            position=position.with_their_item(target, item),
            message=f"{name} holds {dex.get_item(item).name}",
        )

    if head == "ability":
        if len(rest) < 2:
            raise ValueError("which ability? `char ability drought`")
        ability = to_id(" ".join(rest[1:]))
        return Outcome(
            position=position.with_their_ability(target, ability),
            message=f"{name} has {ability}",
        )

    if head in ("used", "use"):
        if target.side == THEM:
            # Checked here rather than in the shared helper: for the opponent
            # there is a right answer, and naming it is more use than a refusal.
            raise ValueError("for one of theirs, say `saw <move>` instead")
        if len(rest) < 2:
            raise ValueError("used what? `char used protect`")
        move = _own_move(position, dex, target, " ".join(rest[1:]))
        updated = position.move_used(target, move, stalling=_is_stalling(dex, move))
        left = updated.remaining_pp(target, move)
        tail = f", {left} left" if left is not None else ""
        return Outcome(
            position=updated,
            message=f"{name} used {dex.get_move(move).name}{tail}",
        )

    if head == "pp":
        if len(rest) < 3 or not rest[-1].isdigit():
            raise ValueError("how much PP? `char pp protect 3`")
        move = _own_move(position, dex, target, " ".join(rest[1:-1]))
        left = int(rest[-1])
        return Outcome(
            position=position.with_pp(target, move, left),
            message=f"{name} has {left} {dex.get_move(move).name} left",
        )

    if head in LOCKING:
        # Choice lock and Encore are different rules with the same consequence
        # for what may be picked: one move, and nothing else.
        if len(rest) < 2:
            raise ValueError(f"{head} into what? `char {head} flare blitz`")
        move = _own_move(position, dex, target, " ".join(rest[1:]))
        return Outcome(
            position=position.locked_into(target, move),
            message=f"{name} can only use {dex.get_move(move).name}",
        )

    if head == "taunt":
        moves = position.own.team[target.index].selectable_moves
        status = [m for m in moves if _is_status(dex, m)]
        if not status:
            raise ValueError(f"{name} has no status moves, so a Taunt changes nothing")
        return Outcome(
            position=position.restrict(target, status),
            message=f"{name} is taunted: {len(status)} status move(s) off",
        )

    if head in ("disable", "disabled"):
        if len(rest) < 2:
            raise ValueError("disable what? `char disable protect`")
        move = _own_move(position, dex, target, " ".join(rest[1:]))
        already = position.own.team[target.index].disabled_moves
        return Outcome(
            position=position.restrict(target, already | {move}),
            message=f"{name} cannot use {dex.get_move(move).name}",
        )

    if head in ("free", "unlocked", "released"):
        return Outcome(
            position=position.unrestricted(target),
            message=f"{name} can use everything again",
        )

    raise ValueError(f"did not understand {' '.join(rest)!r} for {name}. ? for the list.")


def _lead(position: Position, dex: Dex, side: SideName, names: list[str]) -> Outcome:
    """Who is on the field, in slot order."""
    slots = position.regulation.active_slots_per_side
    if not names or len(names) > slots:
        raise ValueError(f"name 1 to {slots} Pokemon, in slot order.")
    updated = position
    shown = []
    for slot, token in enumerate(names):
        if side == THEM:
            species = resolve_species(dex, token, within=position.their_team)
            updated = updated.with_them_out(slot, species)
            shown.append(species)
        else:
            ours = [mon.pokemon_set.species for mon in position.own.team]
            species = resolve_species(dex, token, within=ours)
            index = [to_id(s) for s in ours].index(species)
            updated = updated.with_us_out(slot, index)
            shown.append(species)
    who = "They have" if side == THEM else "You have"
    return Outcome(position=updated, message=f"{who} {' and '.join(shown)} out")


def _side_from(token: str) -> SideName:
    if token in OURS:
        return US
    if token in THEIRS:
        return THEM
    raise ValueError(f"whose? say us or them, not {token!r}")


def _sheet(position: Position, dex: Dex, text: str) -> Outcome:
    """An opposing open team sheet: `sheet <species>, <item>, <ability>, <moves...>`.

    Comma separated because the names are not: "life orb" and "rough skin" are
    two words each, and a tournament sheet is typed once, before the clock
    starts. The species resolves against the six shown at Team Preview, so a
    fragment is enough and a Pokemon that is not in the game is refused.

    The ability is stored as an id without being checked against the dex, the
    same as `char ability` -- the dex dump carries no ability table to check
    against.
    """
    fields = [part.strip() for part in text.split(",")]
    if len(fields) < 2 or not fields[0]:
        raise ValueError(
            "which sheet? `sheet kingambit, black glasses, defiant, sucker punch`"
        )
    species = resolve_species(dex, fields[0], within=position.their_team or None)
    item_text = fields[1]
    ability_text = fields[2] if len(fields) > 2 else ""
    itemless = item_text in CLEARED
    sheet = OpenSheet(
        item=None if itemless or not item_text else resolve_item(dex, item_text),
        itemless=itemless,
        ability=to_id(ability_text) or None,
        moves=tuple(resolve_move(dex, part) for part in fields[3:] if part),
    )
    held = "nothing" if itemless else (dex.get_item(sheet.item).name if sheet.item else "?")
    return Outcome(
        position=position.with_their_sheet(species, sheet),
        message=f"{species}: {held}, {sheet.ability or '?'}, {len(sheet.moves)} moves",
    )


def apply(position: Position, dex: Dex, line: str) -> Outcome:
    """One command. Raises ValueError with something readable for a bad one."""
    tokens = line.strip().lower().split()
    if not tokens:
        return Outcome(position=position, control="show")

    head, rest = tokens[0], tokens[1:]

    if head in ("q", "quit", "exit"):
        return Outcome(position=position, control="quit")
    if head in ("?", "help", "h"):
        return Outcome(position=position, control="help")
    if head in ("u", "undo"):
        return Outcome(position=position, control="undo")
    if head in ("go", "board", "b"):
        return Outcome(position=position, control="show")

    if head in ("n", "next"):
        return Outcome(
            position=position.next_turn(),
            message=f"turn {position.turn + 1}, timers ticked",
        )

    if head == "turn":
        if not rest or not rest[0].isdigit():
            raise ValueError("which turn? `turn 7`")
        return Outcome(position=position.with_turn(int(rest[0])), message=f"turn {rest[0]}")

    if head == "sheet":
        return _sheet(position, dex, " ".join(rest))

    if head == "weather":
        if not rest:
            raise ValueError(f"which weather? {', '.join(sorted(set(WEATHER)))}, or none")
        if rest[0] in CLEARED:
            return Outcome(position=position.with_field(weather=None), message="weather cleared")
        if rest[0] not in WEATHER:
            raise ValueError(f"no weather called {rest[0]!r}: {', '.join(sorted(set(WEATHER)))}")
        value = WEATHER[rest[0]]
        return Outcome(position=position.with_field(weather=value), message=f"weather {value}")

    if head == "terrain":
        if not rest:
            raise ValueError(f"which terrain? {', '.join(sorted(set(TERRAIN)))}, or none")
        if rest[0] in CLEARED:
            return Outcome(position=position.with_field(terrain=None), message="terrain cleared")
        if rest[0] not in TERRAIN:
            raise ValueError(f"no terrain called {rest[0]!r}: {', '.join(sorted(set(TERRAIN)))}")
        value = TERRAIN[rest[0]]
        return Outcome(position=position.with_field(terrain=value), message=f"terrain {value}")

    if head in FIELD_CONDITIONS:
        condition = FIELD_CONDITIONS[head]
        conditions = dict(position.field_conditions)
        if rest and rest[0] in CLEARED:
            conditions.pop(condition, None)
            message = f"{condition} cleared"
        else:
            conditions[condition] = int(rest[0]) if rest and rest[0].isdigit() else 5
            message = f"{condition} up"
        return Outcome(
            position=position.model_copy(update={"field_conditions": conditions}),
            message=message,
        )

    if head in SIDE_CONDITIONS:
        if not rest:
            raise ValueError(f"{head} on whose side? `{head} them`")
        side = _side_from(rest[0])
        turns = int(rest[1]) if len(rest) > 1 and rest[1].isdigit() else DEFAULT_TURNS.get(head, 5)
        if len(rest) > 1 and rest[1] in CLEARED:
            turns = 0
        whose = "your" if side == US else "their"
        return Outcome(
            position=position.with_side_condition(side, head, turns),
            message=f"{head} {'off' if turns == 0 else f'up on {whose} side'}",
        )

    if head == "mega":
        if not rest:
            raise ValueError("whose Mega? `mega us` or `mega them`")
        side = _side_from(rest[0])
        return Outcome(
            position=position.with_mega_used(side),
            message=f"{'your' if side == US else 'their'} Mega is spent",
        )

    if head in OURS | THEIRS:
        side = _side_from(head)
        if not rest:
            raise ValueError(f"{head} what?")
        # `they gambit charizard` names who is out; `their char 55` edits one.
        # The difference is whether what follows the name is an edit.
        if len(rest) > 1 and (rest[1].isdigit() or rest[1] == "ko" or rest[1] in STATUSES
                              or rest[1] in ("saw", "item", "ability") or rest[1] in CLEAR_STATUS
                              or rest[1] in RESTRICTING
                              or rest[1] in COUNTING
                              or _stage(rest[1:]) is not None or rest[1] in STATS
                              or rest[1].lstrip("+-").isdigit()):
            return _edit(position, dex, _target(position, dex, rest[0], side), rest[1:])
        if len(rest) == 1 and head in ("my", "their", "our", "theirs"):
            raise ValueError(f"what about {rest[0]}? Try `{rest[0]} 55`, `ko`, `+2 atk`.")
        return _lead(position, dex, side, rest)

    # A leading stage, so `+1 atk blaziken` reads as naturally as the reverse.
    if len(tokens) == 3 and _stage(tokens[:2]) is not None:
        stat, value = _stage(tokens[:2])
        target = _target(position, dex, tokens[2], None)
        return Outcome(
            position=position.with_boost(target, stat, value),
            message=f"{position.species_at(target)} at {value:+d} {stat}",
        )

    return _edit(position, dex, _target(position, dex, head, None), rest)


def apply_all(position: Position, dex: Dex, line: str) -> Outcome:
    """A whole line, which may hold several commands separated by semicolons.

    A turn usually changes three or four things at once, and typing them as one
    line is the difference between keeping up with a game and not. Applied in
    order and stopped at the first refusal, so what the message reports is what
    actually took effect.
    """
    outcome = Outcome(position=position)
    messages: list[str] = []
    parts = [part for part in line.split(";") if part.strip()]
    if not parts:
        return apply(position, dex, line)
    for part in parts:
        outcome = apply(outcome.position, dex, part)
        if outcome.control:
            return outcome.model_copy(update={"message": ", ".join(messages)})
        if outcome.message:
            messages.append(outcome.message)
    return outcome.model_copy(update={"message": ", ".join(messages)})
