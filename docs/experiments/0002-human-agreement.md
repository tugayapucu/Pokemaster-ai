# Experiment 0002 — Does the heuristic choose what a human chooses?

**Date:** 2026-08-18 (pilot on 3 games; re-measured same day on 50)
**Git commit:** see `git log` for the `feat(evaluation): measure agreement with real human decisions` commit
**Result: Yes, about twice as often as chance** — and the disagreements name one specific, systematic bias.

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
| Data | 50 rated Reg M-B ladder replays, collected 2026-08-18 |
| Rating filter | both players ≥1500 (observed range 1500–1782, median 1589) |
| Decision points | 603, from 350 turns, yielding **1,061 free-choice labels** |
| Features | `data/reconstruct.py`, opponent knowledge limited to the turn |
| Labels | `data/choices.py`, forced replacements and Team Preview leads excluded |
| Baseline | Exact: mean probability a uniform pick from the same action set matches |
| Metric | Per-slot agreement, 95% Wilson interval |

## Result

```
heuristic-v1  418/1061 = 39.4%  (95% CI 36.5%-42.4%)  vs 21.1% random   beats random: yes
random        228/1061 = 21.5%  (95% CI 19.1%-24.1%)  vs 21.1% random   beats random: no

move-only agreement (ignoring which slot the move was aimed at):
heuristic-v1  49.0%
random        38.9%

6.1 legal actions per slot; 38 of 1,099 labels unscorable (3.5%)
```

**`RandomAgent` landing on 21.5% against its own predicted 21.1% baseline is
the check that matters.** The baseline is computed analytically, not sampled,
and a random policy lands where the theory says it should — at both sample
sizes. That validates the measurement before any claim is made with it.

### The pilot was optimistic

The first run, on 3 games and 59 labels, reported **44.1% (CI 32.2%–56.7%)**.
The 50-game figure of 39.4% sits comfortably inside that interval, so nothing
contradicts — but the honest number is ~39%, and the interval narrowed from 24
points wide to 6. Recorded because the pilot number was published first, and a
point estimate from 59 labels was never worth quoting on its own.

## Where the disagreements come from

643 disagreements:

| Category | Count | Share |
|---|---|---|
| Human chose a **status move** we passed over | 237 | 37% |
| **Right move, wrong target** | 102 | 16% |

The status moves the heuristic passed over:

```
protect 90,  tailwind 20,  encore 14,  hypnosis 10,  trickroom 8,
ragepowder 8,  partingshot 6,  recover 5,  swordsdance 5,  bulkup 5
```

### Switching is the larger half, and only visible at scale

Broken out by what kind of action the human took:

```
move labels  :  944, heuristic agreed on 410  (43.4%)
switch labels:  117, heuristic agreed on   8  ( 6.8%)
```

The pilot had exactly **one** switch label, so this was invisible. Followed up
directly:

| | Humans | heuristic-v1 |
|---|---|---|
| Chose to switch | **11.0%** of decisions | **1.7%** |

When a human switched, the heuristic played a move instead 108 times out of
117. **This is not a reconstruction gap:** all 117 switch labels had a matching
switch available in our action set, so the option was there and was not taken.

Notably, when the heuristic *does* switch it agrees 8/18 (44%) — better than
its overall rate. Switching is not scored badly; it is almost never considered.

## The single finding

Protect (90 misses) and switching (109 misses) are the two largest categories,
and they are the same thing: **both are decisions not to attack this turn.**

The heuristic attacks on **98.3%** of turns. Humans attack on **89%**. It has
essentially no model of when *not* to attack, because every action is priced in
expected damage dealt now, and Protect, Tailwind, Trick Room, Rage Powder and
switching all pay off on a *later* turn. Rage Fist is the same problem inverted
— its power depends on hits already taken.

This is a sharper statement of what Experiment 0001 found from the opposite
direction. There, one-turn search was inert because opponent replies were
unknown. Here, the heuristic misses precisely the moves whose value is
deferred. Both point at the same missing machinery — a model of what happens
*next*.

## Caveats, in order of how much they matter

1. **Reconstructed movesets are partial** — 1.91 of 4 moves recovered on
   average — so the agent chooses from fewer options than the human did, which
   inflates the absolute agreement figure. It does **not** distort the
   comparison against the baseline, which is computed on the same reduced
   action set. `random`'s 38.9% move-only agreement is the visible symptom.
2. **Agreement rewards imitation.** The 1500+ filter makes the reference
   competent, not correct.
3. **Mega Evolution is not scored.** A reconstructed observation cannot offer
   it (the enabling item is not published), so it is excluded rather than
   counted as an automatic miss.
4. **3.5% of labels are unscorable** and excluded, mostly moves that could not
   be matched to the reconstructed moveset for that slot.

## Next actions

- **Protect scoring first.** 90 misses, the largest single move-level item, and
  the cheapest to price: unlike Trick Room its value is largely readable from
  the current turn — is this Pokémon likely to be knocked out, and does the
  partner gain from the slot surviving?
- **Then switching**, which is a larger raw gap (109) but needs a notion of
  matchup value the heuristic does not yet have.
- **Fix targeting before adding new scoring terms.** 16% of disagreements are
  the right idea aimed at the wrong Pokémon, which is cheaper than a new
  concept.
- **Re-run this experiment as the regression test for every heuristic change.**
  At 1,061 labels the interval is ±3 points, which is enough to detect a real
  improvement. It is the only metric here that cannot be gamed by changing what
  we compare against ourselves.
