"""Collecting replays from the public API.

Every test here runs against a fake fetcher. The point is that the collector's
*behaviour toward someone else's server* is testable -- how many requests it
makes, and whether it repeats one it has already made -- rather than something
we only find out by running it against the real thing.
"""

import json

import pytest

from champions_ai.data.collect import (
    USAGE_NOTE,
    CollectionManifest,
    collect_replays,
    iter_listings,
    load_all,
    load_collection,
    load_or_fetch,
    manifest_paths,
)


def _log(p1_rating, p2_rating, p1="alice", p2="bob"):
    return "\n".join(
        [
            "|gametype|doubles",
            f"|player|p1|{p1}|1|{p1_rating}",
            f"|player|p2|{p2}|2|{p2_rating}",
            "|rated|",
            "|teamsize|p1|4",
            "|teamsize|p2|4",
            "|start",
            "|switch|p1a: Charizard|Charizard, L50, M|100/100",
            "|turn|1",
            "|move|p1a: Charizard|Heat Wave|p2a: X",
            "|turn|2",
        ]
    )


class FakeApi:
    """Stands in for the replay server, and counts what we asked it for."""

    def __init__(self, replays, pages=None):
        self.replays = replays
        self.pages = pages if pages is not None else [list(replays.values())]
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        if "search.json" in url:
            if "before=" not in url:
                return self.pages[0]
            before = int(url.split("before=")[1].split("&")[0])
            for page in self.pages[1:]:
                if page and int(page[0]["uploadtime"]) < before:
                    return page
            return []
        replay_id = url.rsplit("/", 1)[-1].removesuffix(".json")
        return self.replays[replay_id]

    @property
    def downloads(self):
        return [u for u in self.urls if "search.json" not in u]


def _replay_payload(replay_id, p1_rating, p2_rating, upload=1000, players=("alice", "bob")):
    return {
        "id": replay_id,
        "formatid": "gen9championsvgc2026regmb",
        "uploadtime": upload,
        "players": list(players),
        "log": _log(p1_rating, p2_rating, *players),
    }


FORMAT = "gen9championsvgc2026regmb"


@pytest.fixture
def api():
    return FakeApi(
        {
            "a": _replay_payload("a", 1600, 1650, upload=300),
            "b": _replay_payload("b", 1200, 1250, upload=200),
            "c": _replay_payload("c", 1550, 1580, upload=100),
        }
    )


# ------------------------------------------------------------------ filtering


def test_keeps_only_games_where_both_players_cleared_the_bar(tmp_path, api):
    collected = collect_replays(FORMAT, tmp_path, target=10, fetcher=api, min_rating=1500)
    assert [r.metadata.replay_id for r in collected.replays] == ["a", "c"]
    assert collected.manifest.rejected_rating == 1


def test_no_rating_filter_keeps_everything(tmp_path, api):
    collected = collect_replays(FORMAT, tmp_path, target=10, fetcher=api, min_rating=None)
    assert len(collected) == 3


def test_a_bot_is_skipped_without_being_downloaded(tmp_path):
    """Bot names are visible in the listing, so the request is never made.

    Training on bot games while calling the result expert play is a silent
    quality failure -- and skipping early also spares the server the request.
    """
    api = FakeApi(
        {
            "bot": _replay_payload("bot", 1700, 1700, players=("pcrlbot12d1", "bob")),
            "ok": _replay_payload("ok", 1600, 1600, upload=50),
        }
    )
    collected = collect_replays(FORMAT, tmp_path, target=10, fetcher=api, min_rating=1500)
    assert [r.metadata.replay_id for r in collected.replays] == ["ok"]
    assert collected.manifest.rejected_bot == 1
    assert not any("bot.json" in url for url in api.downloads)


def test_a_replay_from_another_format_is_rejected(tmp_path):
    payload = _replay_payload("x", 1600, 1600)
    payload["formatid"] = "gen9ou"
    api = FakeApi({"x": payload})
    collected = collect_replays(FORMAT, tmp_path, target=10, fetcher=api, min_rating=None)
    assert len(collected) == 0
    assert collected.manifest.rejected_format == 1


def test_stops_once_the_target_is_met(tmp_path, api):
    collected = collect_replays(FORMAT, tmp_path, target=1, fetcher=api, min_rating=1500)
    assert len(collected) == 1


