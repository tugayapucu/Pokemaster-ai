"""Team Preview: six species against six, and nothing else to go on.

The first decision of every battle and the one a player most wants help with,
because at this point both sides are just names. It was previously made for you
and announced in a single line, which is the wrong shape for a decision this
open: there are fifteen ways to choose four of six and the reasoning behind the
pick is a grid, not a sentence.

**The grid is the product here, not the recommendation.** `matchup_table` is
what the agent decides from, and a player reading it can disagree on grounds
the agent cannot express -- a set they can see and we cannot, a lead they know
this opponent favours.

Two things are stated on screen rather than buried, because overselling this
screen would be easy. The pick is chosen for **coverage**: for each of their
six we take our best answer among the four, so four Pokemon that all beat the
same threat score badly. And the **lead order is not evidence-backed** -- it
was measured at 48.4% against a 50% baseline, which is no signal at all.
"""

from champions_ai.dex import Dex
from champions_ai.domain import TeamPreview

# Wide enough to tell Kingambit from Kingdra, narrow enough that six columns
# and a label fit inside eighty.
COLUMN = 7

# Width of the row label: a star, an index, and a truncated species name.
LABEL = 16


def _short(name: str, width: int = COLUMN) -> str:
    return name if len(name) <= width else name[: width - 1] + "."


def species_name(dex: Dex, species: str) -> str:
    """The dex spelling, falling back to whatever the team said."""
    try:
        return dex.get_species(species).name
    except KeyError:
        return species


def render_preview(
    preview: TeamPreview,
    table: list[list[float]],
    picks: tuple[int, ...],
    reasons: tuple[tuple[str, float], ...],
    dex: Dex,
) -> str:
    """The whole screen: both rosters, the matchup grid, and the pick."""
    ours = [species_name(dex, p.species) for p in preview.own_team.pokemon]
    theirs = [species_name(dex, p.species) for p in preview.opponent_team]

    lines = ["", "TEAM PREVIEW", "=" * 62, ""]

    lines.append("  Your six                      Their six")
    for index in range(max(len(ours), len(theirs))):
        left = f"{index + 1}. {ours[index]}" if index < len(ours) else ""
        right = theirs[index] if index < len(theirs) else ""
        lines.append(f"  {left:<30}{right}")

    lines.append("")
    lines.append("  Matchup: your row against their column, -100 to +100.")
    lines.append("  Positive favours you. A star marks the four we would bring.")
    lines.append("")
    header = "".join(f"{_short(name):>{COLUMN + 1}}" for name in theirs)
    lines.append(f"  {'':<{LABEL}}{header}{'avg':>8}")
    for index, name in enumerate(ours):
        row = table[index] if index < len(table) else []
        # `matchup().net` runs -1 to +1 with a median near zero, so two thirds
        # of a table printed at whole-number precision reads as 0. Scaling to
        # -100..+100 is the same number with its information intact.
        cells = "".join(f"{value * 100:>{COLUMN + 1}.0f}" for value in row)
        average = sum(row) / len(row) if row else 0.0
        marker = "*" if index in picks else " "
        label = f"{marker} {index + 1}. {_short(name, 11)}"
        lines.append(f"  {label:<{LABEL}}{cells}{average * 100:>8.0f}")

    lines.append("")
    lines.append("  Bring these four, in this order:")
    for position, index in enumerate(picks):
        reason = reasons[position][0] if position < len(reasons) else ""
        # `explain_team_preview` prefixes the species already; drop it so the
        # numbered line does not say the name twice.
        _, _, detail = reason.partition(": ")
        lines.append(f"    {position + 1}. {ours[index]:<16}{detail}")

    lines.append("")
    lines.append("  Chosen for coverage: for each of their six we take our best answer")
    lines.append("  among the four, so four Pokemon that all beat the same threat score")
    lines.append("  badly. The first two lead.")
    lines.append("")
    lines.append("  On the order: measured at 48.4% against a 50% baseline, which is no")
    lines.append("  signal. Treat the four as the advice and the order as a coin toss.")
    return "\n".join(lines)


def parse_picks(answer: str, roster_size: int, wanted: int) -> tuple[int, ...] | None:
    """Read "2 4 1 5" as a pick, or return None if it is not one.

    Accepts the numbers shown on screen, which are 1-based, and returns the
    0-based indices the domain uses -- an off-by-one here would silently bring
    the wrong Pokemon, so it is converted in exactly one place.
    """
    parts = answer.replace(",", " ").split()
    if len(parts) != wanted:
        return None
    picks = []
    for part in parts:
        if not part.isdigit():
            return None
        value = int(part) - 1
        if not 0 <= value < roster_size or value in picks:
            return None
        picks.append(value)
    return tuple(picks)
