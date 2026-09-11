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
