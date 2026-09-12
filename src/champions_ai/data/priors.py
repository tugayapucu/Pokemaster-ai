"""What ability does an opponent's Pokemon probably have?

`_known_ability` answers this today for a species with exactly one legal
ability -- a Mega forme, or one of 42 base formes -- and returns nothing for
anything with a choice. So Rillaboom, in **39.2%** of Reg M-C teams, is
unknown until its Grassy Surge fires, even though the corpus contains 2,292
activations of it and not one Overgrow.

This derives the missing prior **from the corpus** rather than from anybody's
recollection of what is standard, which is the same rule the rest of the
project follows about the engine.

## Why three gates and not one

A naive "take the most-observed ability" would be wrong in a specific and
quiet way: an ability is only counted when it *announces itself*. Grassy
Surge shouts on every switch-in; Overgrow fires below a third of its holder's
health and may never be seen at all. So "zero Overgrow observed" is, on its
own, almost no evidence.

What rescues it is the **rate**. Intimidate fires on every switch-in, and
Incineroar shows 2,722 activations across 1,386 appearances -- 1.96 each. Any
Incineroar running Blaze would contribute appearances and no activations,
dragging that ratio down. A ratio sitting at the plausible switch-in rate is
the evidence that the alternative is not being run.

So:

- **`min_appearances`** -- a species seen a handful of times says nothing at
  all, whatever the split looks like.
- **`min_share`** -- the leading ability has to actually lead. A near-tie is a
  species with two real sets, and guessing between them is worse than not.
- **`min_per_appearance`** -- the reveal guard, and the one that matters. If
  the leading ability fires far less often than once per appearance, its
  dominance is a statement about which abilities are noisy, not about which
  are played.

A prior that clears all three is still only a prior. `_known_ability` prefers
a revealed ability over it always, so one contradicting observation ends it.
"""

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MIN_APPEARANCES = 50
DEFAULT_MIN_SHARE = 0.95
# Once every two appearances. Below that, "no counter-example" is a statement
# about how loud the ability is rather than about how often it is chosen.
DEFAULT_MIN_PER_APPEARANCE = 0.5


@dataclass(frozen=True)
class AbilityPrior:
    """One species' most likely ability, with the evidence that supports it."""

    species: str
    ability: str
    activations: int
    appearances: int
    share: float
    per_appearance: float


def build_ability_priors(
    evidence,
    *,
    min_appearances: int = DEFAULT_MIN_APPEARANCES,
    min_share: float = DEFAULT_MIN_SHARE,
    min_per_appearance: float = DEFAULT_MIN_PER_APPEARANCE,
) -> dict[str, AbilityPrior]:
    """Species id -> the ability the corpus says it almost always runs.

    `evidence` is `harvest.gather_evidence`'s output. Species that fail any
    gate are simply absent, which is what leaves `_known_ability` returning
    None for them -- the behaviour this replaces only where it can do better.
    """
    priors: dict[str, AbilityPrior] = {}
    for species, record in evidence.items():
        appearances = record.appearances
        if appearances < min_appearances or not record.abilities:
            continue
        total = sum(record.abilities.values())
        ability, activations = record.abilities.most_common(1)[0]
        share = activations / total
        per_appearance = activations / appearances
        if share < min_share or per_appearance < min_per_appearance:
            continue
        priors[species] = AbilityPrior(
            species=species,
            ability=ability,
            activations=activations,
            appearances=appearances,
            share=share,
            per_appearance=per_appearance,
        )
    return priors


def save_priors(priors: dict[str, AbilityPrior], path: Path) -> None:
    """Write them with their evidence, not as a bare mapping.

    A file saying `{"rillaboom": "grassysurge"}` cannot be argued with later.
    One that carries the counts can be re-read by someone asking *why*, and
    re-derived when the corpus grows.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        species: {
            "ability": prior.ability,
            "activations": prior.activations,
            "appearances": prior.appearances,
            "share": round(prior.share, 4),
            "per_appearance": round(prior.per_appearance, 3),
        }
        for species, prior in sorted(priors.items())
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_priors(path: Path) -> dict[str, str]:
    """Species id -> ability id, for the agent. Empty when the file is absent.

    Missing is not an error: the prior is opt-in, and an agent without the
    file behaves exactly as it did before there was one.
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {species: entry["ability"] for species, entry in payload.items()}


# Field effects a Pokemon can bring with it, by the id the scorer reads. Split
# because `matchup()` takes weather and terrain separately.
WEATHER_EFFECTS = frozenset(
    {"sunnyday", "raindance", "sandstorm", "snowscape", "snow", "hail",
     "desolateland", "primordialsea"}
)
TERRAIN_EFFECTS = frozenset(
    {"electricterrain", "grassyterrain", "mistyterrain", "psychicterrain"}
)

DEFAULT_MIN_PREVIEWS = 60
DEFAULT_MIN_PROBABILITY = 0.25


@dataclass(frozen=True)
class FieldPrior:
    """Seeing this species at Team Preview predicts this field, this often."""

    species: str
    effect: str
    kind: str
    previewed: int
    established: int

    @property
    def probability(self) -> float:
        return self.established / self.previewed if self.previewed else 0.0


