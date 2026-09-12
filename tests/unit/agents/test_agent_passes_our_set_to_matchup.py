"""The agent tells `matchup()` our own ability and item.

Two callers, two sources. Team Preview reads the team sheet, whose names have
to become ids first ("Huge Power" is keyed "hugepower"). Switch scoring reads
the battle's current ability and item, which can differ from the sheet once an
item is consumed or knocked off.

Each test compares the flag on against off on the same situation, and the ability
used -- Huge Power, which doubles Attack -- can only move the number through the
path under test.
"""

from champions_ai.agents import HeuristicAgent
from champions_ai.dex import BaseStats, Dex, MoveInfo, SpeciesInfo, TypeChart
from champions_ai.domain import (
    REGULATION_M_B,
    REGULATION_M_C,
    BattlePokemon,
    Observation,
    ObservedPokemon,
    ObservedSide,
    PokemonSet,
    RevealedPokemon,
    Side,
    SwitchAction,
    Team,
    TeamPreview,
)

STATS = BaseStats(hp=90, attack=90, defense=90, special_attack=90, special_defense=90, speed=90)
NAMES = ["Brawler", "Filler1", "Filler2", "Filler3", "Filler4", "Filler5",
         "Foe1", "Foe2", "Foe3", "Foe4", "Foe5", "Foe6"]
DEX = Dex(
    species={
        n.lower(): SpeciesInfo(
            species_id=n.lower(), name=n, types=("Normal",), base_stats=STATS,
            abilities=("Huge Power",),
        )
        for n in NAMES
    },
    moves={
        "tackle": MoveInfo(
            move_id="tackle", name="Tackle", type="Normal", category="Physical",
            base_power=80, accuracy=100, priority=0, target="normal",
        ),
    },
    types=("Normal",),
    type_chart=TypeChart(multipliers={"Normal": {"Normal": 1.0}}),
)


def _preview():
    ours = [PokemonSet(species="Brawler", level=50, ability="Huge Power", moves=("tackle",))]
    ours += [
        PokemonSet(species=n, level=50, ability="Run Away", moves=("tackle",))
        for n in NAMES[1:6]
    ]
    return TeamPreview(
        regulation=REGULATION_M_C,
        own_team=Team(pokemon=tuple(ours)),
        opponent_team=tuple(RevealedPokemon(species=n, level=50) for n in NAMES[6:]),
    )


def test_team_preview_reads_the_sheets_ability_after_converting_it_to_an_id():
    on = HeuristicAgent(DEX).matchup_table(_preview())
    off = HeuristicAgent(DEX, matchup_reads_our_set=False).matchup_table(_preview())
    assert sum(on[0]) > sum(off[0])
    assert on[1:] == off[1:]


def _battle_mon(species, ability):
    return BattlePokemon(
        pokemon_set=PokemonSet(species=species, level=50, ability=ability, moves=("tackle",)),
        current_hp=180, max_hp=180,
        current_ability=ability,
        computed_stats={"atk": 120, "def": 110, "spa": 110, "spd": 110, "spe": 100},
        choosable_moves=("tackle",),
    )


def _observation():
    team = (_battle_mon("Filler1", "runaway"), _battle_mon("Brawler", "hugepower"))
    return Observation(
        regulation=REGULATION_M_B, turn=2, player=0,
        own_side=Side(team=team, active_slots=(0, None)),
        opponent_side=ObservedSide(
            revealed=(ObservedPokemon(species="Foe1", level=50, hp_percent=100, fainted=False),),
            active_slots=(0, None),
        ),
    )


def test_switch_scoring_reads_the_battles_current_ability():
    action = SwitchAction(team_index=1)
    on = HeuristicAgent(DEX).score_slot_action(_observation(), 0, action).score
    off = HeuristicAgent(DEX, matchup_reads_our_set=False).score_slot_action(
        _observation(), 0, action
    ).score
    assert on > off
