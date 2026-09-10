"""Seed our own side from the engine, so its numbers are the engine's numbers.

We know our own team exactly -- we built it -- so nothing about our side needs
guessing. What it does need is a stat line, and that is the one place a
hand-built position could go quietly wrong: Champions' stat formula is not the
mainline one, natures truncate rather than round, and a Pokemon whose Speed is
a point out swaps turn order without ever looking wrong on screen.

So we do not compute it. We start a throwaway battle of the team against
itself, let the engine assemble our side, and take what it reports (ADR 0003:
read what the engine says rather than reimplementing it). That yields exact
stats with the nature already applied, real PP, the engine's move targets, and
its own verdict on which Pokemon may Mega Evolve.

The battle is then thrown away. It is a mirror match against a real opponent's
unknown team; nothing about it is the game being played, and the only thing
taken from it is our side's *starting* configuration.
"""

from champions_ai.data import BattleTeam
from champions_ai.dex import Dex
from champions_ai.domain import Boosts, Regulation, Side, TeamPreviewAction
from champions_ai.env import BattleEnv
from champions_ai.simulator import ShowdownBridge

# Fixed so setup is reproducible. Nothing random about the battle is used --
# only the side the engine assembles before anything happens.
SETUP_SEED = "sodium,00000000000000000000000000000000"


def _mega_capable(dex: Dex, mon) -> frozenset[str]:
    """Whether this Pokemon is holding the stone that Mega Evolves it.

    The engine reports this for the Pokemon it has on the field, but says
    nothing about the bench -- and a Pokemon on the bench is exactly the one
    whose Mega we need to know about when deciding whether to switch it in.
    So the bench is derived from the dex instead, using the same lookup the
    heuristic already uses.

    `tests/integration/test_position_setup.py` checks this derivation against
    the engine's own verdict for the Pokemon it does report on. That is where
    the two are held together; here we simply need an answer for all four.
    """
    held = mon.current_item or mon.pokemon_set.item
    if not held:
        return frozenset()
    try:
        species = dex.get_species(mon.pokemon_set.species)
        item = dex.get_item(held)
    except KeyError:
        return frozenset()
    # Asked item-first, not species-first. `Dex.mega_stone_for` answers "which
    # stone evolves this species" and returns the first match, which is fine
    # for its own callers -- they only ask whether one exists -- but wrong
    # here: Charizard has two stones, and a Charizard holding Charizardite Y
    # was told it could not Mega Evolve because X was found first.
    if item.mega_stone is None or item.mega_stone not in (species.name, species.base_species):
        return frozenset()
    return frozenset({"mega"})


def _mirror(
    bridge: ShowdownBridge,
    regulation: Regulation,
    team: BattleTeam,
    order: tuple[int, ...],
) -> Side:
    """One throwaway mirror battle, and the side the engine assembled for it."""
    env = BattleEnv(regulation, bridge=bridge)
    env.reset((team, team), seed=SETUP_SEED)
    action = TeamPreviewAction(picks=order)
    env.step({0: action, 1: action})
    return env.observation(0).own_side


def own_side(
    bridge: ShowdownBridge,
    regulation: Regulation,
    dex: Dex,
    team: BattleTeam,
    picks: tuple[int, ...],
) -> Side:
    """Our four, as the engine builds them, at the start of a battle.

    `picks` is in lead order: the first two start on the field, matching Team
    Preview everywhere else in this project.

    **Run once per pair of lead slots, not once.** A battle request describes
    moves, PP and targets only for the Pokemon actually on the field, so a
    single battle leaves half the team without them -- and half a team with
    engine data and half without is one position generating legal actions two
    different ways depending on who happened to lead. Rotating the leads and
    asking again costs one more battle start and gets the engine's own numbers
    for all four.
    """
    if len(picks) != regulation.picked_team_size:
        raise ValueError(
            f"{regulation.name} brings {regulation.picked_team_size}, got {len(picks)}"
        )

    slots = regulation.active_slots_per_side
    described: dict[int, object] = {}
    order = picks
    while len(described) < len(picks):
        side = _mirror(bridge, regulation, team, order)
        for slot, pick in enumerate(order[:slots]):
            described.setdefault(pick, side.team[slot])
        rotated = (*order[slots:], *order[:slots])
        if rotated == order:
            # Cannot reach the rest by rotating -- one lead slot, or a team
            # smaller than the rotation. Take what the last run gave for them
            # rather than looping.
            for slot, pick in enumerate(order):
                described.setdefault(pick, side.team[slot])
            break
        order = rotated

    # Everything that happened in the mirror battles is discarded. Abilities
    # fire on the way in -- an Intimidate in the team would leave our own lead
    # at -1 Attack, and Drought would have put the sun up -- and none of that
    # belongs to the position the player is actually in. What is kept is what
    # cannot be recomputed here: stats, max HP, PP and the engine's targets.
    cleaned = tuple(
        described[pick].model_copy(
            update={
                "current_hp": described[pick].max_hp,
                "status": None,
                "boosts": Boosts(),
                "volatile_conditions": frozenset(),
                "disabled_moves": frozenset(),
                "protect_streak": 0,
                "turns_on_field": 0,
                "last_move": None,
                "has_been_active": False,
                # From the team sheet, not from the mirror: an ability that
                # copied itself onto something (Trace, Imposter) copied it from
                # an opponent that does not exist.
                "current_ability": described[pick].pokemon_set.ability or None,
                "available_specials": _mega_capable(dex, described[pick]),
            }
        )
        for pick in picks
    )
    return Side(
        team=cleaned,
        active_slots=tuple(range(slots)),
        side_conditions={},
        mega_used=False,
    )
