"""Deriving "what ability does this probably have" from the corpus.

The three gates are the whole design, and the third is the one that is easy to
leave out. An ability is only counted when it *announces itself*: Grassy Surge
shouts on every switch-in, Overgrow fires below a third of its holder's health
and may never be seen. So "no Overgrow observed" is on its own almost no
evidence, and a rule built on share alone would confidently assign an ability
to every quiet species in the dex.

What rescues it is the rate. Incineroar shows 2,722 Intimidate activations
across 1,386 appearances -- 1.96 each, which is the switch-in rate. Any
Incineroar running Blaze would add appearances and no activations and pull that
down. The ratio is the evidence; the share alone is not.
"""

from collections import Counter

from champions_ai.data.priors import build_ability_priors, load_priors, save_priors


class _Evidence:
    def __init__(self, appearances, abilities):
        self._appearances = appearances
        self.abilities = Counter(abilities)

    @property
    def appearances(self):
        return self._appearances


def test_a_dominant_loud_ability_earns_a_prior():
    """Rillaboom's case: 2,292 activations over 1,701 appearances, no rival."""
    evidence = {"rillaboom": _Evidence(1701, {"grassysurge": 2292})}
    priors = build_ability_priors(evidence)
    assert priors["rillaboom"].ability == "grassysurge"
    assert priors["rillaboom"].per_appearance > 1


def test_a_species_seen_only_a_few_times_earns_nothing():
    """A clean split over nine appearances is a clean split over nine
    appearances."""
    evidence = {"rare": _Evidence(9, {"someability": 20})}
    assert build_ability_priors(evidence) == {}


def test_a_near_tie_earns_nothing():
    """Two real sets. Guessing between them is worse than not guessing: the
    agent already handles 'unknown', and it handles it correctly."""
    evidence = {"split": _Evidence(400, {"first": 300, "second": 280})}
    assert build_ability_priors(evidence) == {}


def test_a_quiet_ability_earns_nothing_however_clean_the_split():
    """**The gate that matters.** 100% of five observations across 400
    appearances is a fact about how rarely the ability speaks, not about how
    often it is chosen. Without this, every quiet species in the dex gets a
    confident prior from a handful of sightings."""
    evidence = {"quiet": _Evidence(400, {"onlyeverseenfivetimes": 5})}
    assert build_ability_priors(evidence) == {}

    # ...and the same split, loud, does earn one.
    loud = {"loud": _Evidence(400, {"fireseveryswitch": 500})}
    assert "loud" in build_ability_priors(loud)


def test_the_gates_are_adjustable_so_the_thresholds_can_be_argued_with():
    evidence = {"quiet": _Evidence(400, {"rarelyfires": 5})}
    assert build_ability_priors(evidence, min_per_appearance=0.01)


def test_saving_keeps_the_evidence_not_just_the_answer(tmp_path):
    """A file saying `{"rillaboom": "grassysurge"}` cannot be argued with. One
    carrying the counts can be re-read by someone asking why."""
    evidence = {"rillaboom": _Evidence(1701, {"grassysurge": 2292})}
    path = tmp_path / "priors.json"
    save_priors(build_ability_priors(evidence), path)

    text = path.read_text(encoding="utf-8")
    assert "2292" in text and "1701" in text
    assert load_priors(path) == {"rillaboom": "grassysurge"}


def test_a_missing_file_is_not_an_error(tmp_path):
    """The prior is opt-in; an agent without the file behaves exactly as it did
    before there was one."""
    assert load_priors(tmp_path / "absent.json") == {}
