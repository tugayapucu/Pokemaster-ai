"""Collect human replays from Showdown's public replay API.

Programmatic access is the documented, intended path. `WEB-API.md` in the
Showdown client repository states that "most PS APIs that you would want to
access programmatically are available by adding `.json` to the URL", documents
`search.json` with pagination by `before=<uploadtime>`, and serves everything
with `Access-Control-Allow-Origin: *`. Its one "don't scrape it" remark is
about the *HTML replay page*, and steers readers toward this API rather than
away from it. `replay.pokemonshowdown.com` publishes no robots.txt.

Two constraints follow from what the terms do **not** say, and both are
enforced here rather than left to memory:

- **No licence covers the replay data.** MIT covers Showdown's server code;
  battle logs are not licensed for redistribution and the privacy policy does
  not mention them. So this collects for local research use and the manifest
  records that the corpus must not be republished. Derived statistics and
  model weights are a different question from the logs themselves.
- **No rate limit is published**, which makes throttling our courtesy
  obligation rather than their permission. Every request goes through a
  deliberate delay, and anything already on disk is never fetched again.
"""

import json
import time
import urllib.request
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from champions_ai.data.replay import Replay, ReplayMetadata, looks_like_bot
from champions_ai.data.trajectory import SCHEMA_VERSION, git_commit, utc_now

DEFAULT_SOURCE = "https://replay.pokemonshowdown.com"
USER_AGENT = "champions-ai research prototype (non-commercial, no redistribution)"

USAGE_NOTE = (
    "Collected from Showdown's documented public replay API for local research "
    "use. No licence covers the replay logs themselves, so this corpus must not "
    "be redistributed or republished."
)

# A callable taking a URL and returning decoded JSON. Injectable so tests never
# touch the network.
Fetcher = Callable[[str], object]


class ThrottledFetcher:
    """Fetches JSON, never faster than `min_interval` seconds apart.

    The interval is not a tuning knob to be minimised: no rate limit is
    published, so this is the whole of our politeness budget.
    """

    def __init__(self, *, min_interval: float = 1.0, timeout: float = 30.0) -> None:
        self.min_interval = min_interval
        self.timeout = timeout
        self._last = 0.0
        self.requests = 0

    def __call__(self, url: str) -> object:
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self._last = time.monotonic()
        self.requests += 1
        return payload


@dataclass(frozen=True)
class CollectionManifest:
    """Provenance for one collected set, as AGENTS.md requires of any dataset.

    Kept next to the replays rather than in a commit message: a directory of
    JSON files with no record of where it came from, when, or under what filter
    is not a dataset, and should not be used as a benchmark.
    """

    schema_version: int
    format_id: str
    source: str
    collected_at: str
    git_commit: str | None
    min_rating: int | None
    exclude_bots: bool
    usage_note: str
    replay_ids: tuple[str, ...] = ()
    considered: int = 0
    rejected_bot: int = 0
    rejected_unrated: int = 0
    rejected_rating: int = 0
    rejected_format: int = 0

    @property
    def kept(self) -> int:
        return len(self.replay_ids)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {**self.__dict__, "replay_ids": list(self.replay_ids)}
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "CollectionManifest":
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["replay_ids"] = tuple(payload["replay_ids"])
        return cls(**payload)


@dataclass
class Collection:
    """What a collection run produced."""

    manifest: CollectionManifest
    replays: list[Replay] = field(default_factory=list, repr=False)

    def __len__(self) -> int:
        return len(self.replays)


def search_page(
    format_id: str,
    fetcher: Fetcher,
    *,
    before: int | None = None,
    source: str = DEFAULT_SOURCE,
) -> list[dict]:
    """One page of the replay listing, newest first.

    Pages hold up to 51 entries; a 51st means at least one more page exists.
    """
    url = f"{source}/search.json?format={format_id}"
    if before is not None:
        url = f"{url}&before={before}"
    found = fetcher(url)
    return list(found) if isinstance(found, list) else []