# ------------------------------------------------------- traffic we generate


def test_a_cached_replay_is_never_requested_again(tmp_path, api):
    collect_replays(FORMAT, tmp_path, target=10, fetcher=api, min_rating=1500)
    first = len(api.downloads)
    assert first == 3, "every candidate is downloaded once to read its rating"

    collect_replays(FORMAT, tmp_path, target=10, fetcher=api, min_rating=1500)
    assert len(api.downloads) == first, "a second run must hit the cache, not the server"


def test_rejected_replays_are_cached_too(tmp_path, api):
    """So re-running with a looser filter costs nothing."""
    collect_replays(FORMAT, tmp_path, target=10, fetcher=api, min_rating=1500)
    assert (tmp_path / "b.json").exists(), "the rejected low-rated game is still on disk"

    before = len(api.downloads)
    widened = collect_replays(FORMAT, tmp_path, target=10, fetcher=api, min_rating=None)
    assert len(widened) == 3
    assert len(api.downloads) == before, "widening the filter must not refetch"


def test_load_or_fetch_reads_from_disk_when_present(tmp_path):
    api = FakeApi({"a": _replay_payload("a", 1600, 1600)})
    load_or_fetch("a", api, tmp_path)
    assert len(api.downloads) == 1
    load_or_fetch("a", api, tmp_path)
    assert len(api.downloads) == 1


def _full_page(prefix, start_time):
    """51 entries -- the API's signal that another page exists."""
    return [
        {"id": f"{prefix}{i}", "uploadtime": start_time - i, "players": ["x", "y"]}
        for i in range(51)
    ]


def test_a_short_page_means_there_are_no_more(tmp_path):
    """Fewer than 51 results is the documented end of the listing."""
    api = FakeApi({}, pages=[[{"id": "a", "uploadtime": 300, "players": ["x", "y"]}]])
    assert [entry["id"] for entry in iter_listings(FORMAT, api)] == ["a"]
    assert len(api.urls) == 1, "a short page must not trigger another request"


def test_pagination_walks_backwards_through_full_pages(tmp_path):
    api = FakeApi({}, pages=[_full_page("a", 1000), _full_page("b", 900), []])
    listings = list(iter_listings(FORMAT, api))
    assert len(listings) == 102
    assert listings[0]["id"] == "a0"
    assert listings[51]["id"] == "b0"
    # The second request must carry the oldest timestamp from the first page.
    assert "before=950" in api.urls[1]


def test_pagination_does_not_loop_when_the_cursor_stops_moving(tmp_path):
    """A server that keeps returning the same full page must not spin forever.

    The guard is the cursor: if a page's oldest entry is not older than the
    `before` we asked with, the listing is not advancing and there is nothing
    further to read. Without it this walks to `max_pages` hammering the server
    with identical requests.
    """
    page = _full_page("a", 1000)
    calls = []

    def always_the_same(url):
        calls.append(url)
        return page

    listings = list(iter_listings(FORMAT, always_the_same, max_pages=50))
    assert len(listings) == 51, "the repeated page must be recognised, not re-yielded"
    assert len(calls) == 2, f"should stop after seeing the cursor stall, made {len(calls)}"


def test_pagination_respects_its_page_cap(tmp_path):
    api = FakeApi({}, pages=[_full_page(chr(97 + i), 10_000 - i * 100) for i in range(10)])
    list(iter_listings(FORMAT, api, max_pages=3))
    assert len(api.urls) == 3


# ----------------------------------------------------------------- provenance


def test_the_manifest_records_where_the_data_came_from(tmp_path, api):
    collected = collect_replays(FORMAT, tmp_path, target=10, fetcher=api, min_rating=1500)
    manifest = collected.manifest
    assert manifest.format_id == FORMAT
    assert manifest.collected_at
    assert manifest.min_rating == 1500
    assert manifest.kept == 2
    assert manifest.considered == 3


def test_the_manifest_carries_the_no_redistribution_constraint(tmp_path, api):
    """No licence covers the replay logs, so the constraint travels with them."""
    collected = collect_replays(FORMAT, tmp_path, target=10, fetcher=api, min_rating=1500)
    assert collected.manifest.usage_note == USAGE_NOTE
    assert "not be redistributed" in collected.manifest.usage_note


