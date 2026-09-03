"""The board renderer, which is the only part of the CLI that is a pure function.

Two things are worth pinning. That it shows what a player needs -- health,
status, stages, who is actually out -- and that it is **incapable** of showing
what they are not entitled to see. The second is the reason this reads from
`Observation` and nothing else: the opponent's bench is a count there, not a
list, so a renderer that only ever touches `Observation` cannot leak it.
"""

from champions_ai.cli.board import render_board
from champions_ai.domain import (
    REGULATION_M_B,
    BattlePokemon,
    Boosts,
    Observation,
    ObservedPokemon,
    ObservedSide,
    PokemonSet,
    Side,
    StatSpread,
)


def _mine(species: str, *, hp: int = 100, max_hp: int = 100, **kwargs) -> BattlePokemon:
    return BattlePokemon(
        pokemon_set=PokemonSet(
            species=species,
            level=50,
            ability="blaze",
            moves=("tackle", "protect"),
            stats=StatSpread(hp=32, speed=32),
        ),
        current_hp=hp,
        max_hp=max_hp,
        **kwargs,
    )


def _observation(*, own=None, opponent=None, **kwargs) -> Observation:
    return Observation(
        regulation=REGULATION_M_B,
        turn=kwargs.pop("turn", 3),
        player=0,
        own_side=own
        or Side(team=(_mine("Charizard"), _mine("Garchomp")), active_slots=(0, 1)),
        opponent_side=opponent or ObservedSide(revealed=(), active_slots=(None, None)),
        **kwargs,
    )


def test_the_active_pokemon_are_marked_and_the_benched_are_not():
    own = Side(
        team=(_mine("Charizard"), _mine("Garchomp"), _mine("Incineroar")),
        active_slots=(0, 1),
    )
    board = render_board(_observation(own=own))

    def line_for(species: str) -> str:
        return next(line for line in board.splitlines() if species in line)

    assert line_for("Charizard").startswith(" >")
    assert line_for("Garchomp").startswith(" >")
    assert not line_for("Incineroar").startswith(" >")


def test_health_status_and_stages_are_all_shown():
    own = Side(
        team=(
            _mine("Charizard", hp=45, max_hp=153, status="brn",
                  boosts=Boosts(attack=2, speed=-1)),
        ),
        active_slots=(0,),
    )
    board = render_board(_observation(own=own))

    assert "45/153" in board
    assert "BRN" in board
    assert "+2 Atk" in board
    assert "-1 Spe" in board


def test_a_fainted_pokemon_says_so_instead_of_showing_a_bar():
    own = Side(team=(_mine("Charizard", hp=0),), active_slots=(None,))
    board = render_board(_observation(own=own))

    assert "fainted" in board
    assert "0/100" not in board


def test_the_opponent_bench_is_a_count_and_never_a_list():
    """The masking rule, enforced where a player can see it.

    `ObservedSide` carries `unrevealed_count` and no identities, so the only
    honest thing to print is the number. A renderer that reached for the real
    team would be a hidden-information leak in the one place a user would
    believe it.
    """
    opponent = ObservedSide(
        revealed=(ObservedPokemon(species="Incineroar", level=50, hp_percent=80, fainted=False),),
        active_slots=(0, None),
        unrevealed_count=3,
    )
    board = render_board(_observation(opponent=opponent))

    assert "Incineroar" in board
    assert "3 not yet seen" in board


def test_opponent_health_is_a_percentage_and_ours_is_exact():
    """The asymmetry is the point: we know our own HP and only ever see theirs."""
    own = Side(team=(_mine("Charizard", hp=77, max_hp=153),), active_slots=(0,))
    opponent = ObservedSide(
        revealed=(ObservedPokemon(species="Garchomp", level=50, hp_percent=53, fainted=False),),
        active_slots=(0, None),
    )
    board = render_board(_observation(own=own, opponent=opponent))

    assert "77/153" in board
    assert "53%" in board
    assert "/153" in board and "Garchomp" in board
    # Nothing anywhere should print an exact HP for the opponent.
    garchomp_line = next(line for line in board.splitlines() if "Garchomp" in line)
    assert "/" not in garchomp_line


def test_weather_and_field_effects_reach_the_header():
    board = render_board(_observation(weather="snow", field_conditions={"trickroom": 5}))

    assert "snow" in board
    assert "Trick Room" in board


def test_tailwind_and_screens_are_named_rather_than_dumped():
    own = Side(
        team=(_mine("Charizard"),),
        active_slots=(0,),
        side_conditions={"tailwind": 3, "reflect": 5},
    )
    board = render_board(_observation(own=own))

    assert "Tailwind" in board
    assert "Screens" in board


def test_a_pokemon_at_a_sliver_of_health_still_shows_a_block():
    """Rounding a survivor down to an empty bar reads as fainted, which is worse
    than imprecise -- it is the one distinction the bar exists to make."""
    own = Side(team=(_mine("Charizard", hp=1, max_hp=200),), active_slots=(0,))
    board = render_board(_observation(own=own))

    charizard = next(line for line in board.splitlines() if "Charizard" in line)
    assert "#" in charizard
