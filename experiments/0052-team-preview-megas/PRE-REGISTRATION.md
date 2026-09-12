# 0052 — Team Preview learns that Pokemon Mega Evolve

**Written before the measurement was run.** Registered 2026-09-12.

## The defect

Team Preview scored every Pokemon as its **base forme**, on both sides.

- **Ours**: a Pokemon holding its own Mega Stone was scored as the Pokemon it
  stops being on its first action. A Mega's whole reason to be brought was
  invisible to the pick.
- **Theirs**: items are hidden, so a species that Mega Evolves 90% of the time
  it takes the field was rated as though it never did.

## What the corpus says

Measured from 3,750 Reg M-C replays off the engine's `|-mega|` line
(`data.priors.build_mega_priors`): 32 species clear 50 appearances. The format
splits in two — Salamence 89% and Golisopod 91% of their appearances, Baxcalibur
77%, Tyranitar 38%, and Excadrill 0% (its sets carry Focus Sash and Air
Balloon, not its stone; checked before it was believed).

And in the harvested pool, **23.8% of teams hold two or more stones**, while
only one Pokemon may Mega Evolve per battle.

## Two changes, measured separately

| | change | kind | flag |
| --- | --- | --- | --- |
| **B** | our stone holders are scored as their Megas; in a selection with several holders exactly one evolves — the one players evolve most often when rates are loaded, otherwise whichever scores best | our items are known: a fact about our team | `own_megas`, **on** |
| **A** | an opponent's cell is its base matchup moved toward its Mega matchup by the species' measured rate | a prior about a hidden item | `opponent_megas`, **off** |

## Instrument checks, before any win rate

Team Preview is decided before a battle exists, so the check needs no engine:
every ordered pair of the first 20 pool teams, 380 previews.

| | B | A |
| --- | --- | --- |
| previews where the precondition holds | our team has a holder | their team has a species with a rate |
| picks that differ | reported | reported |
| picks that differ **without** the precondition | **must be 0** | **must be 0** |

## Predictions

Wide, as since 0049.

| | B | A |
| --- | --- | --- |
| precondition holds | 60–85% of previews | 60–90% |
| picks differ | 15–50% | 5–30% |
| win rate | positive; roughly even odds of clearing its interval | neutral to positive; not expected to clear |

## Design and stopping rules

- **B**: `own_megas` on against off, no rates loaded in either arm, **400
  battles**, seed 0. It ships on correctness; only a result that clears its
  interval *downward* stops it.
- **A**: `opponent_megas` on against off, **rates loaded in both arms** (so the
  choice of which of our holders evolves is identical), **800 battles**, seed 0.
  It turns on only if its interval clears 50% upward; neutral keeps it off.

## Hygiene

Pool teams only. No scouted candidate is used in this experiment, its fixtures
or its write-up.