def test_a_collection_round_trips_through_disk(tmp_path, api):
    collected = collect_replays(FORMAT, tmp_path, target=10, fetcher=api, min_rating=1500)
    manifest_path = tmp_path / "manifest.json"
    collected.manifest.save(manifest_path)

    reloaded = load_collection(tmp_path, manifest_path)
    assert reloaded.manifest == collected.manifest
    assert [r.metadata.replay_id for r in reloaded.replays] == ["a", "c"]


def test_a_saved_manifest_is_readable_json(tmp_path, api):
    collected = collect_replays(FORMAT, tmp_path, target=10, fetcher=api, min_rating=1500)
    path = tmp_path / "manifest.json"
    collected.manifest.save(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["replay_ids"] == ["a", "c"]
    assert payload["source"].startswith("https://")


def test_reloading_a_manifest_needs_no_network(tmp_path, api):
    collected = collect_replays(FORMAT, tmp_path, target=10, fetcher=api, min_rating=1500)
    path = tmp_path / "manifest.json"
    collected.manifest.save(path)
    assert CollectionManifest.load(path).replay_ids == ("a", "c")


# ------------------------------------------------- provenance across many runs


def test_each_run_gets_its_own_manifest(tmp_path, api):
    """Overwriting one run's manifest with the next loses how the earlier batch
    was selected, which is the provenance the dataset is supposed to keep."""
    collected = collect_replays(FORMAT, tmp_path, target=10, fetcher=api, min_rating=1500)
    path = collected.save(tmp_path)
    assert path.name.startswith("manifest-")
    assert path.exists()


def test_two_runs_leave_two_manifests(tmp_path, api):
    first = collect_replays(FORMAT, tmp_path, target=1, fetcher=api, min_rating=1500)
    first.manifest.save(tmp_path / "manifest-2026-01-01T00-00-00.json")
    second = collect_replays(FORMAT, tmp_path, target=10, fetcher=api, min_rating=None)
    second.manifest.save(tmp_path / "manifest-2026-02-02T00-00-00.json")
    assert len(manifest_paths(tmp_path)) == 2


def test_load_all_merges_runs_without_duplicating(tmp_path, api):
    strict = collect_replays(FORMAT, tmp_path, target=10, fetcher=api, min_rating=1500)
    strict.manifest.save(tmp_path / "manifest-2026-01-01T00-00-00.json")
    loose = collect_replays(FORMAT, tmp_path, target=10, fetcher=api, min_rating=None)
    loose.manifest.save(tmp_path / "manifest-2026-02-02T00-00-00.json")

    merged = load_all(tmp_path)
    ids = [r.metadata.replay_id for r in merged.replays]
    assert sorted(ids) == ["a", "b", "c"], "the union, each replay once"
    assert len(ids) == len(set(ids))


def test_the_merged_manifest_reports_the_loosest_filter(tmp_path, api):
    """A set assembled from several passes is only as selective as its least
    selective part, so it must not claim the stricter bar."""
    strict = collect_replays(FORMAT, tmp_path, target=10, fetcher=api, min_rating=1500)
    strict.manifest.save(tmp_path / "manifest-2026-01-01T00-00-00.json")
    loose = collect_replays(FORMAT, tmp_path, target=10, fetcher=api, min_rating=None)
    loose.manifest.save(tmp_path / "manifest-2026-02-02T00-00-00.json")

    merged = load_all(tmp_path).manifest
    assert merged.min_rating is None
    assert merged.considered == strict.manifest.considered + loose.manifest.considered
    assert "not be redistributed" in merged.usage_note


def test_load_all_needs_at_least_one_manifest(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_all(tmp_path)


def test_load_all_skips_a_replay_whose_file_is_gone(tmp_path, api):
    """A manifest naming a file that is not there must not break the load."""
    collected = collect_replays(FORMAT, tmp_path, target=10, fetcher=api, min_rating=1500)
    collected.manifest.save(tmp_path / "manifest-2026-01-01T00-00-00.json")
    (tmp_path / "a.json").unlink()
    assert [r.metadata.replay_id for r in load_all(tmp_path).replays] == ["c"]
