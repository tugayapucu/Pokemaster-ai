"""How does my team do against the field?

Built for a deadline: a team has to be submitted for Frankfurt on 2026-09-25,
and until now this project could tell you what to do *in* a battle and nothing
about what to bring to one.

It answers a narrow question honestly rather than a broad one vaguely. The
opponents are real teams harvested from the ladder, both sides are played by
the same agent, and seats are swapped on a shared seed -- so the only thing
left between the two passes is the teams. What comes out is a win rate against
the field it was harvested from, and, more usefully, **the matchups that beat
it**.

What it is not: a metagame verdict. The pool is what the current ladder brings,
played the way this project plays -- best of four candidate actions 57% of the
time (0038). A losing matchup here is a real structural problem worth looking
at; a winning record here is not a reason to be confident at a Regional.
"""

from pathlib import Path

from champions_ai.agents import HeuristicAgent
from champions_ai.cli.play import dex_path, load_pool, load_team, pool_path_for
from champions_ai.cli.preview import species_name
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_C, Regulation
from champions_ai.env import BattleEnv
from champions_ai.evaluation.team_strength import scout_team
from champions_ai.simulator import BridgeError, ShowdownBridge


def _roster(dex: Dex, species: tuple[str, ...], width: int = 0) -> str:
    """Species as the dex spells them.

    ASCII only where it truncates: this prints to a Windows console that
    renders a typographic ellipsis as a replacement character, and a roster is
    exactly the line a reader needs to be able to scan.
    """
    names = ", ".join(species_name(dex, s) for s in species)
    if not width or len(names) <= width:
        return names
    return names[: width - 3] + "..."


def scout(
    *,
    team_path: Path,
    pool_path: Path | None = None,
    opponents: int = 40,
    seed: int = 0,
    regulation: Regulation = REGULATION_M_C,
) -> int:
    """Play one team against a sample of the field. Returns an exit code."""
    if pool_path is None:
        pool_path = pool_path_for(regulation)
    if not team_path.exists():
        print(f"No team at {team_path}. Pass --team with a Showdown export file.")
        return 2
    if not pool_path.exists():
        print(
            f"No team pool at {pool_path}.\n"
            "  Harvest one from a replay corpus first -- this measures a team\n"
            "  against real teams, and there is nothing to measure it against."
        )
        return 2

    with ShowdownBridge() as bridge:
        dex = Dex.cached(bridge, dex_path(regulation), mod=regulation.mod)
        try:
            team = load_team(bridge, regulation, team_path)
            pool = load_pool(bridge, regulation, pool_path)
        except BridgeError as error:
            print(f"\n  The engine refused something in {regulation.name}:\n    {error}")
            return 2

        env = BattleEnv(regulation, bridge=bridge)
        agent = HeuristicAgent(dex, name="both sides")

        print(f"\n  {regulation.name}")
        print(f"  Your team: {_roster(dex, tuple(e.species for e in team.team.pokemon))}")
        print(f"  Against {opponents} of {len(pool.teams)} harvested teams, "
              "each played from both seats.\n")

        def progress(done, total, wins, battles):
            if done % 10 == 0 or done == total:
                print(f"    {done}/{total} opponents, {wins}/{battles} battles won",
                      flush=True)

        report = scout_team(
            env, agent, team, pool, opponents=opponents, seed=seed, on_progress=progress
        )

        low, high = report.interval
        print(f"\n  {report.wins} of {report.battles} battles "
              f"({report.win_rate:.1%})   95% Wilson [{low:.1%}, {high:.1%}]")
        print(f"  {report.opponents} distinct opponents, {report.even()} split one-all, "
              f"{report.draws} drawn")

        # The losing matchups are the point. A win rate says whether to keep
        # looking; these say what to change.
        print("\n  Worst matchups")
        for matchup in report.worst():
            print(f"    {matchup.wins}/2  {_roster(dex, matchup.roster)}")
        print("\n  Best matchups")
        for matchup in report.best():
            print(f"    {matchup.wins}/2  {_roster(dex, matchup.roster)}")

        # One row is two battles, and a battle seed alone flips it. Groups pool
        # enough opponents for an interval to mean something.
        floor = max(5, report.opponents // 10)
        species = report.by_species(min_opponents=floor)
        if species:
            print(f"\n  Hardest opposing Pokemon (brought by {floor}+ opponents)")
            for group in species[:8]:
                low, high = group.interval
                print(f"    {group.rate:6.1%}  [{low:.0%}, {high:.0%}]  "
                      f"{group.opponents:3} opponents  {species_name(dex, group.label[0])}")
            print("    Screening every species finds a few low ones by chance: re-scout\n"
                  "    a suspect on fresh seeds before changing the team for it.")
        rosters = report.by_roster()
        if rosters:
            print("\n  Rosters drawn more than once")
            for group in rosters[:5]:
                print(f"    {group.wins}/{group.battles}  {_roster(dex, group.label)}")

        print(
            "\n  Both sides were played by the same agent, so an even matchup ties\n"
            "  and every deviation is the teams. The pool is what the ladder\n"
            "  brings, not what wins a Regional -- read a losing matchup as a\n"
            "  structural problem, and a winning record as nothing much."
        )
        return 0
