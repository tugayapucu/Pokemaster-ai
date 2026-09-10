# 0045 — The forcedness explanation is wrong, and the adviser looks better than expected

Run 2026-09-10 against the pre-registration in this directory. Bands were fixed
before any agreement number existed and were not moved.

## Reg M-B — 31,596 decisions

| options | agreed | chance | **lift** | n |
| --- | --- | --- | --- | --- |
| 1 | 99.3% | 100.0% | −0.7% | 810 |
| 2–3 | 62.7% | 39.1% | **+23.6%** | 5,078 |
| 4–5 | 47.5% | 22.3% | **+25.2%** | 8,607 |
| 6–7 | 38.4% | 15.6% | **+22.8%** | 8,146 |
| 8+ | 32.5% | 11.1% | **+21.4%** | 8,955 |

## Reg M-C — 33,986 decisions

| options | agreed | chance | **lift** | n |
| --- | --- | --- | --- | --- |
| 1 | 96.6% | 100.0% | −3.4% | 961 |
| 2–3 | 61.0% | 39.2% | **+21.7%** | 5,525 |
| 4–5 | 46.9% | 22.4% | **+24.5%** | 9,243 |
| 6–7 | 38.8% | 15.5% | **+23.3%** | 8,884 |
| 8+ | 32.9% | 11.0% | **+22.0%** | 9,373 |

## The instrument check passed

The single-option band exists to catch the measurement lying. With one legal
action the human's choice *is* that action, so agreement must be ~100%.

- **Reg M-B: 99.3%.** Reconstruction loses 0.7% of decisions.
- **Reg M-C: 96.6%.** Reconstruction loses 3.4%.

Both are small enough for the rest of the table to stand. **M-C is five times
lossier than M-B**, which is worth its own look: the likeliest causes are its
35 new species and a 1000-rated corpus using moves the reconstruction has seen
less often. It is not large enough to change any conclusion here.

## Prediction 3 was wrong

The pre-registration predicted lift would **shrink as branching rises** — that
the adviser would match humans mainly on easy positions. It does not. Lift sits
between +21% and +25% in every band, in both regulations, and if anything peaks
in the *middle* rather than at the bottom.

Per the pre-registration:

> lift positive and roughly flat → the adviser's edge is real and uniform;
> 0044's flatness is **not** explained by forcedness and needs another cause.

**So the explanation offered in 0044 is falsified.** Agreement is not flat
across ratings because the decisions are forced. On a position offering eight
or more options — where a coin flip scores 11% — the adviser still lands the
human's choice a third of the time.

## And no rating gap anywhere

| options | weaker half | stronger half | gap (M-B) | gap (M-C) |
| --- | --- | --- | --- | --- |
| 2–3 | +23.9% / +21.8% | +23.3% / +22.1% | −0.6% | +0.2% |
| 4–5 | +25.6% / +24.3% | +24.7% / +24.6% | −0.9% | +0.3% |
| 6–7 | +22.9% / +23.7% | +22.7% / +23.3% | −0.1% | −0.4% |
| 8+ | +21.6% / +20.9% | +21.3% / +22.7% | −0.3% | +1.8% |

Every gap is inside noise, at every branching factor, in both corpora. **0044
was a true null, not an underpowered one** — the weighting item stays closed.

## What this actually changes

**One practical consequence.** Raw agreement is dominated by the branching mix:
62.7% on a 2–3 option decision against 32.5% on an 8+ one. So the headline
"44.7%" is a weighted average over how often this format hands you a hard
position, and **two agreement figures are only comparable if their branching
distributions match.** M-B's and M-C's do, near-identically, which is why 0044's
cross-corpus comparison was safe — but that was luck, not design, and it should
be checked rather than assumed next time.

**And a genuinely positive finding, which is rare here.** The adviser beats a
coin flip by roughly 22 points on open positions, not only on forced ones. Every
previous result about agreement in this project has been a caution — 0010 and
0013 both caught it misleading, and 0044 found it blind to skill. This is the
first that says the ranking carries real information where it matters.

## The question that is now open

If the adviser's edge is uniform and rating carries nothing, why do 1000-rated
and 1800-rated players agree with us equally? Two readings, untested:

1. Our ranking captures something both groups do — the obvious plays are
   obvious at every level, and they are most of the game.
2. The difference between weak and strong play is **not in which action is
   chosen** at all, but in things agreement cannot see: team building, planning
   across turns, risk taken when behind.

Reading 2 would explain every agreement result this project has produced,
including 0010 and 0013. It is also the harder one to test, and nothing here
tests it.
