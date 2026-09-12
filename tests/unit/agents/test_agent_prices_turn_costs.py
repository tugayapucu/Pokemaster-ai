"""The agent tells `matchup()` to price moves that cost a turn.

Two callers: Team Preview and switch scoring. In each, a Pokemon whose only
attack is a recharge move must rate lower with `matchup_turn_costs` on than off,
and a Pokemon with an ordinary attack must not move at all.
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

STATS = BaseStats(hp=90, attack=90, defense=90, special_attack=110, special_defense=90, speed=90)
NAMES = ["Blaster", "Plainer", "Fill1", "Fill2", "Fill3", "Fill4",
         "Foe1", "Foe2", "Foe3", "Foe4", "Foe5", "Foe6"]


def _move(move_id, flags):
    return MoveInfo(
        move_id=move_id, name=move_id, type="Normal", category="Special",
        base_power=150, accuracy=90, priority=0, target="normal", flags=frozenset(flags),
    )


DEX = Dex(
    species={
        n.lower(): SpeciesInfo(species_id=n.lower(), name=n, types=("Normal",),
                               base_stats=STATS, abilities=("Run Away",))
        for n in NAMES
    },
    moves={
        "megablast": _move("megablast", {"recharge", "protect"}),
        "plainblast": _move("plainblast", {"protect"}),
    },
    types=("Normal",),
    type_chart=TypeChart(multipliers={"Normal": {"Normal": 1.0}}),
)


def _set(species):
    move = "megablast" if species == "Blaster" else "plainblast"
    return PokemonSet(species=species, level=50, ability="Run Away", moves=(move,))


def _preview():
    return TeamPreview(
        regulation=REGULATION_M_C,
        own_team=Team(pokemon=tuple(_set(n) for n in NAMES[:6])),
        opponent_team=tuple(RevealedPokemon(species=n, level=50) for n in NAMES[6:]),
    )


def test_team_preview_rates_a_recharge_attacker_lower():
    on = HeuristicAgent(DEX).matchup_table(_preview())
    off = HeuristicAgent(DEX, matchup_turn_costs=False).matchup_table(_preview())
    assert sum(on[0]) < sum(off[0])
    assert on[1:] == off[1:]


def _battle_mon(species):
    move = "megablast" if species == "Blaster" else "plainblast"
    return BattlePokemon(
        pokemon_set=PokemonSet(species=species, level=50, ability="runaway", moves=(move,)),
        current_hp=180, max_hp=180, current_ability="runaway",
        computed_stats={"atk": 100, "def": 110, "spa": 140, "spd": 110, "spe": 100},
        choosable_moves=(move,),
    )


def _observation():
    return Observation(
        regulation=REGULATION_M_B, turn=2, player=0,
        own_side=Side(
            team=(_battle_mon("Plainer"), _battle_mon("Blaster")), active_slots=(0, None)
        ),
        opponent_side=ObservedSide(
            revealed=(ObservedPokemon(species="Foe1", level=50, hp_percent=100, fainted=False),),
            active_slots=(0, None),
        ),
    )


def test_switching_into_a_recharge_attacker_is_worth_less():
    action = SwitchAction(team_index=1)
    on = HeuristicAgent(DEX).score_slot_action(_observation(), 0, action).score
    off = HeuristicAgent(DEX, matchup_turn_costs=False).score_slot_action(
        _observation(), 0, action
    ).score
    assert on < off
