from champions_ai.domain import PokemonSet, RevealedPokemon


def _set() -> PokemonSet:
    return PokemonSet(
        species="garchomp",
        level=50,
        ability="roughskin",
        moves=("earthquake", "protect"),
        item="sitrusberry",
        nature="jolly",
        tera_type="steel",
    )


def test_default_masking_hides_everything_but_species_and_level():
    revealed = RevealedPokemon.from_set(_set())
    assert revealed.species == "garchomp"
    assert revealed.level == 50
    assert revealed.ability is None
    assert revealed.item is None
    assert revealed.moves is None
    assert revealed.nature is None
    assert revealed.tera_type is None


def test_sheets_open_reveals_non_stat_fields():
    revealed = RevealedPokemon.from_set(_set(), sheets_open=True)
    assert revealed.ability == "roughskin"
    assert revealed.item == "sitrusberry"
    assert revealed.moves == ("earthquake", "protect")
    assert revealed.nature == "jolly"
    assert revealed.tera_type == "steel"


def test_revealed_pokemon_has_no_stats_field():
    assert "stats" not in RevealedPokemon.model_fields
