"""The Team Preview screen: reading a pick, and rendering the grid.

`parse_picks` is the part worth testing hardest. It converts what a player
types, which is 1-based because that is what the screen shows, into the 0-based
indices the domain uses. An off-by-one here would silently bring a different
Pokemon than the one asked for, and nothing downstream could notice.
"""

from champions_ai.cli.preview import parse_picks, render_preview, species_name
from champions_ai.domain import (
    REGULATION_M_B,
    PokemonSet,
    RevealedPokemon,
    StatSpread,
    Team,
    TeamPreview,
)

SIX = ("Blaziken", "Basculegion", "Sneasler", "Mawile", "Farigiraf", "Torkoal")
THEIRS = ("Kingambit", "Charizard", "Aerodactyl", "Farigiraf", "Garchomp", "Sylveon")


class _Dex:
    class _Species:
        def __init__(self, name):
            self.name = name

    def get_species(self, species):
        if species == "unknownmon":
            raise KeyError(species)
        return self._Species(species.title())


def _preview() -> TeamPreview:
    return TeamPreview(
        regulation=REGULATION_M_B,
        own_team=Team(
            pokemon=tuple(
                PokemonSet(
                    species=name,
                    level=50,
                    ability="blaze",
                    moves=("tackle",),
                    stats=StatSpread(hp=32, speed=32),
                )
                for name in SIX
            )
        ),
        opponent_team=tuple(RevealedPokemon(species=name, level=50) for name in THEIRS),
    )


def _table() -> list[list[float]]:
    return [[(row - col) / 10 for col in range(6)] for row in range(6)]


# ---------------------------------------------------------------- parse_picks


def test_a_pick_is_read_as_one_based_and_returned_zero_based():
    """What the screen numbers 1 must be team index 0, or the wrong Pokemon comes."""
    assert parse_picks("1 2 3 4", 6, 4) == (0, 1, 2, 3)
    assert parse_picks("6 5 4 3", 6, 4) == (5, 4, 3, 2)


def test_the_order_typed_is_the_order_kept():
    """The first two lead, so "4 2 1 6" must not come back sorted."""
    assert parse_picks("4 2 1 6", 6, 4) == (3, 1, 0, 5)


def test_commas_are_accepted_because_people_type_them():
    assert parse_picks("4,2,1,6", 6, 4) == (3, 1, 0, 5)
    assert parse_picks("4, 2, 1, 6", 6, 4) == (3, 1, 0, 5)


def test_a_repeated_pokemon_is_refused():
    assert parse_picks("1 1 2 3", 6, 4) is None


def test_the_wrong_count_is_refused():
    assert parse_picks("1 2 3", 6, 4) is None
    assert parse_picks("1 2 3 4 5", 6, 4) is None
    assert parse_picks("", 6, 4) is None


def test_out_of_range_is_refused_at_both_ends():
    assert parse_picks("0 1 2 3", 6, 4) is None, "0 is not on the screen"
    assert parse_picks("1 2 3 7", 6, 4) is None


def test_anything_that_is_not_a_number_is_refused():
    assert parse_picks("a b c d", 6, 4) is None
    assert parse_picks("1 2 3 four", 6, 4) is None
    assert parse_picks("-1 2 3 4", 6, 4) is None


# -------------------------------------------------------------- species_name


def test_species_names_come_from_the_dex_and_fall_back_intact():
    assert species_name(_Dex(), "basculegion") == "Basculegion"
    assert species_name(_Dex(), "unknownmon") == "unknownmon"


# ------------------------------------------------------------ render_preview


def test_the_screen_shows_both_rosters_and_every_matchup():
    screen = render_preview(_preview(), _table(), (0, 1, 2, 3), (), _Dex())

    for name in SIX + THEIRS:
        assert name in screen


def test_the_chosen_four_are_marked_and_the_rest_are_not():
    screen = render_preview(_preview(), _table(), (1, 2, 4, 5), (), _Dex())
    rows = {
        name: line
        for name in SIX
        for line in screen.splitlines()
        if line.lstrip().startswith(("*", str(SIX.index(name) + 1))) and name in line
    }
    assert rows["Basculegion"].strip().startswith("*")
    assert rows["Torkoal"].strip().startswith("*")
    assert not rows["Blaziken"].strip().startswith("*")
    assert not rows["Mawile"].strip().startswith("*")


def test_matchups_are_scaled_so_they_do_not_all_round_to_zero():
    """`matchup().net` runs -1 to +1, where two thirds of a table printed at
    whole-number precision reads as 0 and the grid says nothing."""
    table = [[0.0] * 6 for _ in range(6)]
    table[0][0] = 0.42
    table[1][1] = -0.37

    screen = render_preview(_preview(), table, (0, 1, 2, 3), (), _Dex())

    assert "42" in screen
    assert "-37" in screen


def test_the_lead_order_caveat_is_on_the_screen():
    """It was measured at 48.4% against a 50% baseline. Showing an order
    without saying that would be the screen's easiest way to mislead."""
    screen = render_preview(_preview(), _table(), (0, 1, 2, 3), (), _Dex())

    assert "48.4%" in screen
    assert "coverage" in screen


def test_rendering_survives_a_reason_list_that_does_not_line_up():
    """`explain_team_preview` is a separate call and could return fewer."""
    screen = render_preview(_preview(), _table(), (0, 1, 2, 3), (("Blaziken: x", 0.0),), _Dex())

    assert "Blaziken" in screen
