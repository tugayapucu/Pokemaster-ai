"""The agent passes `speed_beyond_knockouts` to both `matchup()` callers.

The fixture is a two-hit race: our Pokemon is much faster, both sides need
about two hits, and neither knocks out in one. The old rule prices that speed at
nothing; the new one denies the opponent's second hit.
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

QUICK = BaseStats(hp=100, attack=90, defense=90, special_attack=90, special_defense=90, speed=150)
STEADY = BaseStats(hp=100, attack=90, defense=90, special_attack=90, special_defense=90, speed=60)
NAMES = ["Quick", "Fill1", "Fill2", "Fill3", "Fill4", "Fill5",
         "Foe1", "Foe2", "Foe3", "Foe4", "Foe5", "Foe6"]
DEX = Dex(
    species={
        n.lower(): SpeciesInfo(
            species_id=n.lower(), name=n, types=("Normal",),
            base_stats=QUICK if n == "Quick" else STEADY, abilities=("Run Away",),
        )
        for n in NAMES
    },
    moves={
        "bash": MoveInfo(
            move_id="bash", name="Bash", type="Normal", category="Physical",
            base_power=140, accuracy=100, priority=0, target="normal",
        ),
    },
    types=("Normal",),
    type_chart=TypeChart(multipliers={"Normal": {"Normal": 1.0}}),
)


def _preview():
    return TeamPreview(
        regulation=REGULATION_M_C,
        own_team=Team(pokemon=tuple(
            PokemonSet(species=n, level=50, ability="Run Away", moves=("bash",))
            for n in NAMES[:6]
        )),
        opponent_team=tuple(RevealedPokemon(species=n, level=50) for n in NAMES[6:]),
    )


def test_off_by_default_the_grid_is_unchanged():
    default = HeuristicAgent(DEX).matchup_table(_preview())
    assert HeuristicAgent(DEX, speed_beyond_knockouts=False).matchup_table(_preview()) == default


def test_team_preview_credits_the_faster_pokemon_for_its_speed():
    on = HeuristicAgent(DEX, speed_beyond_knockouts=True).matchup_table(_preview())
    off = HeuristicAgent(DEX).matchup_table(_preview())
    assert sum(on[0]) > sum(off[0])


def _mon(species, spe):
    return BattlePokemon(
        pokemon_set=PokemonSet(species=species, level=50, ability="runaway", moves=("bash",)),
        current_hp=200, max_hp=200, current_ability="runaway",
        computed_stats={"atk": 120, "def": 110, "spa": 110, "spd": 110, "spe": spe},
        choosable_moves=("bash",),
    )


def _observation():
    return Observation(
        regulation=REGULATION_M_B, turn=2, player=0,
        own_side=Side(team=(_mon("Fill1", 60), _mon("Quick", 200)), active_slots=(0, None)),
        opponent_side=ObservedSide(
            revealed=(ObservedPokemon(species="Foe1", level=50, hp_percent=100, fainted=False),),
            active_slots=(0, None),
        ),
    )


def test_switch_scoring_credits_bringing_in_the_faster_pokemon():
    action = SwitchAction(team_index=1)
    on = HeuristicAgent(DEX, speed_beyond_knockouts=True).score_slot_action(
        _observation(), 0, action
    ).score
    off = HeuristicAgent(DEX).score_slot_action(_observation(), 0, action).score
    assert on > off
