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
from champions_ai.mechanics.damage import attacking_side, estimate_damage
from champions_ai.mechanics.stats import (
    assumed_stats,
    estimate_stats,
    hp_stat,
    other_stat,
)

# Base power assumed for an attack we have not seen. Roughly a standard STAB
# move -- enough that an unknown Pokemon does not read as harmless, which is
# the failure mode experiment 0001 documented for one-turn search.
ASSUMED_MOVE_POWER = 80

# Moving first is worth the exchange it prevents: if we would remove them this
# turn, they never get to hit us. So the edge is the chance our hit *ends it*
# times what ending it saves -- not a flat constant, and not the damage
# fraction either. Damage fraction is the wrong proxy for a knockout: a 38%
# hit is a long way from lethal, so charging a slow attacker 38% of its output
# punished it for damage that was never going to land the blow.
#
# The flat version was measured wrong. At the old SPEED_EDGE of 0.15 the swing
# between outspeeding and being outsped was 0.30, while a 2x type advantage
# buys only the neutral damage fraction back, whose median across the real
# Champions dex is 0.224. Speed therefore beat a doubled type advantage on 78%
# of typical hits, which is not how the format plays.


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
    """Signed value of the turn order: positive when we act first.

    Scales with `offence * defence`, so it is large in a knockout race and
    near zero when neither side can hurt the other -- which is what moving
    first actually means.
    """

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
    weather: str | None = None,
) -> tuple[float, float]:
    """(expected fraction of the defender's HP removed, chance of a knockout).

    The knockout chance comes from the damage roll the estimator already
    computes rather than from the fraction: guaranteed when the worst roll
    finishes it, half when only the best roll does.
    """
    best = 0.0
    best_ko = 0.0
    for move in moves:
        if not move.is_damaging:
            continue
        # Body Press swings with Defense and Psyshock lands on it, so the
        # category is not enough to say which stats are involved.
        estimate = estimate_damage(
            dex,
            move,
            attacker=attacker,
            # Foul Play swings with the defender's Attack, so the stat can
            # come off the other side of this pairing entirely.
            attack_stat=attacking_side(
                move, user=attack_stats, target=defence_stats
            )[move.offensive_stat],
            defender=defender,
            defense_stat=defence_stats[move.defensive_stat],
            defender_hp=defender_hp,
            level=level,
            doubles=doubles,
            weather=weather,
        )
        expected = estimate.average_fraction * move.hit_chance
        if expected > best:
            best = expected
            if estimate.guaranteed_ko:
                best_ko = move.hit_chance
            elif estimate.possible_ko:
                best_ko = 0.5 * move.hit_chance
            else:
                best_ko = 0.0
    return min(best, 1.0), best_ko


def matchup(
    dex: Dex,
    ours: PokemonSet,
    theirs: SpeciesInfo,
    *,
    level: int,
    doubles: bool = True,
    # See HeuristicAgent: twelve per stat exceeds the regulation budget.
    assumed_points: int = 11,
    our_stats: dict[str, int] | None = None,
    our_hp: int | None = None,
    their_hp: int | None = None,
    their_moves: list[MoveInfo] | None = None,
    weather: str | None = None,
) -> Matchup:
    """Score our Pokemon against a species we know nothing else about.

    Our side uses the real moveset and real Stat Points, because we have them.
    Theirs uses `assumed_attacks` and an even Stat Point spread, because at
    Team Preview nothing else is visible.

    The overrides exist for the *in-battle* caller, which knows more than Team
    Preview does: the engine's computed stats, current HP on both sides, and
    whichever of the opponent's moves have actually been revealed. Passing them
    is what makes the same function answer "should I switch" as well as "who
    should I bring".
    """
    our_species = dex.get_species(ours.species)
    our_stats = our_stats if our_stats is not None else own_stats(dex, ours)
    their_stats = estimate_stats(theirs.base_stats, assumed_points)

    our_moves = []
    for move_id in ours.moves:
        try:
            our_moves.append(dex.get_move(move_id))
        except KeyError:
            continue

    offence, our_ko = _best_fraction(
        dex, our_moves, our_species, our_stats, theirs, their_stats,
        their_hp if their_hp is not None else their_stats["hp"], level, doubles,
        weather,
    )
    # Their attacking stats get the investment credit; the defensive ones they
    # showed us above do not.
    their_offence = dict(their_stats)
    for key in ("atk", "spa"):
        their_offence[key] = assumed_stats(theirs.base_stats, assumed_points, attacking=key)[key]
    defence, their_ko = _best_fraction(
        dex,
        # Revealed moves when the caller has any: a threat we have actually
        # seen beats a guess about one we have not.
        their_moves if their_moves else assumed_attacks(theirs),
        theirs, their_offence, our_species, our_stats,
        our_hp if our_hp is not None else our_stats["hp"], level, doubles,
        weather,
    )
    # A speed tie is a coin flip, not a loss. Scoring it as a loss made a
    # neutral attacker that happened to be faster outrank a super-effective
    # one that merely tied.
    if our_stats["spe"] > their_stats["spe"]:
        # We end it first, so their hit never arrives.
        edge = our_ko * defence
    elif our_stats["spe"] < their_stats["spe"]:
        # They end it first, so our attack never happens.
        edge = -their_ko * offence
    else:
        edge = 0.0
    return Matchup(offence=offence, defence=defence, speed_edge=edge)
