"""Measure how much of the battle protocol the tracker actually understands.

`BattleTracker` ignores line types it has no handler for. That is the right
behaviour -- the protocol is large and mostly cosmetic -- but it means a
genuine gap degrades *quietly*: reconstruction silently loses information and
nothing fails. This turns that into a number.

Used against real replays, it answers "what fraction of what really happens are
we modelling", which is not a question to answer by assumption.
"""

from collections import Counter
from dataclasses import dataclass, field

from champions_ai.simulator.tracker import BattleTracker, _handler_name

# Lines that carry no battle state: chat, timers, join/leave, presentation.
# Counted separately so they neither flatter nor depress the real figure.
COSMETIC = frozenset(
    {
        "j", "l", "c", "c:", "t:", "chat", "join", "leave", "raw", "html",
        "uhtml", "uhtmlchange", "inactive", "inactiveoff", "debug", "seed",
        "message", "-anim", "-hint", "-message", "askreg", "badge",
        "player", "teamsize", "gametype", "gen", "tier", "rated", "rule",
        "clearpoke", "start", "upkeep", "done", "expire", "turn", "win", "tie",
        # Announcements of things already derivable from the type chart, so
        # not modelling them loses nothing.
        "-supereffective", "-resisted", "-immune", "-crit", "-hitcount",
        "-miss", "-fail", "-notarget", "-nothing", "-ohko", "-zbroken",
        "-combine", "-waiting", "-prepare", "-mustrecharge", "-center",
    }
)


@dataclass(frozen=True)
class CoverageReport:
    """What a tracker understood, and what it walked past."""

    handled: Counter = field(default_factory=Counter)
    unhandled: Counter = field(default_factory=Counter)
    cosmetic: Counter = field(default_factory=Counter)

    @property
    def meaningful_total(self) -> int:
        return sum(self.handled.values()) + sum(self.unhandled.values())

    @property
    def fraction_handled(self) -> float:
        """Share of state-carrying lines the tracker has a handler for."""
        total = self.meaningful_total
        return sum(self.handled.values()) / total if total else 1.0

    def missing(self, limit: int = 15) -> list[tuple[str, int]]:
        """Unhandled line types, most frequent first -- the work queue."""
        return self.unhandled.most_common(limit)

    def render(self) -> str:
        lines = [
            f"protocol coverage: {self.fraction_handled:.1%} "
            f"of {self.meaningful_total} state-carrying lines",
            f"  handled types:   {len(self.handled)}",
            f"  unhandled types: {len(self.unhandled)}",
        ]
        if self.unhandled:
            lines.append("  most common gaps:")
            lines.extend(f"    |{name}|  x{count}" for name, count in self.missing())
        return "\n".join(lines)


def handler_name(line_type: str) -> str:
    """The tracker method a line type maps to. Delegates so the two cannot drift."""
    return _handler_name(line_type)


def measure_coverage(logs: list[tuple[str, ...]]) -> CoverageReport:
    """Classify every protocol line across the given logs."""
    report = CoverageReport(Counter(), Counter(), Counter())

    for log in logs:
        for line in log:
            if not line.startswith("|") or len(line) < 2:
                continue
            line_type = line.split("|")[1]
            if not line_type:
                continue
            if line_type in COSMETIC:
                report.cosmetic[line_type] += 1
            elif hasattr(BattleTracker, handler_name(line_type)):
                report.handled[line_type] += 1
            else:
                report.unhandled[line_type] += 1

    return report
