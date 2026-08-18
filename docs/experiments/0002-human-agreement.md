# Experiment 0002 — Does the heuristic choose what a human chooses?

**Date:** 2026-08-18
**Git commit:** see `git log` for the `feat(evaluation): measure agreement with real human decisions` commit
**Result: Yes, roughly twice as often as chance** — and the disagreements name a specific, fixable blind spot.

## Why this measurement exists

Every result before this one compared agents we wrote against agents we wrote.
`HeuristicAgent` beats `RandomAgent` 96.3%, and `SearchAgent` draws with the
heuristic — but a blind spot shared by all three is invisible to all three. A
rated human's replay is the first outside opinion this project has had.

**Agreement is not strength.** It rewards imitating the reference player, so a
genuinely better move counts as a miss and a human's error counts as the right
answer. It is a signal about whether the agent reasons in the same
neighbourhood as a competent player, and nothing more.

## Setup

| | |
|---|---|
| Data | 3 rated Reg M-B ladder replays (Elo ~1640/1633, ~1637, ~1121/1147) |
| Decision points | 33, yielding **59 free-choice labels** |
| Features | `data/reconstruct.py`, opponent knowledge limited to the turn |
| Labels | `data/choices.py`, forced replacements and Team Preview leads excluded |
| Baseline | Exact: mean probability a uniform pick from the same action set matches |
| Metric | Per-slot agreement, 95% Wilson interval |

## Result

```
heuristic-v1  26/59 = 44.1%  (95% CI 32.2%-56.7%)  vs 21.3% random   beats random: yes
random        12/59 = 20.3%  (95% CI 12.0%-32.3%)  vs 21.3% random   beats random: no

move-only agreement (ignoring which slot the move was aimed at):
heuristic-v1  55.9%
random        40.7%

5.8 legal actions per slot; 0 labels unscorable
```

**`RandomAgent` landing on 20.3% against its own predicted 21.3% baseline is
the check that matters.** The baseline is computed analytically, not sampled,
and a random policy lands where the theory says it should. That validates the
measurement before any claim is made with it.

The heuristic's interval clears the baseline entirely (32.2% > 21.3%), so
"better than chance" is a real finding rather than a favourable reading.

## Where the disagreements come from

33 disagreements, categorised:

| Category | Count | Share |
|---|---|---|
| Human chose a **status move** we passed over | 15 | 45% |
| **Right move, wrong target** | 7 | 21% |
| We chose a status move the human didn't | 4 | 12% |
| Other (different damaging move) | 7 | 21% |

The status moves the heuristic passed over:

```
protect 8,  trickroom 2,  hypnosis 2,  bulkup 1,  followme 1,  perishsong 1
```

**Protect alone is 8 of 33 disagreements — a quarter of them.** What the
heuristic played instead was almost always a damaging move (`wavecrash`,
`rockslide`, `closecombat`, `psychic`).

This is exactly the failure a damage-first heuristic should have, and it is
worth stating plainly: **the heuristic has no model of the future.** Protect,
Trick Room, Follow Me and Perish Song all pay off on a *later* turn, and a
policy that prices only this turn's damage cannot see any of them. Rage Fist
(missed twice) is the same problem in a different shape — its power scales with
hits already taken.

The 21% targeting error is a separate and narrower issue: the heuristic
frequently picks the move a human picked and aims it at the wrong slot.
Move-only agreement (55.9%) minus full agreement (44.1%) is ~12 points of
purely aiming error.

## Caveats, in order of how much they matter

1. **59 labels from 3 games.** The interval is 24 points wide. This establishes
   a method and a direction, not a precise number.
2. **One of the three games is ~1130 Elo**, well below the other two. "Rated
   human" is doing uneven work here.
3. **Reconstructed movesets are partial** — 1.81 of 4 moves recovered on
   average — so the agent chooses from fewer options than the human did, which
   inflates the absolute agreement figure. It does **not** distort the
   comparison against the baseline, because the baseline is computed on the
   same reduced action set. `random`'s 40.7% move-only agreement is the visible
   symptom: with ~1.8 candidate moves, guessing the move is easy.
4. **Mega Evolution is not scored.** A reconstructed observation cannot offer
   it (the enabling item is not published), so it is excluded from the
   comparison rather than counted as an automatic miss.

## Conclusion

The heuristic reasons like a competent player about twice as often as chance,
and where it does not, the reason is consistent and identifiable: **it cannot
value a move whose payoff is on a later turn.**

That is a sharper statement of the same limitation Experiment 0001 found from a
completely different direction. There, one-turn search was inert because the
opponent's replies were unknown. Here, the heuristic misses precisely the moves
whose value is deferred. Both point at the same missing machinery — a model of
what happens *next* — and both say the current bottleneck is knowledge, not
depth.

## Next actions

- **Collect more replays before trusting the number.** Gated on the Smogon
  usage-terms check (`PROJECT_PLAN.md` section 3). A few hundred labels would
  narrow the interval enough to compare heuristic variants against each other.
- **Treat Protect as the cheapest available improvement.** It is a quarter of
  all disagreements, and unlike Trick Room its value is largely readable from
  the current turn: is this Pokémon likely to be knocked out, and does the
  partner benefit from the slot surviving?
- **Re-run this experiment as the regression test for any heuristic change.**
  It is the only metric here that cannot be gamed by changing what we compare
  against ourselves.
- Fix targeting before adding new scoring terms: 21% of disagreements are the
  right idea aimed at the wrong Pokémon, which is a cheaper fix than a new
  concept.
