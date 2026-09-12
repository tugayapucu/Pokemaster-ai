"""Derive `data/mega-priors-champions.json` from the replay corpus.

    python experiments/0052-team-preview-megas/build.py

The dex comes from its cache file, so this needs no engine. The output is
gitignored: a measurement of a corpus that is not published.
"""

from pathlib import Path

from champions_ai.cli.play import dex_path
from champions_ai.data import load_all
from champions_ai.data.priors import build_mega_priors, save_mega_priors
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_C

CORPUS = Path("data/replays")
OUT = Path(f"data/mega-priors-{REGULATION_M_C.mod}.json")


def main() -> None:
    dex = Dex.model_validate_json(Path(dex_path(REGULATION_M_C)).read_text(encoding="utf-8"))
    replays = list(load_all(CORPUS, REGULATION_M_C.format_id, None).replays)
    if not replays:
        raise SystemExit(f"no {REGULATION_M_C.name} replays under {CORPUS}")

    priors = build_mega_priors(replays, dex)
    save_mega_priors(priors, OUT)

    print(f"\n  {len(replays)} replays -> {len(priors)} species\n")
    print(f"  {'species':<16} {'forme':<22} {'on field':>8} {'megas':>6} {'rate':>6}")
    for prior in sorted(priors.values(), key=lambda p: -p.on_field):
        print(
            f"  {prior.species:<16} {prior.forme:<22} {prior.on_field:>8}"
            f" {prior.megas:>6} {prior.rate:>5.0%}"
        )
    print(f"\n  written to {OUT}\n")


if __name__ == "__main__":
    main()
