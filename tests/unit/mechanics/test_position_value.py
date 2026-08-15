"""Position evaluation: scoring a board rather than an action."""

from champions_ai.domain import (
    REGULATION_M_B,
    BattlePokemon,
    BattleState,
    Observation,
    PokemonSet,
    Side,
)
from champions_ai.mechanics import evaluate_position


def _mon(species: str, hp: int = 150, max_hp: int = 150) -> BattlePokemon:
    return BattlePokemon(
        pokemon_set=PokemonSet(species=species, level=50, ability="a", moves=("tackle",)),
        current_hp=hp,
        max_hp=max_hp,
        has_been_active=True,
    )


def _observation(own_hps=(150, 150, 150, 150), foe_hps=(150, 150, 150, 150),
                 own_slots=(0, 1), foe_slots=(0, 1)) -> Observation:
    own = Side(
        team=tuple(_mon(f"own{i}", hp=hp) for i, hp in enumerate(own_hps)),
        active_slots=own_slots,
    )
    foe = Side(
        team=tuple(_mon(f"foe{i}", hp=hp) for i, hp in enumerate(foe_hps)),
        active_slots=foe_slots,
    )
    state = BattleState(regulation=REGULATION_M_B, turn=3, sides=(own, foe))
    return Observation.from_battle_state(state, player=0)


def test_an_even_board_has_no_advantage():
    assert evaluate_position(_observation()).advantage == 0.0


def test_being_up_a_pokemon_is_an_advantage():
    ahead = evaluate_position(_observation(foe_hps=(0, 150, 150, 150)))
    assert ahead.advantage > 0


def test_a_whole_pokemon_is_worth_more_than_any_amount_of_chip_damage():
    """Losing one outright should hurt more than every survivor being hurt."""
    lost_one = evaluate_position(_observation(own_hps=(0, 150, 150, 150)))
    all_hurt = evaluate_position(_observation(own_hps=(80, 80, 80, 80)))
    assert lost_one.advantage < all_hurt.advantage


def test_damage_registers_even_without_a_knockout():
    healthy = evaluate_position(_observation())
    chipped = evaluate_position(_observation(own_hps=(75, 150, 150, 150)))
    assert chipped.advantage < healthy.advantage


def test_an_empty_slot_is_worse_than_a_full_one():
    filled = evaluate_position(_observation(own_slots=(0, 1)))
    empty = evaluate_position(_observation(own_slots=(0, None)))
    assert empty.advantage < filled.advantage


def test_unrevealed_opponents_still_count_as_alive():
    """A Pokemon they have not sent out is a threat, not an absence."""
    observation = _observation()
    assert observation.opponent_side.unrevealed_count == 0

    value = evaluate_position(observation)
    assert value.opponent_score > 0


def test_advantage_is_symmetric_between_the_players():
    observation = _observation(foe_hps=(0, 150, 150, 150))
    from_p0 = evaluate_position(observation)
    assert from_p0.own_score > from_p0.opponent_score
