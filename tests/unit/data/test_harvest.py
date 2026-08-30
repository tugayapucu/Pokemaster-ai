"""Tests for building teams out of the ones humans actually brought.

Every case here is one the real corpus produced and the engine rejected, so
they are regression tests rather than hypotheticals. The engine is the real
gate -- `TeamPool.from_texts` validates -- but a rejection there costs a whole
team, and these keep the common causes from coming back.
"""

import random

import pytest

from champions_ai.data.harvest import (
    SpeciesEvidence,
    brought,
    build_set,
    gather_evidence,
    harvest_teams,
)


class FakeSpecies:
    def __init__(self, abilities):
        self.abilities = abilities


class FakeDex:
    """Only what `build_set` asks for."""

    def __init__(self, abilities: dict[str, tuple[str, ...]]):
        self._abilities = abilities

    def get_species(self, species: str):
        if species not in self._abilities:
            raise KeyError(species)
        return FakeSpecies(self._abilities[species])


def _log(*lines: str) -> tuple[str, ...]:
    return tuple(lines)


REPLAY = _log(
    "|poke|p1|Farigiraf, L50, M|",
    "|poke|p1|Torkoal, L50, F|",
    "|poke|p2|Incineroar, L50, M|",
    "|switch|p1a: Giraffe|Farigiraf, L50, M|100/100",
    "|switch|p1b: Turtle|Torkoal, L50, F|100/100",
    "|switch|p2a: Cat|Incineroar, L50, M|100/100",
    "|turn|1",
    "|move|p1a: Giraffe|Trick Room|",
    "|move|p1b: Turtle|Eruption|p2a: Cat",
    "|move|p2a: Cat|Fake Out|p1a: Giraffe",
    "|turn|2",
    "|move|p1a: Giraffe|Psychic|p2a: Cat",
)


class TestReadingTheLog:
    def test_team_sheets_are_read_per_player(self):
        assert brought(REPLAY) == {
            "p1": ["farigiraf", "torkoal"],
            "p2": ["incineroar"],
        }

    def test_moves_are_attributed_through_nicknames(self):
        """Players rename their Pokemon, so `|move|p1a: Giraffe|` says nothing
        about the species until the switch lines are read."""

        class R:
            log = REPLAY

        evidence = gather_evidence([R()])
        assert set(evidence["farigiraf"].moves) == {"trickroom", "psychic"}
        assert set(evidence["torkoal"].moves) == {"eruption"}
        assert set(evidence["incineroar"].moves) == {"fakeout"}

    def test_one_appearance_yields_one_partial_set(self):
        """Two clicks on the same Pokemon in one battle are one set, not two.

        Counting them separately would make a Pokemon that was out for four
        turns look like four different players' sets.
        """

        class R:
            log = REPLAY

        evidence = gather_evidence([R()])
        assert evidence["farigiraf"].appearances == 1
        assert evidence["farigiraf"].observed_sets == [("psychic", "trickroom")]


class TestItemClause:
    """Reg M-B allows one of each item per team.

    Sitrus Berry and Focus Sash announce themselves when consumed, so they
    dominate the observed evidence and every species independently answers
    "Sitrus Berry". That put three on one team and the engine threw out the
    whole thing -- 129 rejections in one run of 200.
    """

    def _evidence(self) -> dict[str, SpeciesEvidence]:
        out = {}
        for name in ("aaa", "bbb", "ccc"):
            record = SpeciesEvidence()
            record.moves.update(["tackle"])
            record.observed_sets.append(("tackle",))
            record.items.update(["sitrusberry"] * 5)
            out[name] = record
        return out

    def test_one_team_does_not_get_the_same_item_twice(self):
        evidence = self._evidence()
        rng = random.Random(0)
        taken: set[str] = set()
        sets = [build_set(name, evidence, rng, taken_items=taken) for name in ("aaa", "bbb", "ccc")]
        held = [s for s in sets if s and "@" in s.splitlines()[0]]
        assert len(held) == 1, "only the first Pokemon may take the Sitrus Berry"
        assert taken == {"sitrusberry"}

    def test_harvest_teams_shares_the_set_across_a_whole_team(self):
        """The bug that actually happened, at the level it happened.

        `taken_items` existed as a parameter of `build_set` for one commit
        while `harvest_teams` never passed it, so the clause was enforced by a
        function nobody called that way. Both item tests above pass `build_set`
        the set directly and would have stayed green throughout. This one goes
        through the real entry point.
        """
        record = SpeciesEvidence()
        record.moves.update(["tackle"])
        record.observed_sets.append(("tackle",))
        record.items.update(["sitrusberry"] * 5)
        names = ["aaa", "bbb", "ccc", "ddd", "eee", "fff"]
        evidence = {name: record for name in names}

        class R:
            log = tuple(
                [f"|poke|p1|{name.title()}, L50, M|" for name in names]
                + [f"|switch|p1a: {name.title()}|{name.title()}, L50, M|100/100" for name in names]
                + ["|turn|1"]
                + [f"|move|p1a: {name.title()}|Tackle|" for name in names]
            )

        teams = harvest_teams([R()], evidence=evidence, fallback_abilities={})
        assert teams, "the team should have been buildable"
        holding = [line for line in teams[0].splitlines() if "@ sitrusberry" in line]
        assert len(holding) == 1, f"Item Clause broken: {holding}"

    def test_without_the_shared_set_the_clause_is_broken(self):
        """Guards the wiring, not the logic.

        `taken_items` existed as a parameter for one commit while nothing
        passed it, which is this project's most repeated bug: data tracked and
        never read. If the caller stops sharing the set, this fails.
        """
        evidence = self._evidence()
        rng = random.Random(0)
        loose = [build_set(name, evidence, rng, taken_items=None) for name in ("aaa", "bbb", "ccc")]
        assert all(s and "sitrusberry" in s for s in loose)


