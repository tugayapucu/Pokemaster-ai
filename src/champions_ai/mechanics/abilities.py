"""What an ability does to a hit.

Abilities are the largest single source of damage error left. Measured against
the engine on fully random teams the model reads **80.1%**, against 92.5% on
teams whose abilities are inert but whose items are on, and 96-99% on the
control. That twelve-point gap is this file.

The values were read off the residual before being written down, the same way
Life Orb was: run the harness, group by ability, take the median ratio.

    hugepower    1.950  (n=54)     engine says x2
    hustle       1.472  (n=45)     x1.5
    toughclaws   1.243  (n=22)     x1.3 on contact
    ironfist     1.158  (n=59)     x1.2 on punches, so not every move

Everything else came out inside +/-5% of 1.0 -- which is not the same as
"absent". The median only catches *unconditional* multipliers: a Multiscale
that halves damage one hit in five leaves the median alone. So the conditional
ones below are transcribed from the engine and trusted rather than measured,
and their test is the harness accuracy afterwards.
"""

from champions_ai.dex import MoveInfo

# --- unconditional multipliers on the attacking stat ---
ATTACK_MULTIPLIERS: dict[str, float] = {
    "hugepower": 2.0,
    "purepower": 2.0,
    "hustle": 1.5,
}
# ...and on the defending one.
DEFENCE_MULTIPLIERS: dict[str, float] = {
    "furcoat": 2.0,       # Defense only
}

# Raise their type by half once the holder is below a third of its health.
PINCH_ABILITIES: dict[str, str] = {
    "blaze": "Fire",
    "torrent": "Water",
    "overgrow": "Grass",
    "swarm": "Bug",
    "firemane": "Fire",
}
PINCH_FRACTION = 1 / 3
PINCH_MULTIPLIER = 1.5

# Raise the base power of moves carrying one flag. The engine works in
# 4096ths, so 1.2 is [4915, 4096] and 1.3 is [5325, 4096].
FLAG_ABILITIES: dict[str, tuple[str, float]] = {
    "ironfist": ("punch", 1.2),
    "toughclaws": ("contact", 1.3),
    "strongjaw": ("bite", 1.5),
    "megalauncher": ("pulse", 1.5),
    "sharpness": ("slicing", 1.5),
    "punkrock": ("sound", 1.3),
}

# Technician raises anything weak enough, whatever it is.
TECHNICIAN = "technician"
TECHNICIAN_THRESHOLD = 60
TECHNICIAN_MULTIPLIER = 1.5

# Sheer Force trades a move's rider for power: any move with a secondary is
# raised, and the secondary stops happening.
SHEER_FORCE = "sheerforce"
SHEER_FORCE_MULTIPLIER = 1.3

# Reckless raises the moves that hurt their user.
RECKLESS = "reckless"
RECKLESS_MULTIPLIER = 1.2

# Guts raises Attack while its holder is statused, and Marvel Scale Defence.
GUTS = "guts"
MARVEL_SCALE = "marvelscale"
STATUS_MULTIPLIER = 1.5

# Weather- and field-dependent.
SOLAR_POWER = "solarpower"
SUN = frozenset({"sunnyday", "desolateland"})
SAND_FORCE = "sandforce"
SANDSTORM = "sandstorm"
SAND_FORCE_TYPES = frozenset({"Rock", "Ground", "Steel"})
SAND_FORCE_MULTIPLIER = 1.3

# Adaptability turns same-type-attack-bonus from 1.5 into 2. Measured at
# 1.319 against an expected 2.0/1.5 = 1.333 -- and it was missed on the first
# pass because it hangs off `onModifySTAB` rather than any of the stat hooks,
# which is a reminder that a search for one hook shape finds only that shape.
ADAPTABILITY = "adaptability"
ADAPTABILITY_STAB = 2.0

# Abilities that rewrite a move's type and raise it slightly for the trouble.
# The engine exempts a handful of moves that decide their own type already.
ATE_ABILITIES: dict[str, str] = {
    "aerilate": "Flying",
    "pixilate": "Fairy",
    "refrigerate": "Ice",
    "dragonize": "Dragon",
    "galvanize": "Electric",
    "normalize": "Normal",
}
ATE_MULTIPLIER = 1.2
ATE_EXEMPT = frozenset({
    "judgment", "multiattack", "naturalgift", "revelationdance",
    "technoblast", "terrainpulse", "weatherball",
})

# Liquid Voice makes every sound move Water.
LIQUID_VOICE = "liquidvoice"


def rewritten_type(ability: str | None, move: MoveInfo) -> str | None:
    """The type this ability gives the move, or None if it leaves it alone."""
    if not ability or move.move_id in ATE_EXEMPT:
        return None
    if ability == LIQUID_VOICE and "sound" in move.flags:
        return "Water"
    replacement = ATE_ABILITIES.get(ability)
    if replacement and move.type == "Normal":
        return replacement
    return None


def stab_multiplier(ability: str | None, *, has_stab: bool) -> float:
    """What same-type-attack-bonus is worth to this Pokemon."""
    if not has_stab:
        return 1.0
    return ADAPTABILITY_STAB if ability == ADAPTABILITY else 1.5


