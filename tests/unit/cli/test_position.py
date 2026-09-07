"""The loop's own state: history, undo, and refusing without losing anything.

Everything the loop does with a position is tested in `tests/unit/position`.
What is only here is the history stack -- a refused line must not push onto it,
or `undo` walks back through commands that never took effect, and the player
loses work they did type while trying to remove work they did not.

The bridge, the dex and the engine seeding are stubbed. This is about the loop.
"""

from types import SimpleNamespace

import pytest

import champions_ai.cli.position as module
from champions_ai.domain import (
    BattlePokemon,
    PokemonSet,
    Side,
    StatSpread,
)

THEIR_SIX = ("kingambit", "charizard", "aerodactyl", "farigiraf", "garchomp", "sylveon")
OUR_FOUR = ("blaziken", "torkoal", "mawile", "sneasler")


class _Bridge:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Dex:
    species = dict.fromkeys([*THEIR_SIX, *OUR_FOUR], None)
    moves: dict = {}
    items: dict = {}

    @classmethod
    def cached(cls, *args, **kwargs):
        return cls()

    def get_species(self, name):
        raise KeyError(name)


def _mon(species: str) -> BattlePokemon:
    return BattlePokemon(
        pokemon_set=PokemonSet(
            species=species, level=50, ability="blaze", moves=("tackle",),
            stats=StatSpread(hp=11),
        ),
        current_hp=150,
        max_hp=150,
    )


@pytest.fixture
def session(monkeypatch, tmp_path):
    """A running loop with everything but the loop stubbed out."""
    team_file = tmp_path / "team.txt"
    team_file.write_text("stub", encoding="utf-8")

    monkeypatch.setattr(module, "ShowdownBridge", _Bridge)
    monkeypatch.setattr(module, "Dex", _Dex)
    declared = SimpleNamespace(
        team=SimpleNamespace(
            pokemon=tuple(_mon(s).pokemon_set for s in (*OUR_FOUR, "farigiraf", "sylveon"))
        )
    )
    monkeypatch.setattr(module, "load_team", lambda *a, **k: declared)
    monkeypatch.setattr(module, "move_data_from_dex", lambda dex: {})
    monkeypatch.setattr(module, "Recommender", lambda *a, **k: None)
    monkeypatch.setattr(module, "HeuristicAgent", lambda *a, **k: None)
    monkeypatch.setattr(
        module,
        "own_side",
        lambda *a, **k: Side(team=tuple(_mon(s) for s in OUR_FOUR), active_slots=(0, 1)),
    )

    seen: list = []

    def record(position, dex, move_data, recommender):
        seen.append(position)

    monkeypatch.setattr(module, "_advise", record)

    def run(lines: list[str]) -> list:
        script = iter(
            [
                " ".join(THEIR_SIX),      # their six
                "1 2 3 4",                # our picks
                "kingambit charizard",    # their leads
                *lines,
            ]
        )
        monkeypatch.setattr(module, "_ask", lambda prompt: next(script))
        seen.clear()
        assert module.position(team_path=team_file) == 0
        return seen

    return run


def test_a_session_runs_and_advises_from_the_position_typed(session):
    shown = session(["gambit 40", "q"])
    assert shown[-1].their_seen[0].hp_percent == 40


def test_undo_steps_back_one_command(session):
    shown = session(["gambit 40", "gambit 10", "u", "q"])
    assert shown[-1].their_seen[0].hp_percent == 40


def test_a_refused_line_does_not_go_on_the_history(session):
    """The bug this exists for: a refusal pushing the unchanged position means
    the next `undo` steps back over a command that never happened, and the
    player's real work goes with it."""
    shown = session(["gambit 40", "gambit 900", "u", "q"])
    assert shown[-1].their_seen[0].hp_percent == 100


def test_undo_with_nothing_to_undo_does_not_fall_over(session):
    assert session(["u", "q"])


def test_help_does_not_change_the_position(session):
    shown = session(["gambit 40", "?", "q"])
    assert shown[-1].their_seen[0].hp_percent == 40


def test_a_missing_team_file_is_reported_rather_than_raised(tmp_path):
    assert module.position(team_path=tmp_path / "nope.txt") == 2
