"""`matchup` reads our own ability and item.

Ours are never hidden, but `matchup` never read them: every score it produced
treated our Pokemon as though it had no ability and no item, and compared Speed
on the raw stat. That fed Team Preview and every switch decision.

Each test turns on one thing and checks the number it should move. The
opponent's ability and item stay unknown throughout, as they are at Team
Preview.
"""

from champions_ai.dex import BaseStats, Dex, MoveInfo, SpeciesInfo, TypeChart
from champions_ai.domain import PokemonSet
from champions_ai.mechanics import estimate_stats, matchup

TYPES = ("Normal", "Ground")
STATS = BaseStats(hp=90, attack=90, defense=90, special_attack=90, special_defense=90, speed=90)

OURS = SpeciesInfo(
    species_id="ours", name="Ours", types=("Normal",), base_stats=STATS, abilities=("Run Away",)
)
DIGGER = SpeciesInfo(
    species_id="digger", name="Digger", types=("Ground",), base_stats=STATS,
    abilities=("Run Away",),
)
PLAIN = SpeciesInfo(
    species_id="plain", name="Plain", types=("Normal",), base_stats=STATS, abilities=("Run Away",)
)
DEX = Dex(
    species={s.species_id: s for s in (OURS, DIGGER, PLAIN)},
    moves={
        "tackle": MoveInfo(
            move_id="tackle", name="Tackle", type="Normal", category="Physical",
            base_power=80, accuracy=100, priority=0, target="normal",
        ),
    },
    types=TYPES,
    type_chart=TypeChart(multipliers={a: dict.fromkeys(TYPES, 1.0) for a in TYPES}),
)
SET = PokemonSet(species="Ours", level=50, ability="", moves=("tackle",))
THEIR_SPEED = estimate_stats(STATS, 11)["spe"]


def _score(theirs=PLAIN, **kwargs):
    return matchup(DEX, SET, theirs, level=50, **kwargs)


def test_passing_nothing_is_the_old_behaviour_exactly():
    assert _score() == _score(our_ability=None, our_item=None)


def test_our_attacking_ability_raises_our_offence():
    assert _score(our_ability="hugepower").offence > _score().offence


def test_our_defensive_ability_lowers_what_they_do_to_us():
    """Levitate against a Ground attacker: its assumed Ground attacks cannot land."""
    assert _score(DIGGER, our_ability="levitate").defence < _score(DIGGER).defence


def _race(our_speed, **kwargs):
    """A knockout race either way, so the speed edge's sign is who moves first."""
    stats = {"hp": 200, "atk": 150, "def": 100, "spa": 100, "spd": 100, "spe": our_speed}
    return _score(our_stats=stats, our_hp=1, their_hp=1, **kwargs).speed_edge


def test_a_weather_speed_ability_turns_a_slower_pokemon_faster_in_its_weather():
    slower = THEIR_SPEED - 10
    assert _race(slower) < 0
    assert _race(slower, our_ability="swiftswim", weather="raindance") > 0
    assert _race(slower, our_ability="swiftswim") < 0


def test_an_item_that_halves_speed_turns_a_faster_pokemon_slower():
    faster = THEIR_SPEED + 10
    assert _race(faster) > 0
    assert _race(faster, our_item="ironball") < 0
