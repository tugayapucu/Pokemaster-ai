"""Charge moves: a turn of nothing, then the hit -- unless something skips it.

Ten moves in this dex carry the engine's `charge` flag, and `MoveInfo.flags`
has carried it since the dex loader was written. Nothing read it, so the agent
priced Solar Beam and Electro Shot as a full hit on the turn they were chosen.
In the harvested Reg M-C pool those two are on 6.8% and 11.1% of teams.

Transcribed from `data/moves.ts` and `data/items.ts` at the pinned build:

    solarbeam, solarblade -- onTryMove:
        if (attacker.removeVolatile(move.id)) return;        // the second turn
        if (['sunnyday', 'desolateland'].includes(attacker.effectiveWeather(...)))
            return;                                          // no charge in sun
        if (!this.runEvent('ChargeMove', attacker, defender, move)) return;
        attacker.addVolatile('twoturnmove', defender);
        return null;                                         // charges

    electroshot -- the same shape, skipped in 'raindance' / 'primordialsea'
    meteorbeam, skyattack, fly, dig, dive, bounce, phantomforce -- never skipped

    powerherb -- onChargeMove: if (pokemon.useItem()) return false;  // skips it

`Pokemon.effectiveWeather()` then adds two rules about the *holder*: Mega Sol
reads as sun for every move except Electro Shot, and Utility Umbrella hides sun
and rain from whoever holds it. Mega Sol is checked first, so it wins.

What is **not** modelled: Fly, Dig, Dive, Bounce and Phantom Force also make
their user semi-invulnerable on the charge turn. That is a defensive benefit a
judgement would have to price, and together they are on under 1% of pool teams.
"""

from champions_ai.dex import MoveInfo
from champions_ai.mechanics.abilities import MEGA_SOL, MEGA_SOL_WEATHER, SUN

CHARGE_FLAG = "charge"
POWER_HERB = "powerherb"
UTILITY_UMBRELLA = "utilityumbrella"
ELECTRO_SHOT = "electroshot"

RAIN = frozenset({"raindance", "primordialsea"})
UMBRELLA_HIDES = frozenset({"sunnyday", "raindance", "desolateland", "primordialsea"})

# The weathers in which the engine skips a move's charge turn.
CHARGE_SKIPPED_IN: dict[str, frozenset[str]] = {
    "solarbeam": SUN,
    "solarblade": SUN,
    ELECTRO_SHOT: RAIN,
}

# What a hit is worth on the turn it starts charging, as a share of the hit.
#
# Derived rather than tuned. Choosing a charge move commits its user to two
# turns for one hit -- the engine locks the second turn in -- so per turn of
# commitment it delivers half of what a normal move would. This is the smallest
# honest statement of the mechanic, and it deliberately leaves out the second
# turn's own risks (a switch, a Protect, fainting first), which would all push
# the value lower and are judgements rather than facts.
CHARGE_TURN_MULTIPLIER = 0.5


def holder_weather(
    weather: str | None, *, move_id: str, ability: str | None, item: str | None
) -> str | None:
    """The weather a charge move's user sees, per `Pokemon.effectiveWeather()`."""
    if ability == MEGA_SOL and move_id != ELECTRO_SHOT:
        return MEGA_SOL_WEATHER
    if item == UTILITY_UMBRELLA and weather in UMBRELLA_HIDES:
        return None
    return weather


def charges_this_turn(
    move: MoveInfo,
    *,
    weather: str | None,
    ability: str | None = None,
    item: str | None = None,
    already_charging: bool = False,
) -> bool:
    """Whether choosing `move` now spends this turn charging instead of hitting.

    `already_charging` is the engine's second turn, which always fires. The
    caller knows it from the request: a Pokemon locked mid-charge is sent its
    one move with the target omitted.
    """
    if CHARGE_FLAG not in move.flags or already_charging:
        return False
    if item == POWER_HERB:
        return False
    skipped_in = CHARGE_SKIPPED_IN.get(move.move_id)
    if skipped_in is not None:
        seen = holder_weather(weather, move_id=move.move_id, ability=ability, item=item)
        if seen in skipped_in:
            return False
    return True
