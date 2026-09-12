# 0048 — The prediction is real, the picks change, the win rate does not

Run 2026-09-12 against the pre-registration in this directory.

## The instrument check, which ran first this time

| | |
| --- | --- |
| previews compared | 380 |
| with a prior-covered species on the opposing side | 380 |
| picks that **differed** | **122 — 32%** |

**The arms differ.** That is the sentence 0047 could not write, and it is what
makes the rest of this page worth reading. The pre-registration predicted
10–40%; 32% is inside it.

The middle row wants an honest caveat: 380 is every ordered pair of twenty
teams, so "all 380" is really "all twenty of those teams carry a setter", not a
claim about the format. With Rillaboom on 39.2% of teams and Indeedee-F on
22.1%, twenty for twenty is unremarkable rather than suspicious.

## The measurement

| | |
| --- | --- |
| predicting vs bare, 400 battles | **204 / 196 — 51.0%** |
| 95% Wilson | [46.1%, 55.9%] |

**Neutral.** The interval contains 50%, so by the pre-registered stopping rule
it does not ship on: off by default, with the number recorded, alongside
`tenure_boosts` and the ability prior.

This is what the pre-registration said would happen, in the words it said it
in: *"neutral to slightly positive, and I expect it not to clear its
interval."* Writing that down beforehand is the only reason 51.0% reads as a
confirmed prediction rather than as a disappointment.

## What it actually measured, and what it did not

It measured **better-informed picks that do not convert**. A third of previews
now pick a different four, and those fours win 204 of 400 instead of 196.

Team Preview is one decision against roughly twenty in-battle ones, and 0031
put ~93% of outcome variance on the team assignment itself. A change that moves
only the choice of four from six is bounded by that before it starts. The
honest reading is not "the prediction is worthless" but "this lever is small",
and 400 battles cannot separate a small true effect from none.

## The finding that was worth more than the experiment

The A/B could not run at first. `matchup()` had no `terrain` parameter —
**`TypeError: matchup() got an unexpected keyword argument 'terrain'`** — and
pulling that thread found two bugs stacked on each other:

| | |
| --- | --- |
| `matchup()` took a `weather` and no `terrain` | so every score was on bare ground |
| `estimate_damage` fell back to **static** base power | so the terrain 1.3 never applied even once threaded |

The second is the sharper one. Three callers — the in-battle move scorer, the
differential harness, the feature builder — each called `dynamic_base_power`
and passed the answer in. `matchup` passed nothing and got the dex's printed
number. The same Grass move was worth 90 when Team Preview priced it and 117
when the move scorer priced it, **three call sites apart in the same file**.

Neither side was wrong about the rule. One was not asking. Both are fixed in
`1c2ff79` and `a862683`, with 1,384 unit and 115 integration tests passing.

This is the recurring shape again — *the instrument is blind to the effect
being measured* — and it was caught this time because the experiment insisted
on the effect being expressible before it read a number. 0047 found the same
class of bug by accident, after the fact.

## The one still open, and it is bigger than this experiment

`_score_switch_on_matchup` calls `matchup()` with the `observation` in hand
and passes **neither `weather` nor `terrain`**, while the same file threads
`observation.terrain` into six other call sites. Every switch decision this
project makes is scored on a bare field.

That is a decision made many times per battle, against Team Preview's once, so
the lever is the one 0048 says this one is not. It is deliberately not fixed
here: changing the agent's in-battle behaviour mid-experiment would move the
baseline under a pre-registration already written. It is the next item.

## Kept

The machinery stays, off by default: `build_field_priors`, the persisted file,
`HeuristicAgent(field_priors=...)`, and `build.py` so the file is reproducible
rather than the ad-hoc artefact 0047's was. `scout` and `preview` are the
places it is likeliest to earn its keep — a human reading a grid benefits from
"this is scored assuming rain" in a way a 51% win rate does not capture.
