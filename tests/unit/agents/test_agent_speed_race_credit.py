"""The agent passes `speed_race_credit` through to `matchup()`.

A much faster Pokemon in a race longer than one hit: with the whole denied hit
credited its Team Preview row rises the most, with none credited it matches the
flag being off, and half credit lands strictly between.
"""

from champions_ai.agents import HeuristicAgent
from champions_ai.dex import BaseStats, Dex, MoveInfo, SpeciesInfo, TypeChart
from champions_ai.domain import REGULATION_M_C, PokemonSet, RevealedPokemon, Team, TeamPreview

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


def _quick_row(**kwargs):
    return sum(HeuristicAgent(DEX, **kwargs).matchup_table(_preview())[0])


def test_half_credit_lands_between_none_and_all():
    off = _quick_row()
    half = _quick_row(speed_beyond_knockouts=True, speed_race_credit=0.5)
    full = _quick_row(speed_beyond_knockouts=True, speed_race_credit=1.0)
    assert off < half < full


def test_zero_credit_matches_the_flag_being_off():
    assert _quick_row(speed_beyond_knockouts=True, speed_race_credit=0.0) == _quick_row()
