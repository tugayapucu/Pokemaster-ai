# 0045 — Is agreement just a measure of how forced the position was?

**Written before the measurement was run.** Registered 2026-09-10.

## Why

0044 found agreement flat across 800 Elo: 44.7% for 1500–1827 players and 44.6%
for 1000–1341 players. The reading offered there was that agreement mostly
measures **how forced the format's decisions are**, not how well anyone plays
them — a Pokemon with one good attack into one good target has one good move
whoever is holding the controller.

That was explicitly recorded as untested. This tests it.

## The trap this has to avoid

**Raw agreement must fall as options rise, for a reason that means nothing.**
A slot with one legal action agrees 100% by arithmetic. A slot with ten
options would agree 10% by coin flip. Reporting that agreement falls with
branching would be reporting the definition of division.

So the quantity of interest is **lift over chance**:

```
  chance(band) = mean of 1/options across the decisions in that band
  lift          = agreement - chance
```

Lift is what says whether the adviser is doing anything. Every number in the
result table is reported with its chance baseline beside it, and any claim is
made about lift, never about raw agreement.

## The instrument check, done first

Per-slot option counts, over 250 replays of each regulation. "Options" means
distinct actions available to *that slot*, since agreement is measured per slot
decision.

| options | Reg M-B | Reg M-C |
| --- | --- | --- |
| 1 | 2.3% | 2.6% |
| 2–3 | 16.0% | 16.6% |
| 4–5 | 29.4% | 26.3% |
| 6–7 | 26.6% | 25.3% |
| 8+ | 25.7% | 29.2% |

Range 1–14, well spread, and near-identical between regulations. The question
is answerable.

## Bands

Fixed here, before any agreement number was computed: **`1`, `2-3`, `4-5`,
`6-7`, `8+`**. Roughly quarters above the singleton, with chance baselines
spanning 100% down to about 11%.

**The `1` band is a built-in instrument check.** With one legal action the
human's choice must be that action, so agreement there must be ~100%. Anything
lower is not a finding about play — it measures how often reconstruction fails
to contain the move the human actually used, which is a known lossy step. If
that band comes back well below 100%, the rest of the table is suspect and the
run is reported as inconclusive.

## Predictions

1. **Raw agreement falls steeply with branching.** Near-certain and
   uninteresting; stated so it cannot be presented later as a discovery.
2. **Lift is positive in every band.** If it is not, the adviser is not
   beating a coin flip at that branching factor.
3. **Lift shrinks as branching rises.** This is the real prediction and the one
   I am least sure of. If lift is flat instead, the adviser's edge is uniform
   and the 0044 flatness needs a different explanation.

## Crossing with rating

0044's reading also implies the fall should be **the same at every rating**. So
the option bands are crossed with a two-way rating split at each corpus's
median. If lift differs by rating within a branching band, then rating *does*
carry information that 0044's one-dimensional table hid.

## Stopping rule

One run per regulation over the whole corpus. Bands are not moved after seeing
results, and no additional slicing is added.

## What each outcome means

| result | conclusion |
| --- | --- |
| lift positive and roughly flat | the adviser's edge is real and uniform; 0044's flatness is *not* explained by forcedness and needs another cause |
| lift positive but shrinking toward zero as options rise | the adviser matches humans mainly where the position is easy, and the headline agreement figure is carried by forced decisions |
| lift near zero at high branching | agreement is close to worthless as a signal on open positions — the ones that decide games |
| lift differing by rating within a band | 0044 was underpowered rather than null, and the weighting item should reopen |
