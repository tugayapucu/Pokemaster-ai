# 0041 — Does a one-turn scorer underprice a move that pays off later?

0040 found the status category priced about right *as a category*, and then
found that the gap it was built to close does not exist: humans use
non-damaging moves on 34.2% of move choices and this agent on 29.6%. The
disagreement is over which one and when, which a scalar cannot move.

The leading untested explanation is structural. The scorer prices **one turn**,
and half the category pays off over several: Reflect lasts five turns,
Will-O-Wisp halves physical damage for the rest of the battle, Calm Mind is
worth nothing on the turn it is used. Scaling a price that cannot see the
payoff amplifies a number rather than correcting it.

| script | what it does |
|---|---|
| `collect.py` | Forks real decision points and rolls out one-slot variants |
| `report.py` | Regret by when the alternative pays off, against a damage control |

```bash
python experiments/0041-delayed-payoff/collect.py delayed.json 400 14
python experiments/0041-delayed-payoff/report.py delayed.json
```

## Design notes

**Candidates differ in exactly one slot**, with the other held at the agent's
own choice, so a difference between two rollouts is attributable to one move
rather than to a pair of them. Variants are taken from the engine's own legal
list rather than constructed, so an illegal pairing cannot be produced.

**Selection and scoring are separated**, as 0039 does it: candidates are chosen
by our scorer, which has not seen the rollouts that then grade them, so nothing
can be picked because it got lucky.

**The control is `damage (now)`.** Those moves have no delayed payoff to miss,
so their regret is the floor -- the part that is just the agent not being a
perfect ranker, which 0038 measured at 57% best-of-four. A delayed class counts
as evidence only if it clears that floor.

**The classes are not score-matched, and the report says so.** A damage
alternative is usually the near-tied second-best attack; a status alternative is
often ranked far below the pick. The mean score gap is printed per class,
because an alternative we scored well below the pick that still performs as
well is a much stronger signal than one we nearly chose anyway.

## Payoff classes

Read off dex fields rather than a hand-kept list, so a move added to the format
is classified without anyone remembering to update this.

```
  damage (now)          324 moves    the control
  heal (now or soon)      7          Roost, Life Dew, Recover
  boost (later turns)    45          Calm Mind, Swords Dance, Charm
  status (later turns)   10          Will-O-Wisp, Hypnosis, Glare
  field (many turns)     25          Reflect, Tailwind, Trick Room, Aurora Veil
  volatile (varies)      34          Substitute, Yawn, Disable, Protect
  other status           55          Parting Shot, After You, Baton Pass
```
