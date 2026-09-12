"""Which field will their six put up, measured from the corpus.

Deliberately not routed through an ability table. The log states the whole
chain in one line --

    |-weather|Sunny Day|[from] ability: Drought|[of] p2a: Torkoal

-- so "Torkoal means sun" is observable directly and nothing here needs to know
that Drought exists. That also makes the number the one actually wanted:
**P(this field is up | this species was previewed)**, which folds in the two
things an ability table cannot know -- that a previewed Pokemon is only brought
four times in six, and that a setter can be beaten to it or faint first.

The forme test is the one that matters. The `[of]` ident carries a *nickname*,
and for a forme it carries the base name: `[of] p1b: Indeedee` for a Pokemon the
roster calls `indeedeef`. Matching the ident against the roster directly dropped
every Indeedee-F -- 22% of the field and the format's main Psychic Terrain
setter. Same forme-versus-ident trap that cost this project a Mega exclusion in
0046.
"""

from champions_ai.data.priors import (
    build_field_priors,
    load_field_priors,
    save_field_priors,
)
from champions_ai.data.replay import Replay, ReplayMetadata


def _replay(log, replay_id="x"):
    return Replay(
        metadata=ReplayMetadata(
            replay_id=replay_id, format_id="gen9championsvgc2026regmc",
            players=("a", "b"), ratings=(1200, 1200), upload_time=0, rated=True,
        ),
        log=tuple(log),
    )


def _rain(set_it=True, replay_id="x"):
    log = [
        "|poke|p1|Pelipper, F|",
        "|poke|p1|Incineroar, M|",
        "|poke|p2|Rillaboom, M|",
        "|poke|p2|Incineroar, M|",
        "|switch|p1a: Pelipper|Pelipper, F|100/100",
    ]
    if set_it:
        log.append("|-weather|RainDance|[from] ability: Drizzle|[of] p1a: Pelipper")
    return _replay(log, replay_id)


def test_a_species_that_always_sets_its_weather_earns_a_prior():
    priors = build_field_priors(
        [_rain(replay_id=str(n)) for n in range(60)], min_previews=60
    )
    assert priors["pelipper"].effect == "raindance"
    assert priors["pelipper"].kind == "weather"
    assert priors["pelipper"].probability == 1.0


def test_the_probability_is_of_previews_not_of_appearances():
    """The point of the measure: a Pelipper that is previewed and left at home
    is a Pelipper that did not bring rain, and must count against it."""
    replays = [_rain(set_it=n < 30, replay_id=str(n)) for n in range(60)]
    assert build_field_priors(replays, min_previews=60)["pelipper"].probability == 0.5


def test_a_species_previewed_too_few_times_earns_nothing():
    assert build_field_priors([_rain()], min_previews=60) == {}


def test_a_forme_is_resolved_through_the_switch_line_not_the_ident():
    """`[of] p1b: Indeedee` for a roster that says `indeedeef`. Matching the
    ident against the roster dropped every one of them."""
    log = [
        "|poke|p1|Indeedee-F, F|",
        "|poke|p1|Incineroar, M|",
        "|poke|p2|Rillaboom, M|",
        "|poke|p2|Incineroar, M|",
        "|switch|p1b: Indeedee|Indeedee-F, F|100/100",
        "|-fieldstart|move: Psychic Terrain|[from] ability: Psychic Surge|[of] p1b: Indeedee",
    ]
    priors = build_field_priors([_replay(log, str(n)) for n in range(60)], min_previews=60)
    assert priors["indeedeef"].effect == "psychicterrain"
    assert priors["indeedeef"].kind == "terrain"


def test_a_coincidence_below_the_floor_earns_nothing():
    replays = [_rain(set_it=n < 5, replay_id=str(n)) for n in range(60)]
    assert build_field_priors(replays, min_previews=60, min_probability=0.25) == {}


def test_saving_keeps_the_counts_so_the_probability_can_be_argued_with(tmp_path):
    priors = build_field_priors(
        [_rain(replay_id=str(n)) for n in range(60)], min_previews=60
    )
    path = tmp_path / "field.json"
    save_field_priors(priors, path)

    assert "60" in path.read_text(encoding="utf-8")
    assert load_field_priors(path) == {"pelipper": ("raindance", "weather", 1.0)}


def test_a_missing_file_is_not_an_error(tmp_path):
    """The prior is opt-in; an agent without the file behaves as it did before
    there was one."""
    assert load_field_priors(tmp_path / "absent.json") == {}
