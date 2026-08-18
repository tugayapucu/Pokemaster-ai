"""How well does one Pokemon fare against another?

The question behind three different decisions, which is why it lives here
rather than inside any one of them:

- **Team Preview** -- which four of our six answer their six;
- **switching** -- is what we would bring in better placed than what is out;
- **threat assessment** -- how badly does the thing across from us hurt.

At Team Preview the opponent's moves, item and ability are all hidden (ADR
0002), so a matchup can only be built from species: typing, base stats, and a
*prior* over what they are likely to be holding. That prior is stated openly
rather than hidden in a constant, because it is the single biggest assumption
here and Milestone 10 is meant to replace it with something inferred.
"""

from dataclasses import dataclass

from champions_ai.dex import Dex, MoveInfo, SpeciesInfo
from champions_ai.domain import PokemonSet
from champions_ai.mechanics.damage import estimate_damage
from champions_ai.mechanics.stats import estimate_stats, hp_stat, other_stat

# Base power assumed for an attack we have not seen. Roughly a standard STAB
# move -- enough that an unknown Pokemon does not read as harmless, which is
# the failure mode experiment 0001 documented for one-turn search.
ASSUMED_MOVE_POWER = 80

# How much outspeeding is worth, as a fraction of a Pokemon's HP. Moving first
# is not damage, but in a format where battles last five or six turns it
# decides who gets to act at all.
SPEED_EDGE = 0.15


def assumed_attacks(species: SpeciesInfo) -> list[MoveInfo]:
    """A standard STAB attack per type and category, for an unseen moveset.

    A prior, not a fact. Both categories are generated because which one a
    given Pokemon actually uses is exactly what is hidden; taking the worst
    over both is the pessimistic reading, and pessimism about an unknown
    attacker is the safer error.
    """
    return [
        MoveInfo(
            move_id=f"assumed{typing.lower()}{category.lower()}",
            name=f"an unseen {typing} attack",
            type=typing,
            category=category,
            base_power=ASSUMED_MOVE_POWER,
            accuracy=100,
            priority=0,
            target="normal",
        )
        for typing in species.types
        for category in ("Physical", "Special")
    ]


def own_stats(dex: Dex, pokemon: PokemonSet) -> dict[str, int]:
    """Final stats for a Pokemon whose Stat Points we actually know.

    Nature is not applied: `PokemonSet.nature` is a name and this project has
    no table mapping names to the stat they raise. Worth adding, but it shifts
    a stat by 10% and matchup ranking is coarser than that.
    """
    base = dex.get_species(pokemon.species).base_stats
    points = pokemon.stats
    return {
        "hp": hp_stat(base.hp, points.hp),
        "atk": other_stat(base.attack, points.attack),
        "def": other_stat(base.defense, points.defense),
        "spa": other_stat(base.special_attack, points.special_attack),
        "spd": other_stat(base.special_defense, points.special_defense),
        "spe": other_stat(base.speed, points.speed),
    }


@dataclass(frozen=True)
class Matchup:
    """One Pokemon against another, from the first one's point of view."""

    offence: float
    """Fraction of the opponent's HP our best move is expected to remove."""
    defence: float
    """Fraction of our HP their best expected attack would remove."""
    speed_edge: float
    """+SPEED_EDGE when faster, 0 on a tie, -SPEED_EDGE when slower."""

    @property
    def outspeeds(self) -> bool:
        return self.speed_edge > 0

    @property
    def net(self) -> float:
        """Positive means favourable.

        Damage traded is the currency, and speed is priced in it: moving first
        in a five-turn format frequently decides whether the trade happens at
        all.
        """
        return self.offence - self.defence + self.speed_edge


def _best_fraction(
    dex: Dex,
    moves: list[MoveInfo],
    attacker: SpeciesInfo,
    attack_stats: dict[str, int],
    defender: SpeciesInfo,
    defence_stats: dict[str, int],
    defender_hp: int,
    level: int,
    doubles: bool,
) -> float:
    best = 0.0
    for move in moves:
        if not move.is_damaging:
            continue
        physical = move.category == "Physical"
        estimate = estimate_damage(
            dex,
            move,
            attacker=attacker,
            attack_stat=attack_stats["atk" if physical else "spa"],
            defender=defender,
            defense_stat=defence_stats["def" if physical else "spd"],
            defender_hp=defender_hp,
            level=level,
            doubles=doubles,
        )
        best = max(best, estimate.average_fraction * move.hit_chance)
    return min(best, 1.0)


def matchup(
    dex: Dex,
    ours: PokemonSet,
    theirs: SpeciesInfo,
    *,
    level: int,
    doubles: bool = True,
    assumed_points: int = 12,
) -> Matchup:
    """Score our Pokemon against a species we know nothing else about.

    Our side uses the real moveset and real Stat Points, because we have them.
    Theirs uses `assumed_attacks` and an even Stat Point spread, because at
    Team Preview nothing else is visible.
    """
    our_species = dex.get_species(ours.species)
    our_stats = own_stats(dex, ours)
    their_stats = estimate_stats(theirs.base_stats, assumed_points)

    our_moves = []
    for move_id in ours.moves:
        try:
            our_moves.append(dex.get_move(move_id))
        except KeyError:
            continue

    offence = _best_fraction(
        dex, our_moves, our_species, our_stats, theirs, their_stats,
        their_stats["hp"], level, doubles,
    )
    defence = _best_fraction(
        dex, assumed_attacks(theirs), theirs, their_stats, our_species, our_stats,
        our_stats["hp"], level, doubles,
    )
    # A speed tie is a coin flip, not a loss. Scoring it as a loss made a
    # neutral attacker that happened to be faster outrank a super-effective
    # one that merely tied.
    if our_stats["spe"] > their_stats["spe"]:
        edge = SPEED_EDGE
    elif our_stats["spe"] < their_stats["spe"]:
        edge = -SPEED_EDGE
    else:
        edge = 0.0
    return Matchup(offence=offence, defence=defence, speed_edge=edge)
