"""Derive `data/field-priors-champions.json` from the replay corpus.

Separate from `run.py` because the two answer different questions and fail in
different ways. This one asks *what does the corpus say*, and its output is a
file a human can read and argue with. `run.py` asks whether acting on it wins
games.

    python experiments/0048-team-preview-field/build.py

The file is gitignored: it is a measurement of a corpus that is not published,
so it should be rebuilt from whatever corpus is to hand rather than inherited.
"""

from pathlib import Path

from champions_ai.data import load_all
from champions_ai.data.priors import build_field_priors, save_field_priors
from champions_ai.domain import REGULATION_M_C

CORPUS = Path("data/replays")
OUT = Path(f"data/field-priors-{REGULATION_M_C.mod}.json")


def main() -> None:
    corpus = load_all(CORPUS, REGULATION_M_C.format_id, None)
    replays = list(corpus.replays)
    if not replays:
        raise SystemExit(f"no {REGULATION_M_C.name} replays under {CORPUS}")

    priors = build_field_priors(replays)
    save_field_priors(priors, OUT)

    print(f"\n  {len(replays)} replays -> {len(priors)} species\n")
    print(f"  {'species':<20} {'effect':<16} {'previewed':>9} {'set':>6} {'P':>6}")
    for prior in sorted(priors.values(), key=lambda p: -p.previewed):
        print(
            f"  {prior.species:<20} {prior.effect:<16}"
            f" {prior.previewed:>9} {prior.established:>6} {prior.probability:>5.0%}"
        )
    print(f"\n  written to {OUT}\n")


if __name__ == "__main__":
    main()
