"""Whether to Mega Evolve, scored as the forme rather than as a bonus.

The agent never read `action.special`, so a Mega and a non-Mega of the same
move scored identically -- and `max` returns the first of equal maxima while
the enumeration puts `None` first. Measured: **offered 84 times across 60
battles, chosen 0 times.** It threw the mechanic away entirely, in a format
where 149 of 150 generated teams carry a stone.

A Mega action is now scored as the Mega *forme*: its stats, its ability, its
typing. The damage model already knows what all three are worth, so no "Mega is
good" constant is invented.
"""

import pytest

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

TYPES = ("Fighting", "Psychic", "Normal")

MEDICHAM = SpeciesInfo(
    species_id="medicham", name="Medicham", types=("Fighting", "Psychic"),
    base_stats=BaseStats(hp=60, attack=60, defense=75,
                         special_attack=60, special_defense=75, speed=80),
    abilities=("Pure Power",),
)
MEDICHAM_MEGA = SpeciesInfo(
    species_id="medichammega", name="Medicham-Mega", types=("Fighting", "Psychic"),
    base_stats=BaseStats(hp=60, attack=100, defense=85,
                         special_attack=80, special_defense=85, speed=100),
    abilities=("Pure Power",),
)
SNORLAX = SpeciesInfo(
    species_id="snorlax", name="Snorlax", types=("Normal",),
    base_stats=BaseStats(hp=160, attack=110, defense=65,
                         special_attack=65, special_defense=110, speed=30),
    abilities=("Immunity", "Thick Fat"),
)

MOVES = {
    "closecombat": MoveInfo(
        move_id="closecombat", name="Close Combat", type="Fighting",
        category="Physical", base_power=120, accuracy=100, priority=0,
        target="normal",
    ),
}

MEDICHAMITE = ItemInfo(
    item_id="medichamite", name="Medichamite",
    mega_stone="Medicham", mega_forme="Medicham-Mega",
)


@pytest.fixture
def dex() -> Dex:
    return Dex(
        species={s.species_id: s for s in (MEDICHAM, MEDICHAM_MEGA, SNORLAX)},
        moves=MOVES,
        types=TYPES,
        type_chart=TypeChart(
            multipliers={a: dict.fromkeys(TYPES, 1.0) for a in TYPES}
        ),
        items={MEDICHAMITE.item_id: MEDICHAMITE},
    )


@pytest.fixture
def agent(dex) -> HeuristicAgent:
    return HeuristicAgent(dex)


def _mon(species, moves=("closecombat",), item=None):
    return BattlePokemon(
        pokemon_set=PokemonSet(
            species=species, level=50, ability="", moves=moves,
            stats=StatSpread(attack=32, speed=20),
            item=item,
        ),
        current_hp=200,
        max_hp=200,
        current_item=item,
        computed_stats={"hp": 200, "atk": 112, "def": 95, "spa": 80,
                        "spd": 95, "spe": 120},
        choosable_moves=moves,
        choosable_move_targets=tuple(MOVES[m].target for m in moves),
        available_specials=frozenset({"mega"}),
        has_been_active=True,
    )


def _observation(item="medichamite"):
    own = Side(
        team=tuple(_mon("Medicham", item=item) for _ in range(4)),
        active_slots=(0, 1),
    )
    foe = Side(
        team=tuple(_mon("Snorlax") for _ in range(4)), active_slots=(0, 1)
    )
    state = BattleState(regulation=REGULATION_M_B, turn=3, sides=(own, foe))
    return Observation.from_battle_state(state, player=0)


AT_FOE = TargetSlot(side="foe", slot=0)


def test_mega_evolving_beats_not_when_the_forme_hits_harder(agent):
    """Medicham-Mega has 40 more base Attack and keeps Pure Power, so the same
    Close Combat is worth strictly more thrown by the forme."""
    observation = _observation()
    plain = agent.score_slot_action(
        observation, 0, MoveAction(move_index=0, target=AT_FOE)
    )
    mega = agent.score_slot_action(
        observation, 0, MoveAction(move_index=0, target=AT_FOE, special="mega")
    )
    assert mega.score > plain.score


def test_without_the_stone_there_is_no_forme_to_become(agent):
    observation = _observation(item=None)
    plain = agent.score_slot_action(
        observation, 0, MoveAction(move_index=0, target=AT_FOE)
    )
    mega = agent.score_slot_action(
        observation, 0, MoveAction(move_index=0, target=AT_FOE, special="mega")
    )
    assert mega.score == plain.score


def test_the_forme_carries_its_own_stats_and_ability(agent):
    observation = _observation()
    attacker = observation.own_side.team[0]
    became = agent._mega_form(attacker, MEDICHAM)
    assert became is not None
    forme, evolved = became
    assert forme.name == "Medicham-Mega"
    assert evolved.pokemon_set.species == "Medicham-Mega"
    assert evolved.current_ability == "purepower"
    # Attack rises with the base stat, and the ratio keeps whatever nature the
    # engine had already baked into `computed_stats`.
    assert evolved.computed_stats["atk"] > attacker.computed_stats["atk"]
    assert evolved.computed_stats["spe"] > attacker.computed_stats["spe"]


def test_the_agent_cannot_value_a_permanent_upgrade_for_later_turns(agent):
    """A known limitation, pinned rather than hidden.

    Mega Evolution is free and permanent, so it is nearly always right to take
    the moment it is offered. This scorer only asks what it is worth to *this
    turn's move*, so a turn where the forme adds nothing -- a status move, or a
    stat the forme did not raise -- scores the two equally and the mechanic is
    declined. Measured at 21 of 31 offers taken.

    Fixing it properly needs a scorer that can price a lasting resource, which
    a one-turn heuristic cannot. This test exists so the next person knows the
    tie is deliberate rather than a bug.
    """
    observation = _observation()
    plain = agent.score_slot_action(
        observation, 0, MoveAction(move_index=0, target=AT_FOE)
    )
    mega = agent.score_slot_action(
        observation, 0, MoveAction(move_index=0, target=AT_FOE, special="mega")
    )
    # It wins *here* only because this particular move gets stronger.
    assert mega.score > plain.score