class TestAbilities:
    """`|-ability|` announces the ability that is *active*.

    After Trace, Skill Swap or Mummy that is somebody else's, and believing it
    put Pixilate and Fairy Aura on Pokemon that cannot have them.
    """

    def _evidence(self, seen: str) -> dict[str, SpeciesEvidence]:
        record = SpeciesEvidence()
        record.moves.update(["tackle"])
        record.observed_sets.append(("tackle",))
        record.abilities.update([seen] * 3)
        return {"gardevoir": record}

    def test_an_ability_the_species_cannot_have_is_not_believed(self):
        dex = FakeDex({"gardevoir": ("Synchronize", "Trace", "Telepathy")})
        text = build_set("gardevoir", self._evidence("pixilate"), random.Random(0), dex=dex)
        assert text is not None
        assert "pixilate" not in text

    def test_a_legal_observed_ability_is_kept(self):
        dex = FakeDex({"gardevoir": ("Synchronize", "Trace", "Telepathy")})
        text = build_set("gardevoir", self._evidence("trace"), random.Random(0), dex=dex)
        assert text is not None
        assert "Ability: trace" in text

    def test_curated_abilities_fill_in_when_nothing_was_observed(self):
        """Most abilities never announce. Showdown's own competitive sets are
        a better guess than the dex's first entry -- Torkoal runs Drought, and
        the dex lists White Smoke first."""
        record = SpeciesEvidence()
        record.moves.update(["eruption"])
        record.observed_sets.append(("eruption",))
        dex = FakeDex({"torkoal": ("White Smoke", "Drought", "Shell Armor")})
        text = build_set(
            "torkoal",
            {"torkoal": record},
            random.Random(0),
            dex=dex,
            fallback_abilities={"torkoal": "drought"},
        )
        assert text is not None
        assert "Ability: drought" in text


class TestWhatIsRefused:
    def test_a_species_the_corpus_never_saw_move_is_dropped(self):
        """An empty moveset is a Pokemon that can only Struggle, which would
        quietly weaken every team carrying it."""
        assert build_set("mystery", {}, random.Random(0)) is None

    def test_a_team_is_kept_only_when_all_six_can_be_built(self):
        class R:
            log = _log(
                "|poke|p1|Farigiraf, L50, M|",
                "|poke|p1|Torkoal, L50, F|",
                "|switch|p1a: Giraffe|Farigiraf, L50, M|100/100",
                "|turn|1",
                "|move|p1a: Giraffe|Trick Room|",
            )

        # Only two Pokemon on the sheet, and one of them never moved.
        assert harvest_teams([R()], fallback_abilities={}) == []


class TestVariety:
    def test_two_teams_do_not_get_identical_sets_for_a_species(self):
        """Taking the four most common moves globally would make every
        Landorus in the pool the same Landorus."""
        record = SpeciesEvidence()
        record.moves.update(["a", "b", "c", "d", "e", "f"] * 3)
        record.observed_sets.extend([("a", "b"), ("c", "d"), ("e", "f")])
        evidence = {"x": record}
        seen = {build_set("x", evidence, random.Random(seed)) for seed in range(12)}
        assert len(seen) > 1


@pytest.mark.parametrize("seed", [0, 1, 7])
def test_harvesting_is_reproducible(seed):
    class R:
        log = REPLAY

    first = harvest_teams([R()], seed=seed, fallback_abilities={})
    second = harvest_teams([R()], seed=seed, fallback_abilities={})
    assert first == second
