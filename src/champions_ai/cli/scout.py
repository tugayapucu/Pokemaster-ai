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

from champions_ai.agents import FixedPreviewAgent, HeuristicAgent
from champions_ai.cli.play import dex_path, load_pool, load_team, pool_path_for
from champions_ai.cli.preview import species_name
from champions_ai.dex import Dex
from champions_ai.dex.reference import to_id
from champions_ai.domain import REGULATION_M_C, Regulation
from champions_ai.env import BattleEnv
from champions_ai.evaluation.team_strength import scout_team
from champions_ai.position.names import resolve_species
from champions_ai.simulator import BridgeError, ShowdownBridge

# 0053 measured a 40-opponent scout at 57.5% and the same draw at 120 at 50.8%:
# breadth is where the variance is, and 40 is a look rather than a number.
DEFAULT_OPPONENTS = 120


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


def _picks(dex: Dex, own_species: tuple[str, ...], bring: str, size: int) -> tuple[int, ...]:
    """Which of our six to bring, in lead order, from typed names or fragments.

    Resolved against our own team rather than the whole dex, so a fragment is
    enough and anything not on the team is refused rather than quietly dropped.
    """
    names = [part.strip() for part in bring.split(",") if part.strip()]
    if len(names) != size:
        raise ValueError(
            f"--bring takes the {size} you bring, in lead order; got {len(names)}"
        )
    picks = []
    for name in names:
        species = resolve_species(dex, name, within=own_species)
        index = [i for i, own in enumerate(own_species) if to_id(own) == species]
        if not index:
            raise ValueError(f"{name!r} is not on this team")
        if index[0] in picks:
            raise ValueError(f"{name!r} is in --bring twice")
        picks.append(index[0])
    return tuple(picks)


def scout(
    *,
    team_path: Path,
    pool_path: Path | None = None,
    opponents: int = DEFAULT_OPPONENTS,
    seed: int = 0,
    regulation: Regulation = REGULATION_M_C,
    mega_on_ties: bool = False,
    bring: str = "",
) -> int:
    """Play one team against a sample of the field. Returns an exit code.

    `mega_on_ties` is set on the agent playing *both* sides, so the opponents
    take their Mega ties the same way and the comparison stays even (0060).

    `bring` is a comma-separated four, in lead order. Without it the agent picks
    them, and the scout is then partly measuring the picker: on one candidate
    the agent's picks and the player's own differed by 42 battles of 240 on the
    same opponents and seeds.
    """
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
        own_species = tuple(entry.species for entry in team.team.pokemon)
        if bring:
            try:
                picks = _picks(dex, own_species, bring, regulation.picked_team_size)
            except ValueError as error:
                print(f"\n  {error}")
                return 2
            agent = FixedPreviewAgent(
                dex, name="both sides", mega_on_ties=mega_on_ties,
                own_species=own_species, picks=picks,
            )
        else:
            agent = HeuristicAgent(dex, name="both sides", mega_on_ties=mega_on_ties)

        print(f"\n  {regulation.name}")
        print(f"  Your team: {_roster(dex, own_species)}")
        print(f"  Against {opponents} of {len(pool.teams)} harvested teams, "
              "each played from both seats.\n")
        if bring:
            chosen = [species_name(dex, own_species[i]) for i in agent.picks]
            slots = regulation.active_slots_per_side
            print(f"  Bringing: {', '.join(chosen[:slots])} (leading), "
                  f"then {', '.join(chosen[slots:])}\n")
        else:
            print("  The agent picks which four to bring. Pass --bring to decide\n"
                  "  yourself: without it this measures the picker as much as the team.\n")
        if opponents < DEFAULT_OPPONENTS:
            print(f"  {opponents} opponents is below the {DEFAULT_OPPONENTS} this needs to be\n"
                  "  read as a number: a 40-opponent run once read 57.5% where the same\n"
                  "  draw at 120 read 50.8%. Treat what follows as a look.\n")
        if mega_on_ties:
            print("  Both sides take a Mega when it ties with not doing so.\n")

        def progress(done, total, wins, battles):
            if done % 10 == 0 or done == total:
                print(f"    {done}/{total} opponents, {wins}/{battles} battles won",
                      flush=True)

        report = scout_team(
            env, agent, team, pool, opponents=opponents, seed=seed, on_progress=progress
        )

        if bring:
            # Only our side may be forced. Each battle has two previews, one a
            # side: ours forced, theirs left to the agent.
            print(f"\n  Team Preview forced to your four: {agent.forced}"
                  f" of {report.battles + len(report.refused)} battles"
                  f"  (left to the agent: {agent.left_to_the_agent})")
            if agent.forced_on_a_mirror:
                print(f"  {agent.forced_on_a_mirror} of those were an opposing team with your"
                      " exact six, so both sides were forced.")

        low, high = report.interval
        print(f"\n  {report.wins} of {report.battles} battles "
              f"({report.win_rate:.1%})   95% Wilson [{low:.1%}, {high:.1%}]")
        print(f"  {report.opponents} distinct opponents, {report.even()} split one-all, "
              f"{report.draws} drawn")
        if report.refused:
            # Skipped so the run survives, but each one is a legality bug: the
            # engine refused something we offered. The seed reproduces it.
            first = report.refused[0]
            print(f"  {len(report.refused)} battle(s) refused by the engine and skipped. "
                  f"First: seat {first.seat}, seed {first.seed}\n"
                  f"    {first.message}")

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
