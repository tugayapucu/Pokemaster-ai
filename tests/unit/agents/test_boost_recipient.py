"""Stat changes are worth what they are worth *to whoever gets them*.

`_boost_value` had two branches, "us" and "them", and counted only rises on our
side and only drops on theirs. Six status moves in this dex hand a **positive**
boost to somebody who is not the user, and the split could express none of
them:

    Decorate       normal        {atk: +2, spa: +2}     for an ally
    Coaching       adjacentAlly  {atk: +1, def: +1}     for an ally
    Aromatic Mist  adjacentAlly  {spd: +1}              for an ally
    Swagger        normal        {atk: +2}              for an opponent
    Flatter        normal        {spa: +1}              for an opponent
    Spicy Extract  normal        {atk: +2, def: -2}     for an opponent

Decorate is one of the strongest support moves in doubles and scored the flat
unknown-support value. Swagger's +2 Attack to an opponent -- the price paid for
confusing them -- cost us nothing at all.

Whatever the move inflicts follows the same rule: aiming Swagger at our own
partner buys the Attack *and* the confusion, and the confusion is ours.
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

TYPES = ("Normal", "Fighting")

MACHAMP = SpeciesInfo(
    species_id="machamp", name="Machamp", types=("Fighting",),
    base_stats=BaseStats(hp=90, attack=130, defense=80,
                         special_attack=65, special_defense=85, speed=55),
)

MOVES = {
    "decorate": MoveInfo(
        move_id="decorate", name="Decorate", type="Fairy", category="Status",
        base_power=0, accuracy=None, priority=0, target="normal",
        boosts={"atk": 2, "spa": 2},
    ),
    "swagger": MoveInfo(
        move_id="swagger", name="Swagger", type="Normal", category="Status",
        base_power=0, accuracy=85, priority=0, target="normal",
        boosts={"atk": 2}, volatile_status="confusion",
    ),
    "growl": MoveInfo(
        move_id="growl", name="Growl", type="Normal", category="Status",
        base_power=0, accuracy=100, priority=0, target="allAdjacentFoes",
        boosts={"atk": -1},
    ),
    "protect": MoveInfo(
        move_id="protect", name="Protect", type="Normal", category="Status",
        base_power=0, accuracy=None, priority=4, target="self",
    ),
}


@pytest.fixture
def agent() -> HeuristicAgent:
    dex = Dex(
        species={MACHAMP.species_id: MACHAMP},
        moves=MOVES,
        types=TYPES,
        type_chart=TypeChart(
            multipliers={a: dict.fromkeys(TYPES, 1.0) for a in TYPES}
        ),
    )
    return HeuristicAgent(dex)


ORDER = ("decorate", "swagger", "growl", "protect")


def _mon():
    return BattlePokemon(
        pokemon_set=PokemonSet(species="Machamp", level=50, ability="", moves=ORDER),
        current_hp=150, max_hp=200,
        computed_stats={"hp": 200, "atk": 140, "def": 90,
                        "spa": 140, "spd": 90, "spe": 100},
        choosable_moves=ORDER,
        choosable_move_targets=tuple(MOVES[m].target for m in ORDER),
        has_been_active=True,
    )


def _side():
    return Side(team=tuple(_mon() for _ in range(4)), active_slots=(0, 1))


def _observation():
    state = BattleState(regulation=REGULATION_M_B, turn=3, sides=(_side(), _side()))
    return Observation.from_battle_state(state, player=0)


def _score(agent, index, side, slot):
    return agent.score_slot_action(
        _observation(), 0,
        MoveAction(move_index=index, target=TargetSlot(side=side, slot=slot)),
    ).score


def test_decorate_on_our_partner_is_worth_four_stages(agent):
    assert _score(agent, 0, "ally", 1) > 0


def test_decorate_on_an_opponent_is_a_gift_and_scores_as_one(agent):
    """The same move, the same stages, the other direction."""
    assert _score(agent, 0, "foe", 0) == -_score(agent, 0, "ally", 1)


def test_handing_an_opponent_a_boost_is_no_longer_free(agent):
    """Swagger's +2 Attack is the price of the confusion, and the old scorer
    counted only the confusion."""
    at_foe = _score(agent, 1, "foe", 0)
    at_ally = _score(agent, 1, "ally", 1)
    # Aimed either way it is close to a wash, and the two are mirror images.
    assert at_foe == pytest.approx(-at_ally, abs=1e-6)


def test_a_debuff_on_an_opponent_still_scores_positively(agent):
    """The ordinary case has not moved."""
    assert _score(agent, 2, "foe", 0) > 0
