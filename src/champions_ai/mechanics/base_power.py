"""Base power for moves the engine computes at run time.

Showdown gives 29 moves in the Champions dex a `basePowerCallback`. For eleven
of them the static `basePower` is **zero** -- Low Kick, Grass Knot, Gyro
Ball, Heavy Slam, Heat Crash, Electro Ball, Flail, Reversal, Beat Up, Hard Press
and Spit Up. Because `is_damaging` was `base_power > 0`, the heuristic classed
all eleven as *status moves* and scored them at a flat support value. Low Kick
and Grass Knot are ordinary VGC moves.

Found by following the engine differential harness, which reported Psyshock and
Knock Off as consistently under-predicted and led to the wider class.

Every formula here is transcribed from `basePowerCallback` in the engine's
`data/moves.ts`, and the thresholds are in **kilograms** while the engine works
in hectograms -- `getWeight()` returns `weighthg`, which is ten times the
kilogram figure our dex stores. Getting that factor wrong would misprice every
weight move by two whole brackets.
"""

from champions_ai.dex import MoveInfo, SpeciesInfo

# Low Kick and Grass Knot: heavier targets take more. Thresholds converted from
# the engine's hectograms to the kilograms our dex carries.
WEIGHT_BRACKETS_KG: tuple[tuple[float, int], ...] = (
    (200.0, 120),
    (100.0, 100),
    (50.0, 80),
    (25.0, 60),
    (10.0, 40),
)
WEIGHT_MINIMUM = 20

# Heavy Slam and Heat Crash: how many times heavier the user is than the target.
WEIGHT_RATIO_BRACKETS: tuple[tuple[float, int], ...] = (
    (5.0, 120),
    (4.0, 100),
    (3.0, 80),
    (2.0, 60),
)
WEIGHT_RATIO_MINIMUM = 40

# Flail and Reversal: the lower the user's HP the harder they hit. The engine
# works in forty-eighths of a bar.
HP_BRACKETS: tuple[tuple[int, int], ...] = (
    (2, 200),
    (5, 150),
    (10, 100),
    (17, 80),
    (33, 40),
)
HP_MINIMUM = 20

ELECTRO_BALL_BRACKETS = (40, 60, 80, 120, 150)
GYRO_BALL_CAP = 150

TARGET_WEIGHT_MOVES = frozenset({"lowkick", "grassknot"})
WEIGHT_RATIO_MOVES = frozenset({"heavyslam", "heatcrash"})
LOW_HP_MOVES = frozenset({"flail", "reversal"})

# Computed by the engine from state we do not model -- how many teammates are
# left, how many Stockpiles are banked. A middling value keeps them scored as
# the attacks they are rather than as support moves, which is the failure this
# module exists to fix.
UNMODELLED_DEFAULT = 60
UNMODELLED_MOVES = frozenset({"beatup", "spitup", "hardpress"})

# --- families whose static base power is a floor the engine scales up ---

# Hex and Infernal Parade double against a target with any status. Both are
# ordinary picks, and both were being scored at half strength against exactly
# the targets they are chosen for.
STATUS_DOUBLED_MOVES = frozenset({"hex", "infernalparade"})

# Stored Power and Power Trip add 20 per *positive* stage the user holds,
# summed across every stat. A Calm Mind user at +2/+2 swings 20 -> 100.
POSITIVE_BOOST_MOVES = frozenset({"storedpower", "powertrip"})
BOOST_POWER_STEP = 20

# Eruption and Water Spout scale straight down with the user's remaining HP,
# so a weakened Torkoal is not the 150-power threat the static value implies.
HP_SCALED_MOVES = frozenset({"eruption", "waterspout"})

# Last Respects adds 50 for every teammate already fainted -- late in a battle
# it is one of the strongest moves in the format.
LAST_RESPECTS_STEP = 50

ELECTRIC_TERRAIN = "electricterrain"

# Weather Ball doubles in any weather, on top of changing its type. A separate
# engine hook (`onModifyMove`) from the type change, so a separate rule here.
WEATHER_BALL = "weatherball"
WEATHER_BALL_MULTIPLIER = 2.0

# --- a second family: moves the engine scales through `onBasePower` rather
# --- than `basePowerCallback`. Seventeen of them here, and the flag the bridge
# --- dumps does not catch any: Knock Off has no `basePowerCallback` at all.
# --- It was the largest single term left in the damage residual once items
# --- were modelled, at a steady 1.5x across 27 hits.

# Knock Off hits 50% harder when there is an item it can actually take.
# Not merely when one is held: a Mega Stone on its own user cannot be
# removed, and this dex is full of them.
KNOCK_OFF = "knockoff"
KNOCK_OFF_MULTIPLIER = 1.5

