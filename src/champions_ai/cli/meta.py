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
from champions_ai.evaluation.metagame import sets_for, survey
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
        # Evidence is only gathered for the detail view: it re-reads every
        # replay, and the overview does not need it.
        from champions_ai.data.harvest import gather_evidence

        return _detail(report, species, name, gather_evidence(replays), dex)

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


def _detail(report, species: str, name, evidence, dex) -> int:
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

    _sets(sets_for(evidence, wanted), dex)

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


def _label(dex, kind: str, identifier: str) -> str:
    """A move, item or ability as the dex spells it."""
    try:
        if kind == "move":
            return dex.get_move(identifier).name
        if kind == "item":
            return dex.get_item(identifier).name
    except KeyError:
        pass
    return identifier


def _sets(usage, dex) -> None:
    """What it was seen running, with each block's denominator stated.

    The denominators differ and that is the point: moves divide by appearances
    and are exact, items divide by how often an item was *revealed*, and
    abilities divide by activations, which can exceed appearances several times
    over. Printing a bare percentage for all three would invite reading them as
    the same kind of number.
    """
    if usage is None or not usage.appearances:
        print("\n    Never seen in play, so nothing is known about its sets.")
        return

    if usage.moves:
        print(f"\n    moves, of {usage.appearances} appearances")
        for move, seen in usage.moves:
            print(f"    {_label(dex, 'move', move):<22}{seen:>7}{seen / usage.appearances:>8.0%}")

    rate = usage.item_reveal_rate
    print(
        f"\n    items, revealed in {usage.revealed_items} of {usage.appearances} "
        f"appearances ({rate:.0%})"
    )
    if not usage.items:
        print("    none ever revealed -- nothing here to read")
    else:
        for item, seen in usage.items:
            share = seen / usage.revealed_items if usage.revealed_items else 0.0
            print(f"    {_label(dex, 'item', item):<22}{seen:>7}{share:>8.0%}")
        if rate < 0.25:
            print(
                "    ** low reveal rate: an item is only seen when it fires, so this\n"
                "       is a sample of the items that *announce themselves*, not of\n"
                "       what the species runs. Read it as a hint at best."
            )

    if usage.abilities:
        print(f"\n    abilities, of {usage.ability_activations} activations")
        for ability, seen in usage.abilities:
            share = seen / usage.ability_activations
            print(f"    {ability:<22}{seen:>7}{share:>8.0%}")
