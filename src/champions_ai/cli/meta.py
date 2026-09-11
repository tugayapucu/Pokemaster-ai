"""What is the field bringing?

The half of team building that comes before `scout`. `scout` grades a team that
already exists; this is for the stage before one does, when the only thing to
look at is several thousand raw exports.

Counted from replays rather than the harvested pool, because the `|poke|` lines
carry both sides' declared six and no player can hide them -- so usage is what
was *brought to Team Preview*, not what happened to be revealed in play -- and
because a replay records who won.

Read the usage column as fact about the sample and the win rate as a hint with
a wide error bar. It is a young ladder, rated 1000-1400, and a species that
strong players favour looks good whether or not it caused anything.
"""

from pathlib import Path

from champions_ai.cli.play import dex_path
from champions_ai.cli.preview import species_name
from champions_ai.data import load_all
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_C, Regulation
from champions_ai.evaluation.metagame import survey
from champions_ai.simulator import ShowdownBridge

DEFAULT_CORPUS = Path("data/replays")


def meta(
    *,
    corpus_path: Path = DEFAULT_CORPUS,
    species: str | None = None,
    count: int = 20,
    minimum: int = 60,
    min_rating: int | None = None,
    regulation: Regulation = REGULATION_M_C,
) -> int:
    """Report what the field brings. Returns a process exit code."""
    if not corpus_path.exists():
        print(f"No replay corpus at {corpus_path}. Collect one with `champions-ai collect`.")
        return 2

    corpus = load_all(corpus_path, regulation.format_id, min_rating)
    replays = list(corpus.replays)
    if not replays:
        bar = f" at {min_rating}+" if min_rating else ""
        print(f"No {regulation.name} replays{bar} under {corpus_path}.")
        return 2

    report = survey(replays)
    rated = [r.metadata.minimum_rating for r in replays if r.metadata.minimum_rating]
    span = f"rated {min(rated)}-{max(rated)}" if rated else "of unknown rating"

    with ShowdownBridge() as bridge:
        dex = Dex.cached(bridge, dex_path(regulation), mod=regulation.mod)

    def name(identifier: str) -> str:
        return species_name(dex, identifier)

    print(f"\n  {regulation.name}")
    print(f"  {report.replays} replays, {report.teams} declared teams, {span}\n")

    if species is not None:
        return _detail(report, species, name)

    print(f"  {'species':<20}{'teams':>7}{'share':>8}{'win rate':>11}   95% Wilson")
    for entry in report.most_used(count):
        low, high = entry.interval
        print(
            f"  {name(entry.species):<20}{entry.teams:>7}{report.share(entry):>8.1%}"
            f"{entry.win_rate:>11.1%}   [{low:.0%}, {high:.0%}]"
        )

    print(f"\n  Best win rate, among species in {minimum}+ decided games")
    for entry in report.by_win_rate(10, minimum):
        low, high = entry.interval
        print(
            f"  {name(entry.species):<20}{entry.decided:>7}{report.share(entry):>8.1%}"
            f"{entry.win_rate:>11.1%}   [{low:.0%}, {high:.0%}]"
        )

    print(
        "\n  Usage is a fact about the sample: the `|poke|` lines are complete for\n"
        "  both sides, so this is what players brought rather than what they\n"
        "  happened to reveal. **Win rate is not a verdict** -- it is confounded\n"
        "  with who plays what, the intervals are wide, and this ladder is days\n"
        "  old. Use `--species <name>` for what a species is brought with."
    )
    return 0


def _detail(report, species: str, name) -> int:
    """One species: how often, how well, and what it is brought with."""
    wanted = species.lower().replace(" ", "").replace("-", "")
    entry = next((u for u in report.usage if u.species == wanted), None)
    if entry is None:
        print(f"  Nothing in this corpus brought {species!r}.")
        return 2

    low, high = entry.interval
    print(f"  {name(entry.species)}")
    print(f"    brought by {entry.teams} teams ({report.share(entry):.1%} of them)")
    print(
        f"    won {entry.wins} of {entry.decided} decided games "
        f"({entry.win_rate:.1%}, [{low:.0%}, {high:.0%}])"
    )

    partners = report.partners(wanted)
    if not partners:
        print("\n    No partner appeared with it often enough to measure.")
        return 0

    print(f"\n    {'brought with':<20}{'together':>9}{'lift':>8}")
    for other, together, lift in partners:
        print(f"    {name(other):<20}{together:>9}{lift:>8.2f}x")
    print(
        "\n    Lift, not raw count: two popular species appear together often by\n"
        "    being popular. Above 1.0 means more often than that explains."
    )
    return 0
