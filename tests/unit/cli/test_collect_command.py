"""The collection command, and the one decision it encodes.

Named `test_collect_command` rather than `test_collect`: pytest imports test
modules by basename when there are no `__init__.py` files, and this package
has none, so a second `test_collect.py` collides with the one under
`tests/unit/data` and stops the whole suite from being collected.

`collect_replays` and its throttling, caching and filtering are tested in
`tests/unit/data/test_collect.py`. What is here is the command around it, and
specifically that it takes a **format id** rather than a `Regulation`.

That is not a convenience. A `Regulation` in this project is a claim to know a
format's rules and dex; a format id is a string the replay server indexes by.
Collecting for a regulation that is not yet simulatable is the only preparation
available in the gap between a format appearing upstream and its mod being
released -- and it has to be possible without inventing a `Regulation` for it.
"""

from pathlib import Path

import champions_ai.cli.collect as module
from champions_ai.data.collect import Collection, CollectionManifest


def _manifest(format_id: str, kept: int, considered: int, min_rating) -> CollectionManifest:
    return CollectionManifest(
        schema_version=1,
        format_id=format_id,
        source="https://replay.pokemonshowdown.com",
        collected_at="2026-09-10T00-00-00+00-00",
        git_commit=None,
        min_rating=min_rating,
        exclude_bots=True,
        usage_note="local research use only",
        replay_ids=tuple(f"{format_id}-{i}" for i in range(kept)),
        considered=considered,
    )


def _record(calls: list):
    def fake(format_id, cache_dir, **kwargs):
        calls.append({"format_id": format_id, "cache_dir": cache_dir, **kwargs})
        return Collection(
            manifest=_manifest(format_id, kwargs["target"], kwargs["target"], kwargs["min_rating"])
        )

    return fake


def test_it_collects_for_a_format_it_cannot_simulate(monkeypatch, tmp_path, capsys):
    """The case it exists for: a regulation upstream but not installable.

    Nothing about the format is asserted here -- not its dex, not its rules --
    because nothing is known about them yet. It is a string passed to a search.
    """
    calls: list = []
    monkeypatch.setattr(module, "collect_replays", _record(calls))

    assert module.collect(
        format_id="gen9championsvgc2026regmc", corpus_path=tmp_path, target=10
    ) == 0
    assert calls[0]["format_id"] == "gen9championsvgc2026regmc"
    assert "gen9championsvgc2026regmc" in capsys.readouterr().out


def test_the_rating_bar_is_reported_because_it_decides_what_the_corpus_is_for(
    monkeypatch, tmp_path, capsys
):
    """A corpus with no rating filter is a different dataset from one at 1500+,
    and which it is has to be visible without opening the manifest."""
    monkeypatch.setattr(module, "collect_replays", _record([]))

    module.collect(format_id="f", corpus_path=tmp_path, target=1, min_rating=None)
    assert "any rating" in capsys.readouterr().out

    module.collect(format_id="f", corpus_path=tmp_path, target=1, min_rating=1500)
    assert "1500+" in capsys.readouterr().out


def test_the_manifest_is_written_next_to_the_replays(monkeypatch, tmp_path):
    """A directory of JSON files with no record of the filter that selected
    them is not a dataset, and `AGENTS.md` says so."""
    monkeypatch.setattr(module, "collect_replays", _record([]))
    module.collect(format_id="f", corpus_path=tmp_path, target=3)
    assert list(tmp_path.glob("manifest-*.json"))


def test_a_short_run_says_the_listing_ran_out(monkeypatch, tmp_path, capsys):
    """For a format that has only just appeared this is the expected outcome,
    not a failure -- but a short corpus noticed weeks later is a bad surprise."""
    def fake(format_id, cache_dir, **kwargs):
        return Collection(manifest=_manifest(format_id, 4, 60, kwargs["min_rating"]))

    monkeypatch.setattr(module, "collect_replays", fake)
    module.collect(format_id="f", corpus_path=tmp_path, target=500)
    assert "listing ran out" in capsys.readouterr().out


def test_the_corpus_directory_is_created_if_it_is_not_there(monkeypatch, tmp_path):
    monkeypatch.setattr(module, "collect_replays", _record([]))
    fresh = tmp_path / "new" / "place"
    module.collect(format_id="f", corpus_path=fresh, target=1)
    assert fresh.is_dir()


def test_the_default_corpus_is_the_one_everything_else_reads(monkeypatch):
    """`review` and `harvest` read `data/replays`. A second default here would
    collect into a directory nothing looks at."""
    from champions_ai.cli.review import DEFAULT_CORPUS as REVIEW_CORPUS

    assert module.DEFAULT_CORPUS == REVIEW_CORPUS == Path("data/replays")