# Facade doubles off *any* status but sleep -- burn included, which is the
# point of it: the burn halves the damage and Facade more than pays it back.
FACADE = "facade"
FACADE_MULTIPLIER = 2.0
FACADE_EXCLUDED_STATUS = "slp"

# Venoshock and Barb Barrage double into a poisoned target.
POISON_DOUBLED_MOVES = frozenset({"venoshock", "barbbarrage"})
POISON_STATUSES = frozenset({"psn", "tox"})
POISON_DOUBLED_MULTIPLIER = 2.0

# The solar moves are halved by any weather that is not sun.
SOLAR_MOVES = frozenset({"solarbeam", "solarblade"})
SOLAR_WEAKENING_WEATHER = frozenset(
    {"raindance", "primordialsea", "sandstorm", "hail", "snowscape", "snow"}
)
SOLAR_WEAKENED_MULTIPLIER = 0.5

# A terrain raises moves of its own type by 1.3 -- the engine's [5325, 4096].
# Only for a grounded user, which we do not model: a Flying-type or Levitate
# user gets the bonus here and should not.
TERRAIN_BOOSTED_TYPES: dict[str, str] = {
    "electricterrain": "Electric",
    "grassyterrain": "Grass",
    "psychicterrain": "Psychic",
}
TERRAIN_BOOST_MULTIPLIER = 1.3

# Two moves that key off a terrain rather than sharing its type.
TERRAIN_SPECIFIC_MOVES: dict[str, str] = {
    "expandingforce": "psychicterrain",
    "mistyexplosion": "mistyterrain",
}
TERRAIN_SPECIFIC_MULTIPLIER = 1.5

# Left alone on purpose, and each for a stated reason:
#   Fickle Beam  doubles 30% of the time, so it is a coin flip, not a fact
#   Lash Out     needs "were our stats lowered this turn"
#   Helping Hand needs an ally's action within the same turn
#   Charge       needs a volatile we do not track
#   Grav Apple   needs Gravity, which we record but do not thread through here
UNMODELLED_CONDITIONALS = frozenset(
    {"ficklebeam", "lashout", "helpinghand", "charge", "gravapple"}
)


def dynamic_base_power(
    move: MoveInfo,
    *,
    attacker: SpeciesInfo | None = None,
    defender: SpeciesInfo | None = None,
    attacker_hp_fraction: float = 1.0,
    attacker_speed: int | None = None,
    defender_speed: int | None = None,
    attacker_holds_item: bool | None = None,
    attacker_positive_boosts: int = 0,
    attacker_status: str | None = None,
    defender_status: str | None = None,
    defender_item_removable: bool = False,
    fainted_allies: int = 0,
    terrain: str | None = None,
    weather: str | None = None,
) -> int:
    """The base power this move would actually have, given the situation.

    Returns the move's static base power unless the engine computes it, so this
    is safe to call for every move rather than only the special ones.

    Originally this returned early for any move with a non-zero static power,
    which covered the eleven moves that carry none and silently skipped the
    eighteen that carry one *and* scale it. Those are the commoner half:
    Acrobatics doubles without an item, Hex doubles into a status, Stored Power
    reaches 100 off a single Calm Mind.

    A second family scales through `onBasePower` instead, which the dumped
    `dynamicPower` flag does not catch at all -- Knock Off has no
    `basePowerCallback`. Those multipliers are applied on top of whatever the
    first family works out.
    """
    value = _base_value(
        move,
        attacker=attacker,
        defender=defender,
        attacker_hp_fraction=attacker_hp_fraction,
        attacker_speed=attacker_speed,
        defender_speed=defender_speed,
        attacker_holds_item=attacker_holds_item,
        attacker_positive_boosts=attacker_positive_boosts,
        defender_status=defender_status,
        fainted_allies=fainted_allies,
        terrain=terrain,
    )
    return max(
        1,
        int(
            value
            * conditional_multiplier(
                move,
                attacker_status=attacker_status,
                defender_status=defender_status,
                defender_item_removable=defender_item_removable,
                terrain=terrain,
                weather=weather,
            )
        ),
    )


