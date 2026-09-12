"""How often a species Mega Evolves once it is on the field, measured from replays.

Team Preview hides items, so an opponent's stone is unknowable -- but the rate
at which a species that reaches the field actually Megas is not. The number is
read off the engine's `|-mega|` line, which names the stone, and the stone
names the forme exactly: a species with two Megas is never confused between
them.
"""

from champions_ai.data.priors import build_mega_priors, load_mega_priors, save_mega_priors
from champions_ai.data.replay import Replay, ReplayMetadata
from champions_ai.dex import BaseStats, Dex, ItemInfo, SpeciesInfo, TypeChart

STATS = BaseStats(hp=80, attack=80, defense=80, special_attack=80, special_defense=80, speed=80)


def _species(species_id, name, base=None):
    return SpeciesInfo(
        species_id=species_id, name=name, types=("Normal",), base_stats=STATS,
        abilities=("Run Away",), base_species=base or name,
    )


DEX = Dex(
    species={
        s.species_id: s
        for s in (
            _species("drake", "Drake"),
            _species("drakemegax", "Drake-Mega-X", base="Drake"),
            _species("drakemegay", "Drake-Mega-Y", base="Drake"),
            _species("plain", "Plain"),
        )
    },
    moves={},
    types=("Normal",),
    type_chart=TypeChart(multipliers={"Normal": {"Normal": 1.0}}),
    items={
        "drakitex": ItemInfo(item_id="drakitex", name="Drakite X",
                             mega_stone="Drake", mega_forme="Drake-Mega-X"),
        "drakitey": ItemInfo(item_id="drakitey", name="Drakite Y",
                             mega_stone="Drake", mega_forme="Drake-Mega-Y"),
    },
)


def _replay(log, replay_id):
    return Replay(
        metadata=ReplayMetadata(
            replay_id=replay_id, format_id="gen9championsvgc2026regmc",
            players=("a", "b"), ratings=(1200, 1200), upload_time=0, rated=True,
        ),
        log=tuple(log),
    )


def _battle(n, *, mega=None, drake_on_field=True):
    log = ["|poke|p1|Drake, M|", "|poke|p1|Plain, M|"]
    if drake_on_field:
        log.append("|switch|p1a: Drake|Drake, M|100/100")
    log.append("|switch|p1b: Plain|Plain, M|100/100")
    if mega:
        log.append(f"|-mega|p1a: Drake|Drake|{mega}")
        log.append(f"|detailschange|p1a: Drake|Drake-Mega-{mega[-1]}, M")
    return _replay(log, str(n))


def test_the_rate_is_megas_over_times_on_the_field():
    replays = [_battle(n, mega="Drakite Y" if n < 45 else None) for n in range(60)]
    prior = build_mega_priors(replays, DEX, min_on_field=50)["drake"]
    assert (prior.on_field, prior.megas) == (60, 45)
    assert prior.rate == 45 / 60


def test_the_forme_comes_from_the_stone_not_the_name():
    replays = [_battle(n, mega="Drakite X" if n < 10 else "Drakite Y") for n in range(60)]
    assert build_mega_priors(replays, DEX, min_on_field=50)["drake"].forme == "Drake-Mega-Y"


def test_a_species_that_was_declared_but_never_took_the_field_is_not_counted():
    """Brought to Team Preview and left on the bench says nothing about whether
    it would have Mega Evolved."""
    replays = [_battle(n, mega="Drakite Y") for n in range(60)]
    replays += [_battle(100 + n, drake_on_field=False) for n in range(40)]
    assert build_mega_priors(replays, DEX, min_on_field=50)["drake"].on_field == 60


def test_too_few_appearances_earn_nothing():
    replays = [_battle(n, mega="Drakite Y") for n in range(10)]
    assert build_mega_priors(replays, DEX, min_on_field=50) == {}


def test_a_species_that_never_mega_evolves_has_no_prior():
    """Absent means 'score it as itself', which is what zero Megas says."""
    replays = [_battle(n) for n in range(60)]
    assert "drake" not in build_mega_priors(replays, DEX, min_on_field=50)
    assert "plain" not in build_mega_priors(replays, DEX, min_on_field=50)


def test_saving_keeps_the_counts(tmp_path):
    replays = [_battle(n, mega="Drakite Y" if n < 30 else None) for n in range(60)]
    path = tmp_path / "mega.json"
    save_mega_priors(build_mega_priors(replays, DEX, min_on_field=50), path)
    text = path.read_text(encoding="utf-8")
    assert '"on_field": 60' in text and '"megas": 30' in text
    assert load_mega_priors(path) == {"drake": ("Drake-Mega-Y", 0.5)}


def test_a_missing_file_is_not_an_error(tmp_path):
    assert load_mega_priors(tmp_path / "absent.json") == {}
