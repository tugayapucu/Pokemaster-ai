"""Collect a replay corpus for one format.

Driven by hand until now, which was fine while there was one format and one
corpus. It stopped being fine the day a new regulation appeared: collecting for
it is the first thing that can be done, and it is the thing most likely to be
done in a hurry.

**Taken by format id, not by `Regulation`.** A regulation this project has a
model for is one whose rules and dex it claims to know; a format id is just a
string the replay server indexes by. Collecting for a regulation that is not
yet simulatable therefore assumes nothing about it, which is the whole point --
the replays exist well before the mod is installable, and downloading them is
the only preparation available in that gap.

The constraints on this data are in `data/collect.py` and enforced there: no
licence covers the logs, so the corpus is for local research and is never
redistributed, and the request throttle is a courtesy obligation rather than
their permission. Nothing here loosens either.
"""

from pathlib import Path

from champions_ai.data.collect import DEFAULT_SOURCE, collect_replays

DEFAULT_CORPUS = Path("data/replays")
DEFAULT_MIN_RATING = 1500


def _progress(replay_id: str, kept: int, considered: int) -> None:
    if kept % 25 == 0:
        print(f"    {kept} kept of {considered} considered", flush=True)


def collect(
    *,
    format_id: str,
    corpus_path: Path = DEFAULT_CORPUS,
    target: int = 500,
    min_rating: int | None = DEFAULT_MIN_RATING,
    source: str = DEFAULT_SOURCE,
) -> int:
    """Fetch up to `target` replays. Returns a process exit code."""
    corpus_path.mkdir(parents=True, exist_ok=True)

    bar = "any rating" if min_rating is None else f"both players at {min_rating}+"
    print(f"\n  Collecting {format_id}")
    print(f"  into {corpus_path}, target {target}, {bar}, bots excluded.")
    print("  One request a second, and anything already on disk is not fetched again.")

    collection = collect_replays(
        format_id,
        corpus_path,
        target=target,
        min_rating=min_rating,
        source=source,
        on_progress=_progress,
    )
    manifest = collection.manifest
    path = collection.save(corpus_path)

    print(f"\n  Kept {manifest.kept} of {manifest.considered} considered.")
    print(f"    rejected: {manifest.rejected_bot} bot, {manifest.rejected_unrated} unrated, "
          f"{manifest.rejected_rating} under the bar, {manifest.rejected_format} wrong format")
    print(f"  Manifest: {path}")

    if manifest.kept < target:
        # Not a failure. The listing ran out, which for a new regulation means
        # the format is younger than the target -- worth saying plainly rather
        # than leaving a short corpus to be noticed later.
        print(f"\n  That is short of {target}: the listing ran out. For a format that has")
        print("  only just appeared, there may simply not be that many games yet.")
    return 0
