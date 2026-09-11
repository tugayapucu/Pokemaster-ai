# 0047 — Does guessing an opponent's ability help?

**Written before the measurement was run.** Registered 2026-09-12.

## The change

`_known_ability` answered for a species with exactly one legal ability and
returned nothing for anything with a choice. So Rillaboom — in **39.2%** of Reg
M-C teams — was unknown until Grassy Surge fired, though the corpus holds
**2,292 activations of it and no Overgrow**.

The agent may now consult a corpus-derived prior for that gap. A **revealed**
ability always wins over it, and an ability the species cannot legally have is
refused.

## What the prior covers

27 species of the 239 that have a real choice, after three gates: at least 50
appearances, at least 95% of observed activations, and at least 0.5 activations
per appearance. That last one is the important one — it stops a quiet ability
earning a confident prior from five sightings.

The ones that clear it are the loud, decisive abilities: every weather and
terrain setter in the format, plus Intimidate.

| | share of field | prior |
| --- | --- | --- |
| Rillaboom | 39.2% | Grassy Surge |
| Incineroar | 28.7% | Intimidate |
| Salamence | 25.6% | Intimidate |
| Indeedee-F | 22.1% | Psychic Surge |
| Pelipper | 16.3% | Drizzle |

## Design

`evaluate`: the same agent on both sides but for this one flag, over the
harvested M-C pool, agents swapped between the two passes of every matchup on a
shared seed. That is the harness's standard shape and it controls the matchup,
which 0031 put at 93% of outcome variance.

**400 battles, seed 0.** One run.

## Prediction

**Neutral to slightly positive.** The information is real and it is about
species that are everywhere, which argues for a gain. Against that: the loud
abilities are loud *precisely because they announce themselves immediately*, so
in most battles the prior only buys the turns before the first switch-in — and
this project's record on judgement changes is poor. 0010 and 0013 were both
intuitions that measured wrong, and 0043's policy gradient moved the policy and
gained nothing.

I expect a small positive effect that may not clear its own confidence
interval.

## Stopping rule

One run at 400 battles. The result is reported whatever it is, and the flag
ships **only** if the interval excludes 50%. Neutral means the code stays, off
by default, with the number recorded — the same outcome `tenure_boosts` already
has.

## What each outcome means

| result | conclusion |
| --- | --- |
| clearly above 50% | the prior earns its place and goes on by default |
| neutral | the information is real but does not convert. Keep off, record the number, and note that "real information" and "better play" are different claims |
| clearly below 50% | a wrong guess is worse than silence, which would be worth knowing — it would say the scorer handles "unknown" better than it handles "wrong" |