# --- what the defender's ability does to what it takes ---
MULTISCALE = frozenset({"multiscale", "shadowshield"})
MULTISCALE_MULTIPLIER = 0.5

# Blunt a super-effective hit. All three are the same effect under three names.
SUPER_EFFECTIVE_DAMPENERS = frozenset({"filter", "solidrock", "prismarmor"})
DAMPENER_MULTIPLIER = 0.75

FLUFFY = "fluffy"
THICK_FAT = "thickfat"
HEATPROOF = "heatproof"
WATER_BUBBLE = "waterbubble"

# Types a Pokemon with one of these simply cannot be hit by.
ABSORBING_ABILITIES: dict[str, str] = {
    "flashfire": "Fire",
    "waterabsorb": "Water",
    "dryskin": "Water",
    "stormdrain": "Water",
    "voltabsorb": "Electric",
    "lightningrod": "Electric",
    "motordrive": "Electric",
    "sapsipper": "Grass",
    "eartheater": "Ground",
    "wellbakedbody": "Fire",
    "levitate": "Ground",
}
# ...and by whole classes of move.
FLAG_IMMUNITIES: dict[str, str] = {
    "bulletproof": "bullet",
    "soundproof": "sound",
    "windrider": "wind",
}


def attack_multiplier(
    ability: str | None,
    move: MoveInfo,
    *,
    hp_fraction: float = 1.0,
    status: str | None = None,
    weather: str | None = None,
) -> float:
    """What the attacker's ability does to its attacking stat."""
    if not ability:
        return 1.0
    multiplier = ATTACK_MULTIPLIERS.get(ability, 1.0)
    if PINCH_ABILITIES.get(ability) == move.type and hp_fraction <= PINCH_FRACTION:
        multiplier *= PINCH_MULTIPLIER
    if ability == GUTS and status and move.category == "Physical":
        multiplier *= STATUS_MULTIPLIER
    if ability == SOLAR_POWER and weather in SUN and move.category == "Special":
        multiplier *= STATUS_MULTIPLIER
    if ability == WATER_BUBBLE and move.type == "Water":
        multiplier *= 2.0
    return multiplier


def defence_multiplier(
    ability: str | None, move: MoveInfo, *, status: str | None = None
) -> float:
    """What the defender's ability does to its defending stat."""
    if not ability:
        return 1.0
    multiplier = 1.0
    if ability in DEFENCE_MULTIPLIERS and move.category == "Physical":
        multiplier *= DEFENCE_MULTIPLIERS[ability]
    if ability == MARVEL_SCALE and status and move.category == "Physical":
        multiplier *= STATUS_MULTIPLIER
    return multiplier


def base_power_multiplier(
    ability: str | None,
    move: MoveInfo,
    *,
    base_power: int,
    weather: str | None = None,
) -> float:
    """What the attacker's ability does to the move's base power."""
    if not ability:
        return 1.0
    flagged = FLAG_ABILITIES.get(ability)
    if flagged and flagged[0] in move.flags:
        return flagged[1]
    if ability == TECHNICIAN and base_power <= TECHNICIAN_THRESHOLD:
        return TECHNICIAN_MULTIPLIER
    if ability == SHEER_FORCE and move.secondaries:
        return SHEER_FORCE_MULTIPLIER
    if ability == RECKLESS and move.recoil:
        return RECKLESS_MULTIPLIER
    if (
        ability == SAND_FORCE
        and weather == SANDSTORM
        and move.type in SAND_FORCE_TYPES
    ):
        return SAND_FORCE_MULTIPLIER
    return 1.0


def taken_multiplier(
    ability: str | None,
    move: MoveInfo,
    *,
    effectiveness: float,
    at_full_hp: bool = False,
) -> float:
    """What the defender's ability does to the damage it takes.

    Zero means the hit does not land at all, which is a different statement
    from "not much" and is why immunities live here rather than in a separate
    check the callers have to remember.
    """
    if not ability:
        return 1.0
    if ABSORBING_ABILITIES.get(ability) == move.type:
        return 0.0
    if FLAG_IMMUNITIES.get(ability, "") in move.flags and ability in FLAG_IMMUNITIES:
        return 0.0

    multiplier = 1.0
    if ability in MULTISCALE and at_full_hp:
        multiplier *= MULTISCALE_MULTIPLIER
    if ability in SUPER_EFFECTIVE_DAMPENERS and effectiveness > 1:
        multiplier *= DAMPENER_MULTIPLIER
    if ability == FLUFFY:
        if move.type == "Fire":
            multiplier *= 2.0
        if "contact" in move.flags:
            multiplier *= 0.5
    if ability == THICK_FAT and move.type in ("Fire", "Ice"):
        multiplier *= 0.5
    if ability == HEATPROOF and move.type == "Fire":
        multiplier *= 0.5
    if ability == WATER_BUBBLE and move.type == "Fire":
        multiplier *= 0.5
    return multiplier
