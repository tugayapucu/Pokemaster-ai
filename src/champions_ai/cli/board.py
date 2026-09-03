"""Show a position the way a player reads one.

`Observation` is built for scoring, not for looking at: active slots are
indices into a team list, the opponent is a separate shape, and HP is a
fraction on one side and a percentage on the other. None of that is wrong --
it is the masking doing its job -- but it is unreadable at a glance, and a
recommendation nobody can check against the board is not advice.

Everything here reads from `Observation` alone, so the renderer is incapable
of showing a player something they are not entitled to see: the opponent's
bench is a count, not a list, because that is all `ObservedSide` carries.
"""

from champions_ai.domain import Observation

# Ordered so the printed line reads the way players say it: offence, then
# defence, then speed. `Boosts.stage` takes Showdown's ids.
BOOST_ORDER = ("atk", "def", "spa", "spd", "spe", "accuracy", "evasion")
BOOST_LABEL = {
    "atk": "Atk",
    "def": "Def",
    "spa": "SpA",
    "spd": "SpD",
    "spe": "Spe",
    "accuracy": "Acc",
    "evasion": "Eva",
}
SCREENS = ("reflect", "lightscreen", "auroraveil")


def _boosts(boosts) -> str:
    parts = [
        f"{stage:+d} {BOOST_LABEL[stat]}"
        for stat in BOOST_ORDER
        if (stage := boosts.stage(stat))
    ]
    return "  ".join(parts)


def _bar(fraction: float, width: int = 10) -> str:
    """A health bar. Rounds up, so anything still alive shows at least one block."""
    filled = 0 if fraction <= 0 else max(1, round(fraction * width))
    return "#" * filled + "." * (width - filled)


def _conditions(side_conditions: dict) -> str:
    """Tailwind, screens and hazards, named rather than dumped."""
    present = {str(name).lower() for name in side_conditions}
    shown = []
    if "tailwind" in present:
        shown.append("Tailwind")
    screens = [name for name in SCREENS if name in present]
    if screens:
        shown.append("Screens")
    for name in sorted(present - {"tailwind", *SCREENS}):
        shown.append(name.replace("spikes", " Spikes").strip().title())
    return ", ".join(shown)


def render_board(observation: Observation, *, width: int = 62) -> str:
    """The whole position as one block of text, opponent first.

    Opponent above and yours below, because that is the way every Pokemon
    client in existence lays it out and a player should not have to translate.
    """
    lines: list[str] = []

    field = []
    if observation.weather:
        field.append(observation.weather)
    if observation.terrain:
        field.append(observation.terrain)
    for name in observation.field_conditions:
        field.append(str(name).replace("trickroom", "Trick Room"))
    header = f"Turn {observation.turn}"
    if field:
        note = ", ".join(field)
        header = f"{header}{' ' * max(1, width - len(header) - len(note))}{note}"
    lines.append(header)
    lines.append("=" * width)

    opponent = observation.opponent_side
    label = "OPPONENT"
    conditions = _conditions(opponent.side_conditions)
    lines.append(f"{label}{'   ' + conditions if conditions else ''}")
    active = [index for index in opponent.active_slots if index is not None]
    for index, seen in enumerate(opponent.revealed):
        marker = ">" if index in active else " "
        if seen.fainted:
            lines.append(f" {marker} {seen.species:<18} fainted")
            continue
        fraction = seen.hp_percent / 100
        detail = [f"{_bar(fraction)} {seen.hp_percent:>3}%"]
        if seen.status:
            detail.append(seen.status.upper())
        boosts = _boosts(seen.boosts)
        if boosts:
            detail.append(boosts)
        if seen.revealed_item:
            detail.append(f"[{seen.revealed_item}]")
        lines.append(f" {marker} {seen.species:<18} {'  '.join(detail)}")
    if opponent.unrevealed_count:
        lines.append(f"   {'(' + str(opponent.unrevealed_count) + ' not yet seen)':<18}")

    lines.append("-" * width)

    own = observation.own_side
    conditions = _conditions(own.side_conditions)
    lines.append(f"YOU{'   ' + conditions if conditions else ''}")
    active = [index for index in own.active_slots if index is not None]
    for index, mon in enumerate(own.team):
        marker = ">" if index in active else " "
        species = mon.pokemon_set.species
        if mon.fainted:
            lines.append(f" {marker} {species:<18} fainted")
            continue
        detail = [f"{_bar(mon.hp_fraction)} {mon.current_hp:>3}/{mon.max_hp}"]
        if mon.status:
            detail.append(mon.status.upper())
        boosts = _boosts(mon.boosts)
        if boosts:
            detail.append(boosts)
        if mon.current_item:
            detail.append(f"[{mon.current_item}]")
        lines.append(f" {marker} {species:<18} {'  '.join(detail)}")

    return "\n".join(lines)


def render_moves(observation: Observation, dex, slot: int) -> str:
    """What the Pokemon in this slot can throw, with PP where the engine gave it."""
    index = observation.own_side.active_slots[slot]
    if index is None:
        return "  (nothing in this slot)"
    mon = observation.own_side.team[index]

    lines = []
    for position, move_id in enumerate(mon.selectable_moves):
        name = move_id
        extra = ""
        try:
            move = dex.get_move(move_id)
            name = move.name
            power = f"{move.base_power} BP" if move.base_power else "status"
            extra = f"  {move.type}, {power}"
        except KeyError:
            pass
        pp = ""
        if mon.move_pp is not None and position < len(mon.move_pp):
            pp = f"  {mon.move_pp[position]} pp"
        disabled = "  DISABLED" if move_id in mon.disabled_moves else ""
        lines.append(f"    {position + 1}. {name:<18}{extra}{pp}{disabled}")
    return "\n".join(lines) if lines else "  (no moves available)"
