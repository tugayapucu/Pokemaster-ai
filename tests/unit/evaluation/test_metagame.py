"""Counting what the field brings, and the two ways that count misleads.

Usage is arithmetic and hard to get wrong. The two rankings are not, and both
went wrong on the first run against the real corpus:

- **Win rate ranked by point estimate** put three 62-game species above a
  219-game one. With several hundred species, taking the top ten by rate
  selects whichever got lucky.
- **Pair lift with a low floor** put Florges (18 co-occurrences) above
  Incineroar (1,200) among Rillaboom's partners. A ratio from eleven
  observations is noise wearing a decimal point.

Both are the same mistake -- reading a number computed from too little data --
and both are pinned here.
"""

from champions_ai.evaluation.metagame import survey


class _Replay:
    """A replay is a log plus metadata; only `|poke|`, `|win|` and the player
    names matter to this module."""

    def __init__(self, left, right, winner=None, players=("alice", "bob")):
        lines = [f"|poke|p1|{s}, L50, M|" for s in left]
        lines += [f"|poke|p2|{s}, L50, M|" for s in right]
        if winner:
            lines.append(f"|win|{winner}")
        self.log = tuple(lines)
        self.metadata = type("M", (), {"players": players, "minimum_rating": 1000})()

    @property
    def winner(self):
        for line in self.log:
            if line.startswith("|win|"):
                return line.split("|")[2]
        return None


def test_usage_counts_both_declared_sixes():
    """The `|poke|` lines are what a player *brought*, and both sides have
    them -- so usage is not biased by what happened to be revealed in play."""
    report = survey([_Replay(["Rillaboom", "Torkoal"], ["Rillaboom", "Sneasler"])])
    usage = {u.species: u.teams for u in report.usage}
    assert report.teams == 2
    assert usage["rillaboom"] == 2
    assert usage["torkoal"] == 1


def test_a_replay_with_no_winner_counts_for_usage_but_not_for_record():
    """Counting it as a loss for both sides would drag every win rate down."""
    report = survey([_Replay(["Torkoal"], ["Sneasler"])])
    entry = next(u for u in report.usage if u.species == "torkoal")
    assert entry.teams == 1
    assert entry.decided == 0
    assert entry.win_rate == 0.0


def test_the_winner_is_matched_to_a_side_by_name():
    report = survey([_Replay(["Torkoal"], ["Sneasler"], winner="bob")])
    by_name = {u.species: u for u in report.usage}
    assert by_name["sneasler"].wins == 1
    assert by_name["torkoal"].wins == 0


def test_a_winner_who_is_neither_player_decides_nothing():
    """A name that matches no player means the log is not readable that way,
    and guessing a side would be worse than declining to."""
    report = survey([_Replay(["Torkoal"], ["Sneasler"], winner="somebody-else")])
    assert all(u.decided == 0 for u in report.usage)


def test_win_rate_ranks_by_the_lower_bound_not_the_rate():
    """The trap. A species with a great record over sixty games must not
    outrank a solid one over six hundred: with hundreds of species, the top of
    a point-estimate ranking is a list of small samples."""
    # 40 of 60 is a better *rate* than 360 of 600, and a worse lower bound:
    # 66.7% [54%, 77%] against 60.0% [56%, 64%]. That gap is the whole point.
    lucky = [_Replay(["Lucky"], ["Filler"], winner="alice") for _ in range(40)]
    lucky += [_Replay(["Lucky"], ["Filler"], winner="bob") for _ in range(20)]
    solid = [_Replay(["Solid"], ["Filler"], winner="alice") for _ in range(360)]
    solid += [_Replay(["Solid"], ["Filler"], winner="bob") for _ in range(240)]

    report = survey(lucky + solid)
    by_name = {u.species: u for u in report.usage}
    assert by_name["lucky"].win_rate > by_name["solid"].win_rate

    ranked = [u.species for u in report.by_win_rate(count=5, minimum=50)]
    assert ranked.index("solid") < ranked.index("lucky"), (
        "a 60-game record outranked a 600-game one; this is ranking by luck"
    )


def test_a_rare_pair_is_dropped_rather_than_topping_the_lift_table():
    """Lift from a handful of co-occurrences is noise with a decimal point."""
    common = [
        _Replay(["Rillaboom", "Incineroar"], ["Filler"], winner="alice")
        for _ in range(50)
    ]
    rare = [_Replay(["Rillaboom", "Florges"], ["Filler"], winner="alice")]

    report = survey(common + rare, pair_minimum=40)
    partners = [name for name, _, _ in report.partners("rillaboom")]
    assert "incineroar" in partners
    assert "florges" not in partners


def test_pair_lift_is_relative_to_how_popular_each_species_is():
    """Two popular species meet often by being popular. Lift asks whether they
    meet *more* than that, which is the question a team builder has."""
    # A appears 100 times, B 80, C 100, over 200 teams.
    #   A with B: 80 against 40 expected -> 2.0x
    #   A with C: 20 against 50 expected -> 0.4x
    # C is exactly as popular as A, so raw co-occurrence alone would not
    # separate them; only the comparison against expectation does.
    together = [_Replay(["A", "B"], ["C", "D"], winner="alice") for _ in range(80)]
    apart = [_Replay(["A", "C"], ["D", "E"], winner="alice") for _ in range(20)]

    report = survey(together + apart, pair_minimum=10)
    lifts = {name: lift for name, _, lift in report.partners("a")}
    assert lifts["b"] > lifts.get("c", 0)