def build_field_priors(
    replays,
    *,
    min_previews: int = DEFAULT_MIN_PREVIEWS,
    min_probability: float = DEFAULT_MIN_PROBABILITY,
) -> dict[str, FieldPrior]:
    """Species -> the field it is likely to put up, measured end to end.

    Deliberately **not** routed through an ability table. The corpus states the
    whole chain in one line --

        |-weather|Sunny Day|[from] ability: Drought|[of] p2a: Torkoal

    -- so "Torkoal means sun" is observable directly, and nothing here has to
    know that Drought exists or what it does. That also means the number is the
    one actually wanted: **P(this field is up | this species was previewed)**,
    which folds in the two things an ability table cannot know.

    The first is that a previewed Pokemon is only brought four times in six.
    Measured on the Reg M-C corpus, a previewed Pelipper reaches the field 70%
    of the time and Rillaboom 64% -- so asserting rain on sight of Pelipper
    would be wrong in three games out of ten. The second is that a setter can
    be beaten to it, or faint before it arrives.

    `min_probability` is deliberately low: a one-in-three chance of rain is
    real information about a matchup, and the caller weights by it rather than
    treating it as certain. What the floor excludes is coincidence.
    """
    from collections import Counter

    from champions_ai.data.split import declared_rosters
    from champions_ai.simulator.tracker import species_from_details, to_id

    previewed: Counter = Counter()
    established: Counter = Counter()

    for replay in replays:
        rosters = declared_rosters(replay)
        if len(rosters) != 2:
            continue
        sides = {"p1": rosters[0], "p2": rosters[1]}
        for roster in rosters:
            for species in roster:
                previewed[species] += 1

        # Nicknames to species, from the switch lines. Needed because the
        # `[of]` ident carries a *nickname*, and for a forme it carries the
        # base name: `[of] p1b: Indeedee` for a Pokemon the roster calls
        # `indeedeef`. Matching the ident against the roster directly dropped
        # every Indeedee-F -- 22% of the field, and the format's main Psychic
        # Terrain setter -- which is the same forme-versus-ident trap that cost
        # this project a Mega exclusion in 0046.
        by_nickname: dict[tuple[str, str], str] = {}
        for line in replay.log:
            if not line.startswith(("|switch|", "|drag|", "|replace|")):
                continue
            parts = line.split("|")
            if len(parts) > 3:
                ident = parts[2]
                side = ident.split(":")[0].strip()[:2]
                nickname = ident.split(":", 1)[-1].strip()
                by_nickname[(side, nickname)] = to_id(species_from_details(parts[3]))

        # Who caused each field effect, and on whose side.
        seen: set[tuple[str, str]] = set()
        for line in replay.log:
            if "[of] " not in line or "|-" not in line:
                continue
            effect = None
            if line.startswith("|-weather|"):
                effect = to_id(line.split("|")[2])
            elif line.startswith("|-fieldstart|"):
                effect = to_id(line.split("|")[2].split(":")[-1])
            if effect not in WEATHER_EFFECTS and effect not in TERRAIN_EFFECTS:
                continue
            source = line.split("[of] ")[-1].split("|")[0].strip()
            side = source.split(":")[0].strip()[:2]
            name = source.split(":", 1)[-1].strip()
            # The ident carries a nickname; the roster carries species. Match
            # on the declared six of that side, which is the only list we have
            # at Team Preview anyway.
            resolved = by_nickname.get((side, name))
            for species in sides.get(side, frozenset()):
                if resolved == species or to_id(name) == species:
                    seen.add((species, effect))
                    break
        for pair in seen:
            established[pair] += 1

    priors: dict[str, FieldPrior] = {}
    for (species, effect), count in established.items():
        total = previewed[species]
        if total < min_previews or count / total < min_probability:
            continue
        best = priors.get(species)
        if best is not None and best.established >= count:
            continue
        priors[species] = FieldPrior(
            species=species,
            effect=effect,
            kind="weather" if effect in WEATHER_EFFECTS else "terrain",
            previewed=total,
            established=count,
        )
    return priors


def save_field_priors(priors: dict[str, FieldPrior], path: Path) -> None:
    """Same rule as `save_priors`: the counts travel with the conclusion.

    `{"pelipper": "raindance"}` cannot be argued with. A file that also says
    1,221 previewed and 825 established can be re-read by someone asking
    whether 68% is enough to act on, which is the whole question here.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        species: {
            "effect": prior.effect,
            "kind": prior.kind,
            "previewed": prior.previewed,
            "established": prior.established,
            "probability": round(prior.probability, 4),
        }
        for species, prior in sorted(priors.items())
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_field_priors(path: Path) -> dict[str, tuple[str, str, float]]:
    """Species id -> (effect, kind, probability), the shape the agent wants.

    `kind` is carried through as the keyword `matchup()` takes it under, so
    the caller never has to re-derive weather-versus-terrain from the effect
    id. Missing file means an empty mapping and the old behaviour exactly.
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {
        species: (entry["effect"], entry["kind"], float(entry["probability"]))
        for species, entry in payload.items()
    }
