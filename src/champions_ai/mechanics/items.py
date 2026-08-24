"""What a held item does to a hit.

Champions carries a restricted item list -- 148 of them, with Choice Band,
Choice Specs, Assault Vest, Eviolite and the Arceus plates all absent -- so
this is a much smaller table than the full game would need. Forty-four of the
148 touch damage or Speed, and they fall into five families.

The multipliers cannot be dumped: they live in JavaScript callbacks on the
engine. They are transcribed here from `data/items.ts`, and a test checks
every id against the item table the bridge does dump, so a typo or a
regulation dropping an item fails loudly rather than silently doing nothing.

The engine works in 4096ths, which is why the constants look the way they do:
`[5324, 4096]` is Life Orb's 1.3, `[4915, 4096]` is 1.2, `[4505, 4096]` is 1.1.
Life Orb was measured independently at **1.304** across 144 real hits on
item-holding control teams, which is the check that this table is being read
at all rather than merely existing.
"""

from champions_ai.dex import ItemInfo, MoveInfo, SpeciesInfo

# Multiply the *final* damage, after type effectiveness and STAB.
LIFE_ORB = "lifeorb"
LIFE_ORB_MULTIPLIER = 1.3

# Expert Belt is the same shape but conditional: super-effective hits only.
EXPERT_BELT = "expertbelt"
EXPERT_BELT_MULTIPLIER = 1.2

# Multiply the *base power* of moves of one type. One item per type, extracted
# from the engine rather than typed out from memory.
TYPE_BOOST_MULTIPLIER = 1.2
TYPE_BOOST_ITEMS: dict[str, str] = {
    "blackbelt": "Fighting",
    "blackglasses": "Dark",
    "charcoal": "Fire",
    "dragonfang": "Dragon",
    "fairyfeather": "Fairy",
    "hardstone": "Rock",
    "magnet": "Electric",
    "metalcoat": "Steel",
    "miracleseed": "Grass",
    "mysticwater": "Water",
    "nevermeltice": "Ice",
    "poisonbarb": "Poison",
    "sharpbeak": "Flying",
    "silkscarf": "Normal",
    "silverpowder": "Bug",
    "softsand": "Ground",
    "spelltag": "Ghost",
    "twistedspoon": "Psychic",
}

# Multiply the base power of one whole category.
CATEGORY_BOOST_MULTIPLIER = 1.1
CATEGORY_BOOST_ITEMS: dict[str, str] = {
    "muscleband": "Physical",
    "wiseglasses": "Special",
}

# Halve an incoming super-effective hit of one type, then vanish. One per type
# again. Held by the *defender*, unlike everything above.
RESIST_BERRY_MULTIPLIER = 0.5
RESIST_BERRIES: dict[str, str] = {
    "babiriberry": "Steel",
    "chartiberry": "Rock",
    "chilanberry": "Normal",
    "chopleberry": "Fighting",
    "cobaberry": "Flying",
    "colburberry": "Dark",
    "habanberry": "Dragon",
    "kasibberry": "Ghost",
    "kebiaberry": "Poison",
    "occaberry": "Fire",
    "passhoberry": "Water",
    "payapaberry": "Psychic",
    "rindoberry": "Grass",
    "roseliberry": "Fairy",
    "shucaberry": "Ground",
    "tangaberry": "Bug",
    "wacanberry": "Electric",
    "yacheberry": "Ice",
}
# Chilan Berry is the odd one: it halves *any* Normal move, not only a
# super-effective one, because nothing is weak to Normal in the first place.
CHILAN_BERRY = "chilanberry"

# Doubles both attacking stats, and only for the species named in the engine's
# `itemUser`. Kept as a species check rather than a stat multiplier because it
# is the only one of its kind left in this dex.
LIGHT_BALL = "lightball"
LIGHT_BALL_MULTIPLIER = 2.0
LIGHT_BALL_USER = "Pikachu"

# Blocks item removal outright, so Knock Off gets no boost against it.
STICKY_HOLD = "stickyhold"


def is_removable(
    item: ItemInfo | None,
    holder: SpeciesInfo | None = None,
    ability: str | None = None,
    *,
    unknown_counts_as_held: bool = False,
) -> bool:
    """Whether this item can be taken off its holder.

    Knock Off's 1.5x is gated on this, not merely on holding something. The
    engine asks `singleEvent('TakeItem', ...)` before deciding, and returns no
    boost at all when the answer is no.

    Seventy-five items in this dex refuse, and every one of them is a Mega
    Stone -- which cannot be removed from *the species it evolves*, though it
    can be taken off anyone else. That matters here more than it would in most
    formats, because Champions teams are full of them.

    `unknown_counts_as_held` is for the agent, which cannot see an opponent's
    item until it fires. Passing None then means "not seen", not "not there",
    and almost every Pokemon in this format carries something -- so treating
    an unseen item as absent priced Knock Off at its floor against nearly
    every target. The differential harness, which knows both sides exactly,
    leaves this off.
    """
    if item is None:
        return unknown_counts_as_held
    if ability == STICKY_HOLD:
        return False
    if item.mega_stone is None:
        return True
    if holder is None:
        # Unknown holder: assume the stone is on the Pokemon it belongs to,
        # which is the overwhelmingly common case and the cautious guess.
        return False
    return item.mega_stone not in (holder.name, holder.base_species)


# Speed, for turn order rather than damage.
SPEED_MULTIPLIERS: dict[str, float] = {
    "choicescarf": 1.5,
    "ironball": 0.5,
}


def base_power_multiplier(item: str | None, move: MoveInfo) -> float:
    """What the attacker's item does to this move's base power."""
    if not item:
        return 1.0
    if TYPE_BOOST_ITEMS.get(item) == move.type:
        return TYPE_BOOST_MULTIPLIER
    if CATEGORY_BOOST_ITEMS.get(item) == move.category:
        return CATEGORY_BOOST_MULTIPLIER
    return 1.0


def attack_multiplier(item: str | None, attacker: SpeciesInfo | None) -> float:
    """What the attacker's item does to the attacking stat itself."""
    if item == LIGHT_BALL and attacker is not None:
        if attacker.name == LIGHT_BALL_USER or attacker.base_species == LIGHT_BALL_USER:
            return LIGHT_BALL_MULTIPLIER
    return 1.0


def damage_multiplier(item: str | None, *, effectiveness: float) -> float:
    """What the attacker's item does to the final damage."""
    if item == LIFE_ORB:
        return LIFE_ORB_MULTIPLIER
    if item == EXPERT_BELT and effectiveness > 1:
        return EXPERT_BELT_MULTIPLIER
    return 1.0


def defender_multiplier(
    item: str | None, move: MoveInfo, *, effectiveness: float
) -> float:
    """What the *defender's* item does to the damage it takes.

    A resist berry is consumed the moment it fires, so this is only right
    while the holder still has it -- which the tracker knows, because the
    engine announces `|-enditem|` and the item stops being reported.
    """
    resisted = RESIST_BERRIES.get(item or "")
    if resisted is None or resisted != move.type:
        return 1.0
    if item == CHILAN_BERRY or effectiveness > 1:
        return RESIST_BERRY_MULTIPLIER
    return 1.0


def speed_multiplier(item: str | None) -> float:
    """What a held item does to Speed, for turn order."""
    return SPEED_MULTIPLIERS.get(item or "", 1.0)
