"""Parse Showdown's export format into domain teams.

This is the format players actually copy out of the game's team builder, so it
is the natural way to bring a real team into the project.

Only the fields the domain models are read; anything else in a set (Shiny,
Happiness, IVs) is ignored rather than rejected, because a team pasted from
elsewhere should not fail to load over a line we do not use.
"""

import re

from champions_ai.domain import PokemonSet, StatSpread, Team

# Showdown's stat abbreviations -> StatSpread fields. "Stat Points" in
# Champions occupy the EV line of the export format (see ADR 0002).
STAT_KEYS = {
    "hp": "hp",
    "atk": "attack",
    "def": "defense",
    "spa": "special_attack",
    "spd": "special_defense",
    "spe": "speed",
}

_HEAD = re.compile(
    r"^(?P<lead>.+?)"
    r"(?:\s*\((?P<gender>[MF])\))?"
    r"(?:\s*@\s*(?P<item>.+))?$"
)
_NICKNAMED = re.compile(r"^(?P<nickname>.+?)\s*\((?P<species>[^()]+)\)$")


def _parse_stats(value: str) -> StatSpread:
    points: dict[str, int] = {}
    for part in value.split("/"):
        chunk = part.strip().split()
        if len(chunk) != 2:
            continue
        amount, key = chunk
        field = STAT_KEYS.get(key.lower())
        if field:
            points[field] = int(amount)
    return StatSpread(**points)


def parse_pokemon_set(block: str, *, default_level: int = 50) -> PokemonSet:
    lines = [line.strip() for line in block.strip().splitlines() if line.strip()]
    if not lines:
        raise ValueError("empty Pokemon block")

    head = _HEAD.match(lines[0])
    if head is None:
        raise ValueError(f"could not parse set header: {lines[0]!r}")

    lead = head.group("lead").strip()
    nicknamed = _NICKNAMED.match(lead)
    species = nicknamed.group("species").strip() if nicknamed else lead
    nickname = nicknamed.group("nickname").strip() if nicknamed else None

    fields: dict[str, object] = {
        "species": species,
        "nickname": nickname,
        "item": (head.group("item") or "").strip() or None,
        "level": default_level,
        "ability": "",
        "moves": [],
        "stats": StatSpread(),
        "nature": None,
        "tera_type": None,
    }

    for line in lines[1:]:
        if line.startswith("- "):
            fields["moves"].append(line[2:].strip())
        elif line.startswith("Ability:"):
            fields["ability"] = line.split(":", 1)[1].strip()
        elif line.startswith("Level:"):
            fields["level"] = int(line.split(":", 1)[1].strip())
        elif line.startswith("EVs:"):
            fields["stats"] = _parse_stats(line.split(":", 1)[1])
        elif line.startswith("Tera Type:"):
            fields["tera_type"] = line.split(":", 1)[1].strip()
        elif line.endswith("Nature"):
            fields["nature"] = line.rsplit(" ", 1)[0].strip()

    fields["moves"] = tuple(fields["moves"])
    return PokemonSet(**fields)


def parse_showdown_team(text: str, *, default_level: int = 50) -> Team:
    """Parse a whole team. Sets are separated by blank lines, as Showdown exports them."""
    blocks = [block for block in re.split(r"\n\s*\n", text.strip()) if block.strip()]
    if not blocks:
        raise ValueError("no Pokemon found in team text")
    return Team(
        pokemon=tuple(parse_pokemon_set(block, default_level=default_level) for block in blocks)
    )
