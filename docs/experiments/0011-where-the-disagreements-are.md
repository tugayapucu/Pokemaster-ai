# Experiment 0011 — Where the disagreements actually are

**Date:** 2026-08-24
**Result: a map, and one refuted hypothesis.** The planned next step turned out to be worth almost nothing, and measuring where the disagreements really are found a gap nine times larger. A fix aimed at that gap was then built, measured, and **did not work** — it is kept only on a narrower argument than the one that motivated it.

## The planned step was not worth taking

The stated next item was the 56 status moves whose effects live in an `onHit` callback the engine cannot dump — and I had named **Belly Drum** and **Haze** as "large swings the agent is blind to".

Counting their actual use across 500 rated replays:

```
54 undumped status moves, 227 uses in total, 37 of them never appear at all

  Parting Shot   152      Instruct      7
  Perish Song     24      Skill Swap    4
  Soak             9      ...rest <= 4
  Strength Sap     9
```

**Belly Drum appears once. Haze twice.** Two thirds of the entire class is one move. The whole category is 227 uses against 11,133 labels — perfect handling would be worth a fraction of a point.

That is the second time in two sessions that importance was assumed rather than measured. So the next step was chosen from data instead.

## The map

Every disagreement on the training half, by what the human did:

```
9,057 labels, 45.66% agreement, 4,922 disagreements

  attack   2485  (50%)      human attack, we attack   1851  (38%)
  status   1488  (30%)      human status, we attack   1020  (21%)
  switch    949  (19%)      human switch, we attack    664  (13%)
                            human attack, we status    593  (12%)
```

And the finding that mattered:

> **Of 2,485 missed attacks, 861 (35%) picked the right move and the wrong target.**

That is 9.5% of all labels, and nine times the size of the entire `onHit` category.

## The hypothesis, and its refutation

`select_action` sums independently scored slots, with the cache keyed by `(slot, action)` — so a slot's score can never depend on what the other slot does. That structurally cannot express **focus fire**: two attacks into one target where the combined damage secures a knockout neither achieves alone. It is also wrong in the other direction: two *guaranteed* knockouts on one target each collected the full bonus, so the agent was rewarded for overkill.

Both were fixed by recomputing the bonus once per target from the combined damage. Then measured:

```
                         train              test
  right move, wrong target   949 -> 945       213 -> 204
  overall agreement      45.66 -> 45.40%   46.68 -> 47.16%
  McNemar                  p 0.238            p 0.261   (halves disagree in direction)
  strength                 pooled 50.56% over 1,600 battles, p 0.65
```

**It barely touches the gap it was built for**, and is neutral on both instruments.

## So what *is* causing it?

Two candidates ruled out cheaply:

- **Not focus fire** — measured above.
- **Not a slot bias.** An agent that always aimed at the first opponent would look exactly like this, so it was worth checking: 495 cases of "human picked foe 1, we picked foe 0" against 432 the other way. Near-symmetric.

What is left is that the agent's choice between two opponents is **near-arbitrary** — its damage estimates for the two are close enough that the tiebreak is noise, while the human had a reason. The obvious untested candidate is that removing a *dangerous* opponent is worth more than removing a harmless one, and nothing in the score says so; `_incoming_threat` already computes exactly that per opponent and is used only for Protect.

That is a hypothesis, and it is recorded as one rather than implemented on the strength of a story.

## What was kept, and why

The joint correction stays, but the argument for it changed. It fires on **2.17%** of joint actions (1,480 overkill, 2,040 focus fire), so it is not dead code — just too rare to move a metric. It is kept because **a Pokémon can only faint once**, so scoring two knockouts of it is a double-count regardless of measurement. That is a narrower claim than the one it was built on, and the only one that survives.

The alternative reading is defensible: it adds complexity for no measured benefit, and this project has reverted a change (0004) for less. If the stricter standard is preferred, it is a one-line revert.
