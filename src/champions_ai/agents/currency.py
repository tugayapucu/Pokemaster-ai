"""The units the agent scores in.

Every score in this project is a fraction of a health bar times a weight,
so that a status, a stat stage, a point of healing and a point of damage
all compete on one scale rather than on five separate ones.

They live here rather than in `heuristic` so that the support-move scorer
can price a Belly Drum with the same number a Swords Dance rider uses,
without the two modules importing each other.
"""

# Drain and recoil are priced in the same currency as damage dealt, because
# that is exactly what they are: HP moved between the two bars. Weighted a
# little below offence, since HP on our own bar is worth slightly less than HP
# removed from theirs -- taking a Pokemon out removes its actions too.
SUSTAIN_WEIGHT = 70.0

# What a status is worth, as a fraction of a health bar. These are judgements,
# not measurements, and they are ordered by how much of a Pokemon's
# contribution the status removes rather than by how much damage it deals:
# sleep takes turns away outright, paralysis halves Speed *and* skips turns,
# burn halves physical attack, poison is chip damage and little else.
STATUS_VALUE = {
    "slp": 0.60,
    "frz": 0.55,
    "par": 0.35,
    "brn": 0.30,
    "tox": 0.25,
    "psn": 0.15,
}
STATUS_WEIGHT = 100.0

# Types that cannot receive a given status at all. Ignoring this made Nuzzle
# look like a fine answer to an Electric-type and Will-O-Wisp to a Fire-type.
STATUS_IMMUNE_TYPES = {
    "par": {"Electric"},
    "brn": {"Fire"},
    "psn": {"Poison", "Steel"},
    "tox": {"Poison", "Steel"},
    "frz": {"Ice"},
}

# One stat stage, as a fraction of a health bar. Flat across stats on purpose:
# weighting them separately is a refinement, and an unjustified table of six
# numbers is harder to argue with than one.
STAT_STAGE_VALUE = 0.12
STAT_STAGE_WEIGHT = 100.0

# Stats whose loss only matters if something actually hits us afterwards. An
# offensive drop reduces our damage whatever happens; a defensive one is a bill
# that only arrives if we are still there to be hit. Charging Close Combat the
# full price for its own -1 Def/-1 SpD made the agent avoid one of the format's
# best attacks.
DEFENSIVE_STATS = frozenset({"def", "spd", "evasion"})


# Getting something nearly dead out of danger. A currency rather than a switch
# detail, because Parting Shot buys exactly the same thing and has to be able
# to say so in the same units.
SWITCH_WHEN_WEAKENED_BONUS = 55.0
LOW_HP_FRACTION = 0.35
