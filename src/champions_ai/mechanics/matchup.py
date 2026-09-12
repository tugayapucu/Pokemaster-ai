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

import math
from dataclasses import dataclass

from champions_ai.dex import Dex, MoveInfo, SpeciesInfo
from champions_ai.domain import PokemonSet
from champions_ai.mechanics.charge import (
    CHARGE_TURN_MULTIPLIER,
    RECHARGE_FLAG,
    charges_this_turn,
    recharge_multiplier,
)
from champions_ai.mechanics.damage import attacking_side, estimate_damage
from champions_ai.mechanics.stats import (
    assumed_stats,
    estimate_stats,
    hp_stat,
    other_stat,
)
from champions_ai.mechanics.turn_order import effective_speed

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
    terrain: str | None = None,
    attacker_ability: str | None = None,
    attacker_item: str | None = None,
    defender_ability: str | None = None,
    defender_item: str | None = None,
    price_turn_costs: bool = False,
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
            terrain=terrain,
            attacker_ability=attacker_ability,
            attacker_item=attacker_item,
            defender_ability=defender_ability,
            defender_item=defender_item,
        )
        expected = estimate.average_fraction * move.hit_chance
        # Moves that cost a turn, priced per turn they commit -- the same
        # prices the move scorer uses. A charge move charging this turn lands
        # nothing now, so it also cannot win a knockout race this turn. A
        # recharge move does land now, so its knockout chance stands.
        ko_scale = 1.0
        if price_turn_costs:
            if charges_this_turn(
                move, weather=weather, ability=attacker_ability, item=attacker_item
            ):
                expected *= CHARGE_TURN_MULTIPLIER
                ko_scale = 0.0
            elif RECHARGE_FLAG in move.flags:
                expected *= recharge_multiplier(move)
        if expected > best:
            best = expected
            if estimate.guaranteed_ko:
                best_ko = move.hit_chance * ko_scale
            elif estimate.possible_ko:
                best_ko = 0.5 * move.hit_chance * ko_scale
            else:
                best_ko = 0.0
    return min(best, 1.0), best_ko


def hits_to_knock_out(fraction: float) -> float:
    """Hits needed to remove a whole health bar at `fraction` of it per hit."""
    if fraction <= 0:
        return math.inf
    # Rounded before the ceiling so 1 / 0.5 does not become 2.0000000001 -> 3.
    return float(math.ceil(round(1.0 / fraction, 9)))


def _finishes_first(
    dealt: float,
    taken: float,
    ko_chance: float,
    beyond_knockouts: bool,
    race_credit: float = 1.0,
) -> float:
    """Chance the faster side ends the race no later than the slower one could.

    `dealt` is the faster side's expected hit, `taken` the slower side's.
    """
    if not beyond_knockouts:
        return ko_chance
    hits = hits_to_knock_out(dealt)
    if hits <= 1:
        # A one-hit race keeps the knockout chance from the damage roll, which
        # is sharper than the expected fraction.
        return ko_chance
    return race_credit if hits <= hits_to_knock_out(taken) else 0.0


def order_edge(
    offence: float,
    defence: float,
    our_ko: float,
    their_ko: float,
    our_speed: float,
    their_speed: float,
    *,
    beyond_knockouts: bool = False,
    race_credit: float = 1.0,
) -> float:
    """Signed value of the turn order, in fractions of HP.

    Moving first is worth the hit it denies: on the turn a side finishes the
    race, the other side's attack that turn never lands.

    Without `beyond_knockouts` only a one-hit race counts, which is the rule
    this project always had -- and it prices speed at nothing for a Pokemon
    that rarely knocks out in one hit, however much faster it is. With it, the
    race runs over as many hits as it takes: the faster side denies the slower
    side's hit whenever it needs no more hits than the slower side does. Needing
    two against their two, moving first wins a race that moving second loses.

    Still a race between two Pokemon: no switching, no Protect, no partners.
    That is why `race_credit` exists: the share of the denied hit credited in a
    race longer than one hit, standing in for how often doubles lets a race run
    to its end. 1 credits the whole hit (0055, which over-valued speed); 0 is
    the one-hit rule exactly. A one-hit race is unaffected at every value.
    """
    if not 0.0 <= race_credit <= 1.0:
        raise ValueError(f"race_credit must be within [0, 1], got {race_credit}")
    if our_speed == their_speed:
        return 0.0
    if our_speed > their_speed:
        first = _finishes_first(offence, defence, our_ko, beyond_knockouts, race_credit)
        return first * defence
    first = _finishes_first(defence, offence, their_ko, beyond_knockouts, race_credit)
    return -first * offence


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
    # `estimate_damage` has taken a terrain all along -- it is what applies the
    # 1.3 to a Grass move in Grassy Terrain, Expanding Force's spread bonus and
    # Grass Pelt's defence -- but nothing above it ever passed one, so every
    # matchup this project has ever scored was scored on bare ground. The two
    # commonest field effects in Reg M-C are terrains (Rillaboom at 39.2% of
    # teams, Indeedee-F at 22.1%), so the omission was not a small one.
    terrain: str | None = None,
    # Our own ability and item, as Showdown ids. Ours are never hidden -- the
    # set says what they are, and in battle the engine's request does -- but
    # nothing here read them, so every matchup was scored as though our
    # Pokemon had neither: no attacking or defensive ability, no item, and a
    # Speed comparison on the raw stat. The opponent's stay unknown, as they
    # are at Team Preview. None for both is the old behaviour exactly.
    our_ability: str | None = None,
    our_item: str | None = None,
    # Price moves that cost a turn -- a charge move charging now, a recharge
    # move -- per turn they commit, as the move scorer does. It priced both as
    # free, instant hits here, so Team Preview and switching overrated any
    # Pokemon whose best move was one of them. Off by default: the old numbers
    # exactly, until a caller opts in.
    price_turn_costs: bool = False,
    # Whether moving first is valued over a race of any length rather than only
    # in a one-hit knockout race. See `order_edge`. Off by default: the old
    # numbers exactly.
    speed_beyond_knockouts: bool = False,
    # With `speed_beyond_knockouts`, the share of a denied hit credited in a
    # race longer than one hit. See `order_edge`. 1.0 is 0055's rule.
    speed_race_credit: float = 1.0,
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
        weather, terrain,
        attacker_ability=our_ability,
        attacker_item=our_item,
        price_turn_costs=price_turn_costs,
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
        weather, terrain,
        defender_ability=our_ability,
        defender_item=our_item,
        price_turn_costs=price_turn_costs,
    )
    # A speed tie is a coin flip, not a loss. Scoring it as a loss made a
    # neutral attacker that happened to be faster outrank a super-effective
    # one that merely tied.
    # Our Speed as the engine orders on it: the item's multiplier, and an
    # ability that doubles Speed in its own weather. Theirs stays the raw
    # estimate, because at Team Preview neither their item nor their ability
    # is known.
    our_speed = effective_speed(
        our_stats["spe"],
        item=our_item,
        ability=our_ability,
        weather=weather,
        holds_item=our_item is not None,
    )
    their_speed = their_stats["spe"]
    edge = order_edge(
        offence, defence, our_ko, their_ko, our_speed, their_speed,
        beyond_knockouts=speed_beyond_knockouts,
        race_credit=speed_race_credit,
    )
    return Matchup(offence=offence, defence=defence, speed_edge=edge)
