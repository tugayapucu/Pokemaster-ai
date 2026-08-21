"""Base power for moves the engine computes at run time.

Showdown gives 29 moves in the Champions dex a `basePowerCallback`, and for
eleven of them the static `basePower` is **zero** -- Low Kick, Grass Knot, Gyro
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


def dynamic_base_power(
    move: MoveInfo,
    *,
    attacker: SpeciesInfo | None = None,
    defender: SpeciesInfo | None = None,
    attacker_hp_fraction: float = 1.0,
    attacker_speed: int | None = None,
    defender_speed: int | None = None,
) -> int:
    """The base power this move would actually have, given the situation.

    Returns the move's static base power unless the engine computes it, so this
    is safe to call for every move rather than only the special ones.
    """
    if move.base_power > 0:
        return move.base_power

    move_id = move.move_id

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
