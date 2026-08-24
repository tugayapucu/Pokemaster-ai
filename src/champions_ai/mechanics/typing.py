"""What types a Pokemon has *right now*, and whether it is standing on the ground.

Two questions that look separate and are the same one. A Pokemon's typing is
not fixed for the battle: Roost strips the Flying type for a turn, and being
Flying is most of what decides whether Ground moves and terrain reach you.

Found by measuring, not by reading the rules. A control run of the damage
harness read 90.0% instead of the usual 95%, and one mechanic explained every
large mismatch in it:

    Earthquake connecting with Altaria      Dragon/Flying -> Dragon, grounded
    Head Smash halved into Altaria          Rock vs Flying 2x -> vs Dragon 1x
    Body Press doubled into Corviknight     Fighting vs Flying/Steel 1x -> 2x

The swing between runs of that harness was never noise. It was whether the
randomly generated team happened to draw a Pokemon that Roosts.
"""

from collections.abc import Iterable

FLYING = "Flying"

# Roost removes the Flying type for the turn it is used. The tracker records
# it as a single-turn volatile, which expires at the turn boundary on its own.
ROOST = "roost"

# Abilities and items that keep a Pokemon off the ground regardless of type.
LEVITATE = "levitate"
AIR_BALLOON = "airballoon"

# ...and the ones that drag it back down. Iron Ball and Gravity override
# everything above, which is the point of them.
IRON_BALL = "ironball"
GRAVITY = "gravity"
GROUNDING_VOLATILES = frozenset({"smackdown", "ingrain"})


def effective_types(
    types: tuple[str, ...], volatiles: Iterable[str] = ()
) -> tuple[str, ...]:
    """The types this Pokemon actually has at this moment.

    Only Roost for now, which is the one that appears in this dex. Returning
    the original tuple untouched otherwise keeps this safe to call everywhere
    rather than only where something is known to be odd.
    """
    if ROOST not in set(volatiles):
        return types
    stripped = tuple(t for t in types if t != FLYING)
    # A pure Flying type that Roosts becomes Normal rather than typeless,
    # which is what the engine does.
    return stripped or ("Normal",)


def is_grounded(
    types: tuple[str, ...],
    *,
    ability: str | None = None,
    item: str | None = None,
    volatiles: Iterable[str] = (),
    field_conditions: Iterable[str] = (),
) -> bool:
    """Whether terrain, Ground moves and the hazards can reach this Pokemon.

    Pass `types` that have already been through `effective_types`, so a
    Roosting Flying type reads as grounded -- which is the whole reason the
    two live in the same module.
    """
    held = set(volatiles)
    if GRAVITY in set(field_conditions) or item == IRON_BALL or held & GROUNDING_VOLATILES:
        return True
    if FLYING in types or ability == LEVITATE or item == AIR_BALLOON:
        return False
    return True
