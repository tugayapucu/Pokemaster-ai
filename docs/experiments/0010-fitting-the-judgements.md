# Experiment 0010 — Fitting the judgement constants

**Date:** 2026-08-24
**Result: the largest measured gain in the project, and significant on held-out data.** Against the agent as it stood before any status-move work: overall agreement **44.41% → 46.68%** on the test half the sweep never saw (McNemar p = 1.5×10⁻⁴), agreement on status-move slots **36.2% → 47.0%**, and on Protect specifically **46.2% → 60.3%**.

The methodology mattered more than the constants. Two of the fits turned out to be measuring nothing, and one was measuring the wrong thing — none of which is visible in the headline number.

## The setup

Experiment 0009 priced status moves in currencies that already existed (a stat stage, a status, healing). What it could not borrow, it invented: the side-condition, weather, terrain and volatile tables. Those are the only things fitted here, plus Protect's own three constants, which had been hand-chosen in 0003 and never touched since.

Fitting constants on the data you then report them on is how a real gain becomes a fake one, so this uses the corpus split that already existed — hashed by replay id, stable under corpus growth, 405 train / 95 test. **The sweep never saw the test half.** Coordinate descent, one knob at a time, ties going to the incumbent so a knob only moves on evidence.

## What the headline number hid

The first converged sweep reported train 44.13% → 45.72%, test 44.99% → 46.82%. Good numbers. But **seven of thirteen knobs had landed on the edge of their grid**, which means the search wanted to keep going and the reported value was really just "the largest number I offered it".

Sweeping each edge knob far past its grid separated three cases:

```
taunt           PLATEAUS      32:45.70  50:45.72*  90:45.70  160:45.67  300:45.60
unknown         PLATEAUS      12:45.66  30:45.72*  50:45.62   90:45.32  160:45.20
protect_tempo   PLATEAUS     -60:44.51 -160:45.72* -260:44.68 -400:42.44
protect_ko      FLAT            0:45.72*  40:45.71   90:45.57
encore          FLAT           30:45.69   15:45.72*   5:45.72*   0:45.67
leechseed       NO EFFECT      26:45.71   13:45.72*   5:45.72*   0:45.72*  -80:45.72*
trickroom       DEGENERATE     55:45.71  160:45.72  300:45.88*  1200:45.88*  5000:45.88*
```

- **Trick Room is degenerate.** Agreement is still climbing at 5,000 and never stops, because a team that brought Trick Room nearly always uses it. The constant stops meaning *"worth this much"* and becomes *"always do this"*. An agent that recommends Trick Room regardless of the matchup would be wrong in a way human agreement structurally cannot see, so it is **capped deliberately** at a value that remains a valuation.
- **Leech Seed and Encore measure nothing.** Identical agreement across their whole plausible range. The apparent improvements were noise, and both are reverted to where they were.
- **Protect's knockout bonus is flat between 0 and 40.** The fit would set it to zero; it keeps a positive value, because surviving a knockout plainly matters even where agreement cannot detect it.

The remaining fits have genuine peaks and are kept.

## Protect, and a diagnosis that changed the question

Experiment 0009 left Protect looking worse — 45% → 44%. I was about to treat that as a regression to undo. The diagnosis said otherwise:

```
before   agreed on 552/1224 human Protects,  over-protected 651 times
after    agreed on 534/1224,                 over-protected 593 times
```

It lost 18 correct Protects and made **58 fewer wrong ones** — a shift along a precision/recall tradeoff (45.9% → 47.4% precision), not a regression. And in *both* versions, 94–99% of the missed Protects were the agent choosing an attack instead.

So the real problem was older and much larger: Protect's own constants had never been fitted, on the most common status move humans play. Fitted, they say something legible:

```
PROTECT_DAMAGE_WEIGHT   100 -> 430        protect only against a *large*
PROTECT_TEMPO_COST      -20 -> -160       incoming hit, because the turn it
PROTECT_SAVES_KO_BONUS   90 ->  40        costs is expensive
```

That combination has a sharp peak — 44.5% at a tempo cost of −60, 45.7% at −160, 44.7% at −260 — so it is a real optimum rather than a slope.

## Results

```
                      train (9,057 labels)     test (2,076, never swept)
  overall               42.95 -> 45.66%          44.41 -> 46.68%
  status-move slots     31.34 -> 45.51%          36.16 -> 47.04%
  protect only          44.32 -> 57.59%          46.21 -> 60.29%
  McNemar              534 up / 289 down         97 up / 50 down
                        p = 1.8e-17              p = 1.5e-04
```

Both halves agree in direction and magnitude, and the held-out half is significant on its own — which experiment 0009's status tables alone were not (p = 0.19 on test).

## Strength

1,600 paired battles across two seeds, against the agent as it stood before any of this:

```
seed 4242   53.1%   (not significant on its own)
seed   99   52.2%   (not significant on its own)
pooled      52.7%   (95% CI 50.24-55.12%, p = 0.032)
```

**The first change in this project to show any positive strength signal at all.** It is suggestive rather than established: marginal, and it is self-play against a weaker copy of itself, which is the easiest possible test. Every previous correctness fix measured strength-neutral, and the difference here is probably that Protect timing is one of the few things a self-play opponent *can* be punished for.

## A correction to experiment 0009

That experiment reported p = 4.8×10⁻⁵ for the status tables. It was measured over the whole corpus, and nothing had been fitted at that point, so it was a fair measurement — but it included what has since become the training half. The clean held-out read of that same change is p = 0.88 for the hand-picked values and p = 0.19 for the fitted ones. The status tables alone are a small effect that the test half cannot resolve; it is the Protect fit that carries the significance reported here.

## What this leaves open

- **Agreement as an objective degenerates** for any move humans almost always use when they have it. Trick Room is the clear case here; Tailwind may be a mild one. A different objective — win rate, or a held-out margin — would not have this failure, and would have others.
- Thirteen free constants on 4,990 decisions is a lot of freedom. The edge check is the guard against it, and it should be run on any future fit rather than trusting the headline.
- The 56 status moves whose effects live in an `onHit` callback still score a flat value, now fitted to 30 rather than 12.
