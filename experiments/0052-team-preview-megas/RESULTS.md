# 0052 — Team Preview learns Mega Evolution: ours ships, theirs stays off

Run 2026-09-12 against the pre-registration in this directory.

## What was built

| commit | what |
| --- | --- |
| `52e83db` | `build_mega_priors`: how often each species Mega Evolves once on the field, read off `|-mega|`, the forme taken from the stone |
| `80c7786` | **B**, `own_megas` (on): our stone holders scored as their Megas; one holder per selection evolves |
| `ed4ed15` | **A**, `opponent_megas` (off): an opponent's cell moved toward its Mega matchup by the measured rate |

The rates split the format in two — Salamence 89%, Golisopod 91%, Baxcalibur
77%, Tyranitar 38%, Excadrill 0% — and the zero was checked against the pool
before it was believed: those sets carry Focus Sash and Air Balloon.

## B — our own Mega Stone holders

| | | pre-registered |
| --- | --- | --- |
| previews with a holder on our team | 304 of 380 — 80% | 60–85% ✓ |
| picks that differed | 202 — **53%** | 15–50% ✗ |
| differed without a holder | **0** | must be 0 ✓ |
| own-megas vs base formes, 400 battles | **214 / 186 — 53.5%** | positive, even odds of clearing |
| 95% Wilson | [48.6%, 58.3%] | |

Positive and not clearing. **It ships**, as pre-registered: a Pokemon holding
its own stone does become the Mega, and only a result clearing its interval
downward would have stopped it. It is the largest effect of the four changes
made on 2026-09-12.

## A — an opponent's possible Mega

| | | pre-registered |
| --- | --- | --- |
| previews with a rated species on their team | 342 of 380 — 90% | 60–90% ✓ |
| picks that differed | 190 — **50%** | 5–30% ✗ |
| differed without one | **0** | must be 0 ✓ |
| opp-megas vs opp-base, 800 battles, rates in both arms | **418 / 382 — 52.2%** | neutral to positive, not clearing ✓ |
| 95% Wilson | [48.8%, 55.7%] | |

Neutral. **`opponent_megas` stays off**, by the rule written beforehand.

A limitation found in writing this up and not fixed: every rated species on
the opponent's team is blended at its full rate, though only one of them can
Mega Evolve in a battle. Teams with two stone users are overstated.

## Both pick counts overshot

Half the previews changed their pick under either change, above both bands.
Team Preview is closer to a tie across candidate fours than the predictions
assumed, so a modest change to any row reorders them.

## The integration canary, and why its Team Preview is now pinned

After B, `test_calibration_drift` failed: the mean top-vs-runner-up score gap
fell to 26.1, below its floor of 28. That canary guards the *scale* the win-rate
bands in `recommendation/calibration.py` were fitted on, and its own docstring
says a failure means the scorer moved.

It had not. Re-running the canary's six battles three ways:

| agent | pick | decisions | median | mean |
| --- | --- | --- | --- | --- |
| everything from 2026-09-12 off | (1, 2, 4, 3) | 67 | 25.4 | 38.8 |
| everything except B | (1, 2, 4, 3) | 67 | 25.4 | 38.8 |
| current default | (1, 0, 4, 3) | 57 | 22.0 | 26.1 |

The first two reproduce the canary's recorded numbers exactly, so the day's
other changes moved it by nothing. B moved it only by bringing a different four
— different battles, a different set of decisions — while the in-battle scorer
that produces the gaps was untouched: `own_megas` is read at Team Preview and
nowhere else.

The canary assumed its battles were fixed. A Team Preview change breaks that
silently, and two more are queued. So its Team Preview is now **pinned to
(1, 2, 4, 3)**, the picks its recorded numbers were measured on. Its ranges were
not widened.

## Still not modelled

- A Mega's **ability**. `matchup()` never reads an ability or an item for
  either side, so the forme brings its stats and typing and nothing else.
- For A, the one-Mega-per-battle rule on the opponent's side.

## Hygiene

Pool teams and synthetic fixtures only.
