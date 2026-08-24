import pytest

from champions_ai.data import BattleTeam, TeamPool, parse_showdown_team


def _battle_team(name: str, species: str) -> BattleTeam:
    text = "\n\n".join(
        f"{species}{i} @ Leftovers\nAbility: A\n- Tackle" for i in range(6)
    )
    return BattleTeam(team=parse_showdown_team(text), packed=f"packed-{name}", name=name)


def _pool(size: int = 4) -> TeamPool:
    return TeamPool([_battle_team(f"t{i}", f"mon{i}_") for i in range(size)])


def test_a_pool_needs_two_teams_to_form_a_matchup():
    with pytest.raises(ValueError):
        TeamPool([_battle_team("only", "x")])


def test_matchups_pair_two_different_teams():
    for matchup in _pool().matchups(20, seed=1):
        assert matchup.teams[0] is not matchup.teams[1]


def test_matchups_are_reproducible_from_the_seed():
    first = [m.label for m in _pool().matchups(10, seed=5)]
    second = [m.label for m in _pool().matchups(10, seed=5)]
    assert first == second


def test_different_seeds_draw_different_matchups():
    first = [m.label for m in _pool().matchups(10, seed=1)]
    second = [m.label for m in _pool().matchups(10, seed=2)]
    assert first != second


def test_a_run_spreads_across_the_pool():
    """A result resting on one lucky pairing would not generalise."""
    labels = {m.label for m in _pool(6).matchups(20, seed=3)}
    assert len(labels) > 1


def test_count_must_be_positive():
    with pytest.raises(ValueError):
        _pool().matchups(0)


def test_matchup_label_identifies_the_pairing():
    matchup = _pool().matchups(1, seed=0)[0]
    assert matchup.teams[0].name in matchup.label
    assert matchup.teams[1].name in matchup.label


def test_battle_team_exposes_its_species():
    team = _battle_team("t", "pikachu_")
    assert len(team.species) == 6
    assert team.species[0] == "pikachu_0"


def test_a_seeded_pool_derives_one_seed_per_team():
    """Derived rather than shared, so growing `size` leaves earlier teams
    alone: team 3 is the same team in a pool of 4 and a pool of 40."""
    from champions_ai.data.team_pool import _derived

    base = "sodium," + "0" * 64
    seeds = [_derived(base, i) for i in range(5)]
    assert len(set(seeds)) == 5
    assert all(s.startswith("sodium,") for s in seeds)
    assert all(len(s.split(",")[1]) == 64 for s in seeds)
    # Stable: the same index always derives the same seed.
    assert _derived(base, 3) == seeds[3]


def test_an_unseeded_pool_asks_for_no_seed():
    from champions_ai.data.team_pool import _derived

    assert _derived("not-a-seed", 2) == "not-a-seed"
