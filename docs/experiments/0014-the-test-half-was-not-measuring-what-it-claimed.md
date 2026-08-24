# Experiment 0014 — The test half was not measuring what it claimed

**Date:** 2026-08-24
**Result: every agreement figure this project has reported is optimistic by about four points.** Agreement on player-sides whose team never appeared in training is **43.13%**, against **48.51%** where the team was seen — a 5.38-point gap at **p = 0.041**. The headline test figure of 47.30% sits between them because the test half is 74% contaminated. A clean team-level split turns out to be *impossible* on this corpus, so the leakage is now measured and reported rather than removed.

Raised by an external review of the repository, which recommended splitting "by replay and team where possible". The hedge was well placed.

## The split never separated teams

`data/split.py` hashes the replay id. That stops the same *battle* being scored twice and says nothing about the same *team*:

```
500 replays: 405 train, 95 test
80 rosters appear in both halves
141 of 190 test-side roster appearances (74.2%) also occur in train
worst case: one roster 26 times in train, 5 in test
78 players in both halves — 140 of 190 (73.7%)
```

Player-level leakage was already known and deliberately accepted in that module's docstring — *"reported rather than prevented ... the honest move is to know the number."* Team-level leakage was not, and the number was never surfaced in any result.

## Why the obvious fix does not work

Group replays so a roster lands wholly on one side. Every replay has *two* rosters, so replays chain: A brings X and Y, B brings Y and Z, and now A and B must share a side. On this corpus the chaining runs away.

```
500 replays -> 46 connected components
largest component: 427 replays (85.4% of the corpus)
top ten sizes: 427, 16, 5, 4, 3, 2, 2, 2, 2, 1

a strict team-disjoint test set could reach 14.6% at most
```

And those 73 replays would be the *least*-connected ones — obscure teams, one-off players. The test set would be small and unrepresentative at the same time. A team-level split is not awkward here; it is unavailable.

Subsetting fails too, for the same reason:

```
test replays (95):
  both teams already seen in train : 55
  one team new                     : 38
  both teams new                   :  2
```

Two replays is not a measurement.

## What does work: split the *sides*, not the replays

38 test replays have exactly one new team. Scoring only that player's decisions turns two replays into **42 player-sides and 466 labels** — small, but enough.

```
TRAIN, everything                  45.45%   (9057 labels)
TEST,  everything                  47.30%   (2076 labels)
TEST,  unseen team only            43.13%   ( 466 labels)
TEST,  team seen in training       48.51%   (1610 labels)

two-proportion z-test:  z = 2.047,  p = 0.041
```

This is not perfectly clean — the *opponent's* team may still be familiar. It isolates "we have never seen the team making these decisions", which is the half that matters for an agent meant to handle a variety of teams.

## What it means

**The reported test figure was inflated by roughly four points.** Not by a large margin, and not fatally: only about thirteen global constants have ever been fitted, against 9,057 labels, so there was never much capacity to memorise a particular team. But the direction is exactly what leakage predicts, the effect is significant, and it explains a small oddity that had been left unexamined — test scoring *above* train, which is unusual and is what you would expect if the test half were disproportionately made of familiar teams.

It also makes experiment 0012's overfitting result harder to read, and it would have quietly invalidated any learned policy trained on this split.

**Three consequences.**

1. Agreement figures should be quoted as *the model on teams it has seen*, unless drawn from the unseen-team subset. `CorpusSplit.summary()` now states the contamination so it cannot be quoted unwittingly.
2. **Collecting more replays should prioritise team diversity, not volume.** 500 replays yielded 448 distinct rosters but only 42 usable clean sides. More games from the same ladder population will not fix that; more games from *different* teams will.
3. **For team variety, the engine differential harness is the better instrument and already is one.** It generates random teams, so it has unlimited team diversity by construction, and it is where damage (92–94%), turn order (97.7%) and the knockout claim (99.0%) are measured. Replay agreement measures something narrower than it appears to, and now says so.

## What was not done

The split itself is unchanged. Reshuffling it would invalidate every prior result while fixing nothing — the contamination is a property of the corpus, not of the hash.
