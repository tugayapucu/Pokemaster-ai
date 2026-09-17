# 0060 — Breaking Mega ties toward the Mega: neutral, so off

Run 2026-09-17 against the pre-registration in this directory, which was
committed and pushed (`9b6fb13`) before any battle was played with the setting on.

## What was built

| commit | what |
| --- | --- |
| `5f18d18` | `HeuristicAgent(mega_on_ties=...)`: a Mega joint action that equals the best non-Mega total is taken; the recommender's ranking (`_ranked`) follows the same setting |

## Results

| | prediction | result |
| --- | --- | --- |
| battle decisions differ | 1–5% | ✓ **3.0%** (10 of 335) |
| differing but not a Mega tie | must be 0 | ✓ **0** |
| Megas on the first turn out, setting off | 40–70% | ✓ 63.3% (19 of 30) |
| Megas on the first turn out, setting on | 85% or higher | ✗ **78.8%** (26 of 33) |
| A/B, on against off, 800 battles, seed 60 | 50–54%, likely not clearing | ✓ **404 / 396 — 50.5%**, 95% Wilson [47.0%, 54.0%] |
| matchups decided | — | 26 of 400 |

The corpus figure for players is 88.9%.

## The decision

**The rule is not met** — the lower bound is 47.0%, not above 50% — so
`mega_on_ties` stays **off by default**. The instrument check is clean: every
decision that changed is exactly the one claimed, a Mega taken at an equal joint
total.

## Reading it

**The setting does what it says and barely changes a game across the pool.**
3% of decisions move, and only 26 of 400 matchups come out decided in either
direction. Most Megas in the pool already happen on an attacking turn, where the
forme's stronger move wins outright and no tie arises.

**The miss on timing is the other half of the defect.** With ties broken, 78.8%
of Megas land on the first turn out, not 85%+. The rest are turns where the
scorer rates the non-Mega action strictly higher — a move that is genuinely
better from the base forme *this turn*. A one-turn scorer is right about that
turn and blind to the permanent upgrade it delays, and this change deliberately
does not override it.

**Where it may matter is narrower than the pool.** A Mega whose arrival changes
the field — its ability sets weather or terrain — gains that field only on the
turn it evolves, so a delayed Mega is a turn of the opponent's field instead.
That is a mechanism, not a measurement here; the pool A/B is dominated by Megas
whose arrival changes nothing.

## What is available, and what is not

- `mega_on_ties=True` can be passed to `HeuristicAgent` by any script — local
  scouts included.
- **There is no command-line flag for it yet** in `play`, `position` or `scout`,
  so the shortlist those print still breaks a Mega tie toward the simpler
  action.

## Hygiene

Pool teams only.
