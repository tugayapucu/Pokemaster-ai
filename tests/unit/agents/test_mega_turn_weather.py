"""On the turn a Pokemon Mega Evolves, its move is thrown in the weather its forme sets.

Mega Evolution resolves before any move of the turn (`megaEvo: 104` against
moves at `200` in `battle-queue.ts`), and `formeChange` hands the forme its
ability through `setAbility`, which fires `Start`. So a forme that sets weather
on arrival has it up by the time it attacks. The agent scored that turn in the
old weather.

Two Megas below are identical except for their ability, which isolates the
weather as the only thing that can move the score.
"""

from champions_ai.agents import HeuristicAgent
from champions_ai.dex import BaseStats, Dex, ItemInfo, MoveInfo, SpeciesInfo, TypeChart
from champions_ai.domain import (
    REGULATION_M_B,
    BattlePokemon,
    BattleState,
    MoveAction,
    Observation,
    PokemonSet,
    Side,
    StatSpread,
    TargetSlot,
)

TYPES = ("Fire", "Water", "Normal")
STATS = BaseStats(hp=80, attack=80, defense=80, special_attack=110, special_defense=80, speed=90)
MEGA_STATS = BaseStats(
    hp=80, attack=80, defense=80, special_attack=150, special_defense=80, speed=100
)

KINDLE = SpeciesInfo(
    species_id="kindle", name="Kindle", types=("Fire",), base_stats=STATS, abilities=("Blaze",)
)
TARGET = SpeciesInfo(
    species_id="target", name="Target", types=("Normal",), base_stats=STATS, abilities=("Run Away",)
)
MOVES = {
    "flame": MoveInfo(
        move_id="flame", name="Flame", type="Fire", category="Special",
        base_power=90, accuracy=100, priority=0, target="normal",
    ),
}
STONE = ItemInfo(item_id="kindlite", name="Kindlite", mega_stone="Kindle", mega_forme="Kindle-Mega")


def _dex(mega_ability: str) -> Dex:
    mega = SpeciesInfo(
        species_id="kindlemega", name="Kindle-Mega", types=("Fire",),
        base_stats=MEGA_STATS, abilities=(mega_ability,),
    )
    return Dex(
        species={s.species_id: s for s in (KINDLE, mega, TARGET)},
        moves=MOVES,
        types=TYPES,
        type_chart=TypeChart(multipliers={a: dict.fromkeys(TYPES, 1.0) for a in TYPES}),
        items={STONE.item_id: STONE},
    )


def _mon(species, item=None):
    return BattlePokemon(
        pokemon_set=PokemonSet(
            species=species, level=50, ability="", moves=("flame",),
            stats=StatSpread(special_attack=32, speed=20), item=item,
        ),
        current_hp=180,
        max_hp=180,
        current_item=item,
        computed_stats={"hp": 180, "atk": 100, "def": 100, "spa": 150, "spd": 100, "spe": 120},
        choosable_moves=("flame",),
        choosable_move_targets=("normal",),
        available_specials=frozenset({"mega"}),
        has_been_active=True,
    )


def _observation(weather=None):
    own = Side(team=tuple(_mon("Kindle", item="kindlite") for _ in range(4)), active_slots=(0, 1))
    foe = Side(team=tuple(_mon("Target") for _ in range(4)), active_slots=(0, 1))
    state = BattleState(regulation=REGULATION_M_B, turn=3, sides=(own, foe), weather=weather)
    return Observation.from_battle_state(state, player=0)


AT_FOE = TargetSlot(side="foe", slot=0)


def _score(dex, special, weather=None):
    return HeuristicAgent(dex).score_slot_action(
        _observation(weather), 0, MoveAction(move_index=0, target=AT_FOE, special=special)
    ).score


def test_a_forme_that_brings_sun_throws_its_fire_move_in_the_sun():
    assert _score(_dex("Drought"), "mega") > _score(_dex("Inner Focus"), "mega")


def test_a_forme_that_brings_rain_throws_its_fire_move_in_the_rain():
    """The other direction, so the test cannot pass on any change at all."""
    assert _score(_dex("Drizzle"), "mega") < _score(_dex("Inner Focus"), "mega")


def test_not_mega_evolving_leaves_the_field_as_it_is():
    """The forme's ability is not the base Pokemon's, and nothing changes the
    weather unless the evolution actually happens."""
    assert _score(_dex("Drought"), None) == _score(_dex("Inner Focus"), None)


def test_a_forme_that_sets_nothing_keeps_the_field_weather():
    """Rain still halves the Fire move: the fix must fall back to the field's
    weather, not replace it with nothing."""
    assert _score(_dex("Inner Focus"), "mega", weather="raindance") < _score(
        _dex("Inner Focus"), "mega"
    )


def test_mega_sol_is_read_as_sun_and_is_not_a_setter():
    """Mega Sol makes its holder's moves see sun whatever the field says, so
    rain and a dry field score the same -- and that is the damage model's
    doing, not this fix treating Mega Sol as a weather it sets."""
    assert _score(_dex("Mega Sol"), "mega", weather="raindance") == _score(
        _dex("Mega Sol"), "mega"
    )
