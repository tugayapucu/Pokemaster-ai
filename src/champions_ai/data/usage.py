"""What a species actually carries, from sources that see whole sets.

The team pool was built from what replays *reveal*. An item only enters a
replay when it announces itself -- a seed activating, a berry eaten -- so a
Life Orb or a White Herb that never announces is simply missing, and the
pool's items are the items that make noise. Measured against Smogon's usage
statistics for Reg M-B, where the server saw every team whole (1,269,250
battles at 1500+):

    Kingambit     usage: Chople Berry 37%, Black Glasses 27%  pool: Chople Berry 93%
    Sneasler      usage: White Herb 46%, Focus Sash 43%       pool: Grassy Seed 67%

Every pool Pokemon also carried an even 11 Stat Points in each stat and a
neutral nature; among the thirty most-used Reg M-B species, 0.2% of real spreads
look anything like even.

Two sources here, both of which see a set whole rather than what fired:

- **Smogon's chaos usage file** -- items, natures and Stat Point spreads. It
  covers the species legal in the regulation it was built for, and lists each
  Mega forme as its own entry, which is folded back into the species that holds
  the stone.
- **Open team sheets** (`|showteam|`) in our own replays -- items and natures,
  no Stat Points. Few, but true, and they cover species newer than the usage
  file: Baxcalibur holds its Mega Stone on 96% of sheets and on 2% of the old
  pool's sets.

Both are measurements of unpublished or third-party data and are kept out of
the repository; see `.gitignore`.
"""

import gzip
import json
import random
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from champions_ai.simulator.tracker import to_id

STAT_LABELS = ("HP", "Atk", "Def", "SpA", "SpD", "Spe")
DEFAULT_MIN_SHEETS = 20
# The key an itemless set is counted under; Smogon writes it as "nothing".
NO_ITEM = ""


@dataclass
class SetDistribution:
    """How often a species carries each item, nature and spread."""

    species: str
    source: str
    samples: float = 0.0
    items: Counter = field(default_factory=Counter)
    natures: Counter = field(default_factory=Counter)
    # (nature, (hp, atk, def, spa, spd, spe)) -> weight
    spreads: Counter = field(default_factory=Counter)


def _own_key(dex, name: str) -> str:
    try:
        return to_id(dex.get_species(name).name)
    except KeyError:
        return to_id(name)


def _stone_holders(dex) -> dict[str, str]:
    """Mega forme id -> id of the species that holds its stone.

    By the stone rather than by `base_species`: Floette's Mega evolves from
    Floette-Eternal, and a base-species lookup would file its usage under a
    species that cannot hold the stone at all.
    """
    return {
        to_id(item.mega_forme): to_id(item.mega_stone)
        for item in dex.items.values()
        if item.mega_forme and item.mega_stone
    }


def load_smogon_chaos(path: Path, dex) -> dict[str, SetDistribution]:
    """Species id -> distribution, from a Smogon chaos file (`.json` or `.json.gz`)."""
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)

    holders = _stone_holders(dex)
    out: dict[str, SetDistribution] = {}
    for name, entry in payload["data"].items():
        key = holders.get(to_id(name)) or _own_key(dex, name)
        dist = out.setdefault(key, SetDistribution(species=key, source="smogon"))
        dist.samples += entry.get("Raw count", 0)
        for item, weight in entry.get("Items", {}).items():
            dist.items[NO_ITEM if item == "nothing" else item] += weight
        for spread, weight in entry.get("Spreads", {}).items():
            nature, _, points = spread.partition(":")
            values = tuple(int(value) for value in points.split("/"))
            if len(values) != len(STAT_LABELS):
                continue
            dist.spreads[(nature, values)] += weight
            dist.natures[nature] += weight
    return out


def open_sheet_distributions(
    replays, dex, *, min_sets: int = DEFAULT_MIN_SHEETS
) -> dict[str, SetDistribution]:
    """Species id -> distribution, from `|showteam|` lines.

    The packed format is `name|species|item|ability|moves|nature|evs|...`, with
    the species field empty when it matches the name and the Stat Points left
    blank -- open sheets show everything but those. Species seen on fewer than
    `min_sets` sheets are dropped: a distribution from three sets is a guess.
    """
    raw: dict[str, SetDistribution] = {}
    for replay in replays:
        for line in replay.log:
            if not line.startswith("|showteam|"):
                continue
            parts = line.split("|", 3)
            if len(parts) < 4:
                continue
            for packed in parts[3].split("]"):
                fields = packed.split("|")
                if len(fields) < 6:
                    continue
                name, species, item, _ability, _moves, nature = fields[:6]
                key = _own_key(dex, species or name)
                dist = raw.setdefault(key, SetDistribution(species=key, source="open-sheets"))
                dist.samples += 1
                dist.items[to_id(item)] += 1
                if nature:
                    dist.natures[nature] += 1
    return {key: dist for key, dist in raw.items() if dist.samples >= min_sets}


def combine(*sources: dict[str, SetDistribution]) -> dict[str, SetDistribution]:
    """Earlier sources win per species; later ones only fill gaps."""
    out: dict[str, SetDistribution] = {}
    for source in sources:
        for key, dist in source.items():
            out.setdefault(key, dist)
    return out


def _weighted_choice(rng: random.Random, weights):
    # Sorted so the draw depends on the seed and never on dictionary order.
    population = sorted((key for key, weight in weights.items() if weight > 0), key=str)
    if not population:
        return None
    return rng.choices(population, weights=[weights[key] for key in population], k=1)[0]


def sample_item(
    dist: SetDistribution,
    rng: random.Random,
    *,
    taken: set[str] | None = None,
    legal: set[str] | None = None,
) -> str | None:
    """An item drawn in proportion to use, or None for no item.

    Items already on the team are excluded (Item Clause), and so are items the
    regulation does not have. Holding nothing is always allowed.
    """
    candidates = {
        item: weight
        for item, weight in dist.items.items()
        if item == NO_ITEM
        or ((taken is None or item not in taken) and (legal is None or item in legal))
    }
    choice = _weighted_choice(rng, candidates)
    return choice or None


def sample_spread(
    dist: SetDistribution, rng: random.Random
) -> tuple[str | None, tuple[int, ...] | None]:
    """(nature, Stat Points) drawn in proportion to use.

    A distribution with spreads gives both. One with natures only -- an open
    sheet -- gives the nature and leaves the Stat Points to the caller.
    """
    if dist.spreads:
        nature, points = _weighted_choice(rng, dist.spreads)
        return nature, points
    if dist.natures:
        return _weighted_choice(rng, dist.natures), None
    return None, None