def iter_listings(
    format_id: str,
    fetcher: Fetcher,
    *,
    source: str = DEFAULT_SOURCE,
    max_pages: int = 20,
) -> Iterator[dict]:
    """Walk the listing backwards in time, page by page.

    Paginates on the last entry's `uploadtime` as the API documents. Stops when
    a page does not fill, when the cursor stops moving (which would otherwise
    loop forever on a boundary), or at `max_pages`.
    """
    before: int | None = None
    seen: set[str] = set()

    for _ in range(max_pages):
        page = search_page(format_id, fetcher, before=before, source=source)
        if not page:
            return

        for entry in page:
            replay_id = str(entry.get("id", ""))
            if replay_id and replay_id not in seen:
                seen.add(replay_id)
                yield entry

        oldest = page[-1].get("uploadtime")
        if oldest is None or (before is not None and int(oldest) >= before):
            return
        before = int(oldest)
        if len(page) < 51:
            return


def load_or_fetch(
    replay_id: str,
    fetcher: Fetcher,
    cache_dir: Path,
    *,
    source: str = DEFAULT_SOURCE,
) -> Replay:
    """Read a replay from the cache, downloading it only if it is absent.

    Caching rejected replays too is deliberate: re-running a collection with a
    different rating filter should cost nothing, and repeating a request for a
    game we already judged is exactly the traffic to avoid.
    """
    path = cache_dir / f"{replay_id}.json"
    if path.exists():
        return Replay.load(path)

    payload = fetcher(f"{source}/{replay_id}.json")
    if not isinstance(payload, dict):
        raise ValueError(
            f"replay {replay_id} returned {type(payload).__name__}, expected an object"
        )
    cache_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return Replay.from_payload(payload)


def _acceptable(
    metadata: ReplayMetadata, format_id: str, min_rating: int | None
) -> str | None:
    """Why this replay was rejected, or None if it is usable."""
    if metadata.format_id and metadata.format_id != format_id:
        return "format"
    if min_rating is None:
        return None
    if metadata.minimum_rating is None:
        return "unrated"
    if not metadata.is_high_level(min_rating):
        return "rating"
    return None


def collect_replays(
    format_id: str,
    cache_dir: Path,
    *,
    target: int,
    fetcher: Fetcher | None = None,
    min_rating: int | None = 1500,
    exclude_bots: bool = True,
    source: str = DEFAULT_SOURCE,
    max_pages: int = 20,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> Collection:
    """Collect up to `target` usable replays, newest first.

    Bot accounts are filtered from the *listing*, before any download, because
    their names are visible there -- training on bot games while calling the
    result expert play is a silent quality failure, and skipping them early
    also spares the server the request.

    Ratings are not in the listing, so a rating filter costs one download per
    candidate whether or not it is kept. Those downloads are cached, so the
    cost is paid once.
    """
    fetch = fetcher if fetcher is not None else ThrottledFetcher()
    kept: list[Replay] = []
    counts = {"considered": 0, "bot": 0, "unrated": 0, "rating": 0, "format": 0}

    for entry in iter_listings(format_id, fetch, source=source, max_pages=max_pages):
        if len(kept) >= target:
            break
        counts["considered"] += 1

        players = [str(name) for name in (entry.get("players") or [])]
        if exclude_bots and any(looks_like_bot(name) for name in players):
            counts["bot"] += 1
            continue

        replay = load_or_fetch(str(entry["id"]), fetch, cache_dir, source=source)
        if exclude_bots and any(looks_like_bot(name) for name in replay.metadata.players):
            counts["bot"] += 1
            continue

        reason = _acceptable(replay.metadata, format_id, min_rating)
        if reason is not None:
            counts[reason] += 1
            continue

        kept.append(replay)
        if on_progress is not None:
            on_progress(replay.metadata.replay_id, len(kept), counts["considered"])

    manifest = CollectionManifest(
        schema_version=SCHEMA_VERSION,
        format_id=format_id,
        source=source,
        collected_at=utc_now(),
        git_commit=git_commit(),
        min_rating=min_rating,
        exclude_bots=exclude_bots,
        usage_note=USAGE_NOTE,
        replay_ids=tuple(r.metadata.replay_id for r in kept),
        considered=counts["considered"],
        rejected_bot=counts["bot"],
        rejected_unrated=counts["unrated"],
        rejected_rating=counts["rating"],
        rejected_format=counts["format"],
    )
    return Collection(manifest=manifest, replays=kept)


def load_collection(cache_dir: Path, manifest_path: Path) -> Collection:
    """Rebuild a collection from disk, without any network access."""
    manifest = CollectionManifest.load(manifest_path)
    return Collection(
        manifest=manifest,
        replays=[Replay.load(cache_dir / f"{rid}.json") for rid in manifest.replay_ids],
    )