def conditional_multiplier(
    move: MoveInfo,
    *,
    attacker_status: str | None = None,
    defender_status: str | None = None,
    defender_item_removable: bool = False,
    terrain: str | None = None,
    weather: str | None = None,
) -> float:
    """What the situation multiplies this move's base power by.

    Separate from the value above because it is a different engine hook and a
    different question: not "what power does this move have" but "what is
    happening that changes it".
    """
    move_id = move.move_id
    multiplier = 1.0

    if move_id == KNOCK_OFF and defender_item_removable:
        multiplier *= KNOCK_OFF_MULTIPLIER
    if move_id == FACADE and attacker_status and attacker_status != FACADE_EXCLUDED_STATUS:
        multiplier *= FACADE_MULTIPLIER
    if move_id in POISON_DOUBLED_MOVES and defender_status in POISON_STATUSES:
        multiplier *= POISON_DOUBLED_MULTIPLIER
    if move_id in SOLAR_MOVES and weather in SOLAR_WEAKENING_WEATHER:
        multiplier *= SOLAR_WEAKENED_MULTIPLIER
    if TERRAIN_BOOSTED_TYPES.get(terrain or "") == move.type:
        multiplier *= TERRAIN_BOOST_MULTIPLIER
    # `terrain is not None` first: without it this is `None == None` for
    # every ordinary move on a bare field, and multiplies all of them.
    # Weather Ball doubles in any weather, on top of changing its type.
    if move_id == WEATHER_BALL and weather:
        multiplier *= WEATHER_BALL_MULTIPLIER
    if terrain is not None and TERRAIN_SPECIFIC_MOVES.get(move_id) == terrain:
        multiplier *= TERRAIN_SPECIFIC_MULTIPLIER

    return multiplier


def _base_value(
    move: MoveInfo,
    *,
    attacker: SpeciesInfo | None,
    defender: SpeciesInfo | None,
    attacker_hp_fraction: float,
    attacker_speed: int | None,
    defender_speed: int | None,
    attacker_holds_item: bool | None,
    attacker_positive_boosts: int,
    defender_status: str | None,
    fainted_allies: int,
    terrain: str | None,
) -> int:
    """The move's power before the situation scales it."""
    move_id = move.move_id
    static = move.base_power

    # --- static power the engine scales ---

    if move_id == "acrobatics":
        # Only doubles when the user holds nothing at all. `None` means we do
        # not know -- an opponent's item is hidden until it is used -- and most
        # Pokemon hold one, so the undoubled value is the right guess.
        return static * 2 if attacker_holds_item is False else static

    if move_id in STATUS_DOUBLED_MOVES:
        return static * 2 if defender_status else static

    if move_id in POSITIVE_BOOST_MOVES:
        return static + BOOST_POWER_STEP * max(0, attacker_positive_boosts)

    if move_id in HP_SCALED_MOVES:
        # The engine clamps base power to at least 1, so a Pokemon on its last
        # sliver still does something rather than nothing.
        return max(1, int(static * attacker_hp_fraction))

    if move_id == "lastrespects":
        return static + LAST_RESPECTS_STEP * max(0, fainted_allies)

    if move_id == "risingvoltage":
        return static * 2 if terrain == ELECTRIC_TERRAIN else static

    # --- moves that carry no static power at all ---

    if move_id in TARGET_WEIGHT_MOVES:
        if defender is None:
            return UNMODELLED_DEFAULT
        return _bracket(defender.weight_kg, WEIGHT_BRACKETS_KG, WEIGHT_MINIMUM)

    if move_id in WEIGHT_RATIO_MOVES:
        if attacker is None or defender is None or defender.weight_kg <= 0:
            return UNMODELLED_DEFAULT
        return _bracket(
            attacker.weight_kg / defender.weight_kg,
            WEIGHT_RATIO_BRACKETS,
            WEIGHT_RATIO_MINIMUM,
        )

    if move_id in LOW_HP_MOVES:
        # `max(..., 1)` mirrors the engine: a Pokemon on its last sliver still
        # lands in the top bracket rather than dividing to nothing.
        forty_eighths = max(int(attacker_hp_fraction * 48), 1)
        return _bracket_ascending(forty_eighths, HP_BRACKETS, HP_MINIMUM)

    if move_id == "gyroball":
        if not attacker_speed or defender_speed is None:
            return UNMODELLED_DEFAULT
        return min(GYRO_BALL_CAP, int(25 * defender_speed / attacker_speed) + 1)

    if move_id == "electroball":
        if not defender_speed or attacker_speed is None:
            return UNMODELLED_DEFAULT
        ratio = int(attacker_speed / defender_speed)
        return ELECTRO_BALL_BRACKETS[min(max(ratio, 0), 4)]

    if static > 0:
        # The rest are computed from state we do not track: Rage Fist counts
        # how often its user has been hit, Payback and Avalanche depend on the
        # turn order, Assurance on whether the target has already been damaged
        # this turn, Stomping Tantrum and Temper Flare on whether the last move
        # failed. The static value is the floor in every one of those, so this
        # under-predicts rather than inventing a number.
        return static

    # Anything else the engine computes from state we do not track.
    return UNMODELLED_DEFAULT


def _bracket(value: float, brackets: tuple[tuple[float, int], ...], floor: int) -> int:
    """Highest bracket whose threshold `value` reaches."""
    for threshold, power in brackets:
        if value >= threshold:
            return power
    return floor


def _bracket_ascending(
    value: int, brackets: tuple[tuple[int, int], ...], floor: int
) -> int:
    """Lowest bracket `value` falls under -- the HP families read the other way."""
    for threshold, power in brackets:
        if value < threshold:
            return power
    return floor
