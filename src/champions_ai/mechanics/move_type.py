"""Moves that decide their own type when they are used.

Four in this dex, and each reads the *wrong row of the type chart* until the
real type is worked out: Weather Ball becomes the weather's type, Terrain
Pulse the terrain's, Raging Bull depends on which Tauros is holding it, and
Aura Wheel on which Morpeko.

The type is not a cosmetic detail. It decides effectiveness, immunity and
whether STAB applies, so a Weather Ball in sun is a Fire move against a Grass
type -- super effective, from a move the chart would have called neutral.

Weather Ball also *doubles* its base power in any weather, which is a separate
hook and lives with the other base-power rules.

Transcribed from `onModifyType` in the engine's `data/moves.ts`, and guarded
by a test that every move the bridge flags has a rule here.
"""

from champions_ai.dex import MoveInfo, SpeciesInfo

WEATHER_BALL = "weatherball"
WEATHER_BALL_TYPES: dict[str, str] = {
    "sunnyday": "Fire",
    "desolateland": "Fire",
    "raindance": "Water",
    "primordialsea": "Water",
    "sandstorm": "Rock",
    "hail": "Ice",
    "snowscape": "Ice",
    "snow": "Ice",
}

TERRAIN_PULSE = "terrainpulse"
TERRAIN_PULSE_TYPES: dict[str, str] = {
    "electricterrain": "Electric",
    "grassyterrain": "Grass",
    "mistyterrain": "Fairy",
    "psychicterrain": "Psychic",
}

# Both of these key off which forme is holding the move, which is a fact about
# the user rather than the field.
RAGING_BULL = "ragingbull"
RAGING_BULL_TYPES: dict[str, str] = {
    "Tauros-Paldea-Combat": "Fighting",
    "Tauros-Paldea-Blaze": "Fire",
    "Tauros-Paldea-Aqua": "Water",
}

AURA_WHEEL = "aurawheel"
AURA_WHEEL_HANGRY = "Morpeko-Hangry"
AURA_WHEEL_HANGRY_TYPE = "Dark"
AURA_WHEEL_TYPE = "Electric"


def effective_type(
    move: MoveInfo,
    *,
    attacker: SpeciesInfo | None = None,
    weather: str | None = None,
    terrain: str | None = None,
) -> str:
    """The type this move will actually have when it lands.

    Safe to call for every move: anything without a rule returns its own type,
    so callers need not know which four are special.
    """
    if not move.modifies_type:
        return move.type

    if move.move_id == WEATHER_BALL:
        return WEATHER_BALL_TYPES.get(weather or "", move.type)

    if move.move_id == TERRAIN_PULSE:
        # The engine requires the user to be grounded, which we do not model:
        # a Flying-type or Levitate user keeps Normal and this will say
        # otherwise.
        return TERRAIN_PULSE_TYPES.get(terrain or "", move.type)

    if move.move_id == RAGING_BULL and attacker is not None:
        return RAGING_BULL_TYPES.get(attacker.name, move.type)

    if move.move_id == AURA_WHEEL and attacker is not None:
        return (
            AURA_WHEEL_HANGRY_TYPE
            if attacker.name == AURA_WHEEL_HANGRY
            else AURA_WHEEL_TYPE
        )

    return move.type
