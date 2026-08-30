"""Setting up is a bet on being around to collect, and the score has to say so.

A stat stage used to cost a flat 0.12 health bars, which made Swords Dance
worth 24 and therefore worth using whenever the best attack on the sheet did
under 24% of a bar. That is a judgement about how hard we hit. The trade is
about how long we last:

    attack every turn ->  f * T          set up first ->  m * f * (T - 1)

so the `f` cancels and only tenure decides. These tests hold the board still
and move only our own health, which the flat price cannot see at all -- it
returns 24 whether we are about to sweep or about to faint.
"""

import pytest

from champions_ai.agents import HeuristicAgent
from champions_ai.dex import BaseStats, Dex, MoveInfo, SpeciesInfo, TypeChart
from champions_ai.domain import (
    REGULATION_M_B,
    BattlePokemon,
    BattleState,
    MoveAction,
    Observation,
    PokemonSet,
    Side,
    TargetSlot,
)

TYPES = ("Normal",)

BRUISER = SpeciesInfo(
    species_id="bruiser",
    name="Bruiser",
    types=("Normal",),
    base_stats=BaseStats(
        hp=90, attack=120, defense=80, special_attack=60, special_defense=80, speed=90
    ),
)

MOVES = {
    "swordsdance": MoveInfo(
        move_id="swordsdance",
        name="Swords Dance",
        type="Normal",
        category="Status",
        base_power=0,
        accuracy=None,
        priority=0,
        target="self",
        boosts={"atk": 2},
    ),
    "slam": MoveInfo(
        move_id="slam",
        name="Slam",
        type="Normal",
        category="Physical",
        base_power=70,
        accuracy=100,
        priority=0,
        target="normal",
    ),
    "mindreader": MoveInfo(
        move_id="mindreader",
        name="Mind Reader",
        type="Normal",
        category="Status",
        base_power=0,
        accuracy=None,
        priority=0,
        target="self",
        boosts={"spa": 2},
    ),
}

ORDER = ("swordsdance", "slam", "mindreader")
SWORDS_DANCE, SLAM, SPECIAL_SETUP = 0, 1, 2


@pytest.fixture
def agent() -> HeuristicAgent:
    dex = Dex(
        species={BRUISER.species_id: BRUISER},
        moves=MOVES,
        types=TYPES,
        type_chart=TypeChart(multipliers={"Normal": {"Normal": 1.0}}),
    )
    return HeuristicAgent(dex)


def _mon(hp_fraction: float = 1.0) -> BattlePokemon:
    max_hp = 200
    return BattlePokemon(
        pokemon_set=PokemonSet(species="Bruiser", level=50, ability="", moves=ORDER),
        current_hp=max(1, round(max_hp * hp_fraction)),
        max_hp=max_hp,
        computed_stats={"hp": max_hp, "atk": 140, "def": 90, "spa": 70, "spd": 90, "spe": 100},
        choosable_moves=ORDER,
        choosable_move_targets=tuple(MOVES[m].target for m in ORDER),
        has_been_active=True,
    )


def _observation(our_hp: float) -> Observation:
    ours = Side(team=(_mon(our_hp), _mon(), _mon(), _mon()), active_slots=(0, None))
    theirs = Side(team=tuple(_mon() for _ in range(4)), active_slots=(0, None))
    state = BattleState(regulation=REGULATION_M_B, turn=3, sides=(ours, theirs))
    return Observation.from_battle_state(state, player=0)


def _score(agent, our_hp: float, index: int) -> float:
    target = TargetSlot(side="foe", slot=0) if index == SLAM else None
    return agent.score_slot_action(
        _observation(our_hp), 0, MoveAction(move_index=index, target=target)
    ).score


class TestTenureDecidesSetup:
    def test_healthy_prefers_to_set_up(self, agent):
        assert _score(agent, 1.0, SWORDS_DANCE) > _score(agent, 1.0, SLAM)

    def test_nearly_fainting_prefers_to_attack(self, agent):
        assert _score(agent, 0.08, SWORDS_DANCE) < _score(agent, 0.08, SLAM)

    def test_the_same_board_flips_on_our_health_alone(self, agent):
        """The whole claim, in one assertion.

        Nothing about the opponent, the move or the damage changes between
        these two boards -- only how long we can expect to be standing. A flat
        stage price scores Swords Dance identically in both.
        """
        healthy = _score(agent, 1.0, SWORDS_DANCE)
        dying = _score(agent, 0.08, SWORDS_DANCE)
        assert healthy > dying

    def test_setup_is_worth_more_the_healthier_we_are(self, agent):
        """Strictly more, not merely no less.

        `sorted` alone passes on a flat price, which returns the same 24.0 at
        every health level -- exactly the behaviour these tests exist to rule
        out.
        """
        scores = [_score(agent, hp, SWORDS_DANCE) for hp in (0.1, 0.3, 0.6, 1.0)]
        assert all(a < b for a, b in zip(scores, scores[1:])), scores


class TestBoostIsPricedAgainstMovesItHelps:
    def test_a_special_boost_is_not_paid_for_by_physical_attacks(self, agent):
        """This Pokemon has 140 Attack and 70 Special Attack, and only a
        physical attack on its sheet. Raising Special Attack buys nothing, and
        pricing it off the best attack available regardless of category would
        have said otherwise."""
        assert _score(agent, 1.0, SPECIAL_SETUP) < _score(agent, 1.0, SWORDS_DANCE)
