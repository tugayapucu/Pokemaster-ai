# Backlog

Near-term work, in order. `PROJECT_PLAN.md` is the big picture and the record
of what was measured; this is the short list of what happens next.

**What counts as right.** Two instruments, and they answer different
questions, so the order matters:

- **The engine settles anything with a right answer.** Mechanics, damage,
  turn order, what a move does. This is ground truth and it is exhausted
  first. Every large durable win in this project came from here — damage
  28% → 94.8%, turn order 85% → 97.7%, four separate classes of move that
  read as status moves.
- **Human agreement is a *ranking* signal for judgement calls only** — what a
  stat stage is worth, when Protect beats attacking — because the rules have
  no answer to those. It is never truth. The corpus is 1500–1850 Elo and
  those players make mistakes, so matching them means matching those too.

Agreement has already lied twice and been caught: Trick Room's fitted value
climbed without bound because a team that brought it nearly always uses it
(0010), and target selection looked like the largest gap in the project when
humans themselves are near-random on it (0013). **A measurement that improves
agreement is not on its own a reason to keep a change, and one that does not
is not on its own a reason to drop it.**

**How it is used.** Work starts at the top. If a measurement suggests a
different order, that gets raised and agreed *before* the order changes —
not reordered and reported afterwards. Items leave by being done or by being
ruled out with evidence, and ruled-out items move to the bottom section rather
than disappearing.

---

## Now

### ~~1. Read the fields we already dump~~ — done 2026-08-24

All six wired. It found a real bug, as this shape of check keeps doing:
**the four one-hit knockout moves read as status moves** — the *fourth*
distinct reason a move in this dex can carry a zero base power, after the
per-hit callbacks, the situational multipliers and the damage callbacks.

`modifies_type` was the other substantial one: Weather Ball, Terrain Pulse,
Raging Bull and Aura Wheel were all read on the wrong row of the type chart.

Agreement train 45.36 → 45.42%, test 47.06 → **47.25%**. Damage prediction
holds at ~95% on the control team.

### ~~1. Focus Sash and the knockout claim~~ — done 2026-08-24

**The gap was five times smaller than this said.** Measured against the engine
first, per the rule 0013 earned: the "guaranteed knockout" claim was already
right **98.1%** of the time. The 17% figure came from *replay* calibration,
where the opponent's spread and item are unknown — it was measuring
hidden-information uncertainty, not the knockout logic.

Both causes of the remaining 1.9% were real and are fixed:

```
Focus Sash     leaves the holder on 1 HP, and only from full health.
               Sturdy is the same as an ability. Focus Band is left out:
               a 10% chance at any HP is a coin flip, not a certainty.
Dragon Darts   is multihit 2 *and* smartTarget, so in doubles it fires one
               dart at each opponent rather than two at one. `smartTarget`
               was not dumped at all.
```

Now **99.0%**, with neither cause left among the survivors.

### ~~1. Roost, and the Flying type~~ — done 2026-08-24

Roost strips the user's Flying type for the turn, and it explained the whole
run-to-run swing in the control differential. **That swing was never noise** —
it was whether the random team drew a Roost user.

```
before   90.0% ... 95.0%   depending on team composition
after    96.5%, 97.1%, 98.8% across three runs
```

Typing and grounding turned out to be one question, so item 5 is folded in
here: `is_grounded` exists and knows Levitate, Air Balloon, Iron Ball,
Gravity, Smack Down and Ingrain. The **terrain rules still have to consult
it** — see item 4.

The same silent bug shape appeared for the third time: `-singleturn` was
recorded for the opponent and never for us, so our own Roost was invisible.
Boosts, side conditions, and now single-turn effects.

### ~~1. Abilities~~ — done 2026-08-24

The item said "five support moves need ability tracking". Measuring first
found something an order of magnitude larger: **abilities were the biggest
remaining source of damage error in the whole model.**

```
fully random teams (all abilities and items)     80.1%   ->  92-94%
items on, abilities inert                        92.5%
the control (neither)                           96-99%
```

Values read off the residual before being written down, as Life Orb was:
Huge Power 1.950, Hustle 1.472, Tough Claws 1.243, Iron Fist 1.158,
Adaptability 1.319. Everything else landed inside ±5% of 1.0 — which is **not**
the same as absent, because the median only catches *unconditional*
multipliers. A Multiscale that halves damage one hit in five leaves it
untouched, so the conditional ones are transcribed from the engine instead and
their test is the harness afterwards.

Two process notes worth keeping:

- **Adaptability was missed by the first extraction** because it hangs off
  `onModifySTAB` rather than any stat hook. A search for one hook shape finds
  only that shape.
- **The Dragon Darts split was inert**, and the control harness said so: every
  mismatch in one run was Dragon Darts over-predicted by exactly 2x. The
  harness was passing `spread_targets` as the opponent count, and that is 1
  for a single-target move — which Dragon Darts is, despite reaching both
  opponents. It now counts what actually landed.

The **five support moves** the item was originally about — Skill Swap, Role
Play, Entrainment, Worry Seed, Simple Beam — are still unpriced, and sit with
the rest in item 1 below.

### ~~1. The rest of the unpriced support moves~~ — mostly done 2026-08-24

Fourteen of the 23 are now priced, in four clusters, each its own commit:

```
borrowing another move   Copycat, Sleep Talk, Instruct           (Spite left)
rewriting a typing       Soak, Magic Powder, Forest's Curse,
                         Trick-or-Treat, Reflect Type
buying an ordering       After You, Quash                  (Ally Switch left)
denying a retreat        Block, Mean Look
handing an ability       Skill Swap, Role Play, Entrainment,
                         Worry Seed, Simple Beam
```

Not one of them is priced with a new constant. Each reuses a currency that was
already there — After You is worth the turn our partner would otherwise lose,
Block is worth exactly what we price our *own* escape at, and the retyping and
ability moves are worth the difference between two runs of the damage
estimator. That last trick needed `estimate_damage` to answer "what if they
were this type instead", which is now an explicit `defender_types` override.

**The corpus cannot judge any of this.** Humans picked one of these fourteen
**sixteen times in 500 battles** — seven Instructs and nine Soaks, and none of
the other twelve at all. Agreement moved 45.42% → 45.45% on train and 47.25%
→ 47.30% on test, 3 up and 0 down, which is neither significant nor meant to
be. The verification is **29 tests against the engine's own rules** instead:
`moves.ts` for the failure cases, the move flags already in our dump for what
refuses to be borrowed, the ability flags for what refuses to be handed
around, and `trapped: 3` in the type chart for why Ghosts cannot be trapped.

Three things the corpus *did* catch, all in Instruct:

- **It is usually not the last move that gets repeated.** Instruct is priority
  0 and its users are slow, so the ally has already moved by the time it
  resolves. Reading `last_move` gave the previous turn's move, and it was
  wrong in all seven human Instructs — twice reporting "nothing to repeat" for
  a Torkoal that fired an Eruption in that very turn.
- **Not everything gains from going twice in one turn.** The repeat is
  immediate, so a second Protect is refused and a second Trick Room undoes the
  first. Without that rule the best repeat for one ally came out as its
  Protect, at 310 points for an effect worth nothing.
- **Instruct's target is `normal`, not `adjacentAlly`.** The engine offers it
  across the field, which hands the opponent a free attack.

### 1. Split by team, not only by replay

**An external review raised this and it is right — measured, not argued.** The
split is hashed by replay id, which stops the same *battle* being scored twice
and says nothing about the same **team** appearing in both halves. It does:

```
500 replays: 405 train, 95 test

team roster   80 rosters appear in BOTH halves
              141 of 190 test-side appearances (74.2%) also occur in train
              worst: one roster 26 times in train, 5 in test

player name   78 players appear in BOTH halves
              140 of 190 (73.7%)
              worst: one player 24 times in train, 8 in test
```

So "test" is not measuring generalisation to unseen teams. It is measuring
recall of teams and players already seen 5 to 26 times. **Every agreement
figure this project has reported rests on that**, and the standing rule says a
figure is only as good as the instrument behind it.

It probably has not done much damage *yet* — only about thirteen global
constants have ever been fitted, against 9,057 labels, so there is little
capacity to memorise a particular player. But it makes the one overfitting
result we already have (0012, train up and test down) harder to interpret, and
it would quietly invalidate any learned policy trained on this split.

The job: group by roster before splitting, so a team lands wholly on one side.
Then re-report the agreement numbers and say plainly whether they moved. If
they drop, they drop — the instrument was wrong, not the result.

### 2. Mega: never scored, never measured

Also from the review, and worse than it looked from outside.

Mega is generated as a legal action (`available_specials` in
`domain/legal_actions.py`), tracked (`mega_used`), and reaches the agent. And
then:

- **The heuristic never reads `action.special`.** A Mega and a non-Mega of the
  same move score *identically*, so which one the agent picks is whichever the
  enumeration happens to hand it first. It has no opinion at all.
- **No harness ever Megas.** Every measurement agent filters to
  `special is None`, so the 92-94% damage figure and the 97.7% turn-order
  figure were both measured with Mega switched off. Mega changes base stats,
  ability, and sometimes typing — none of that has ever been checked against
  the engine.

That is the ninth instance this project has found of *state tracked and never
read*, and the first where the unread thing is a whole game mechanic.

The job, in that order: let the differential and turn-order harnesses Mega, see
what the accuracy does, and only then decide what the agent should think about
it. Measure before building, as usual.

### 3. Make the terrain rules consult `is_grounded`

`is_grounded` exists now but nothing calls it. Five rules still apply to
Flying types and Levitate users that should be exempt:

```
Terrain Pulse       only changes type for a grounded user
Rising Voltage      only doubles against a grounded target
Expanding Force     only boosted for a grounded user
Misty Explosion     same
the terrain damage bonuses (Electric, Grassy, Psychic)   same
```

Cheap, and it is the last of the terrain work.

### 4. Speed Boost and the weather Speed abilities

What is left in the turn-order residual after Choice Scarf. Chlorophyll, Swift
Swim, Sand Rush and Slush Rush all double Speed under weather we already track;
Speed Boost needs a per-turn counter.

Turn order currently reads **97.7%** on random teams, so this is a small
remainder rather than a gap.

### 5. The support moves that are still unpriced, and why

Put last deliberately: every one of these is blocked on something we do not
track rather than on effort, so the two items above are worth more per hour.
Kept as an item rather than closed, because "we cannot say" is a claim that
should be revisited, not a permanent verdict.

| Move | Why |
|---|---|
| **Ally Switch** | Its value is dodging an attack aimed at a slot, and which slot they aimed at is exactly what a player cannot see. |
| **Perish Song** | Cuts both ways. Depends on being ahead and on trapping, neither modelled. A first attempt at a number cost three labels. |
| **Teatime** | Everything on the field eats its Berry, ours included — and their Berries are the half we cannot see. |
| **Baton Pass** | Passes boosts to a chosen bench Pokemon. Needs a model of who benefits, which is a matchup question. |
| **Transform** | Becomes the target. Priceable in principle, but the value is next turn's whole moveset. |
| **Spite** | PP is not modelled at all, an opponent's is unknowable, and four PP in a five-turn format is rarely what binds. |
| **Swallow** | Needs a Stockpile counter that nothing tracks. |
| **Lock-On** | Guarantees next turn's hit. Worth the accuracy gap on a move we have not chosen yet. |
| **Wish, Healing Wish, Decorate, Magnetic Flux, Guard/Power Split** | Ally-facing or delayed; the arithmetic is easy and the plumbing to reach the right Pokemon is not there yet. |

Three more — **Trick, Switcheroo, Fling** — are priced already, but only once
the opponent's item has shown itself, which is the same shape as the five
ability moves above.

---

## Reviewed externally, 2026-08-24

A second model was asked to review the repository. Sorted rather than adopted
wholesale, because a reviewer working from the public repo cannot see
`data/replays/` and is reading our descriptions of the measurements rather
than the measurements.

**Accepted, and now items 1 and 2.** Split by team as well as by replay
(measured at 74.2% leakage). Mega mechanics (never scored, never measured).
Both are instrument problems, which is why they went to the top.

**Already the plan, and confirms it.** Terrain and grounding, and the speed
abilities, were already items 1 and 2 and are now 3 and 4. Damage accuracy is
92-94% on random teams and turn order 97.7%, both measured against the engine.
Legal-action generation is engine-reported by ADR 0003 rather than
reimplemented. "Use the exact simulator for counterfactual testing" is ADR
0001. "Avoid RL and large neural models for now" is already the position:
experiment 0006 built a learned linear policy, got +4.2% agreement and a 32.5%
win rate, and it was not wired in.

**Rejected: "defer rare support moves".** This contradicts a standing
instruction, and the reasoning behind it is the disagreement worth stating.
The advice assumes the corpus is the target. It is not — it is a measuring
instrument, and a move absent from 500 games is a fact about the sample rather
than about the game. For a product roadmap the reviewer would be right; for a
correctness roadmap it inverts the priority. The work is done regardless, and
the nine that remain are already parked last, which is where the reviewer
would have put all of them.

**A scope question, not a correction: the team discovery lab.** Evaluating
candidate teams by their *matchup floor* rather than their average is a good
idea and is not currently anywhere in the near-term plan. It is Milestone 13
in `PROJECT_PLAN.md`, and pulling it forward means going ahead of milestones 6
through 11. That is a decision about what this project is for, so it is left
here as a question rather than added to the list.

---

## Ruled out, with evidence

Kept here so the same ground is not covered twice.

| Direction | Why it is off the list |
|---|---|
| **Switching** | Three independent failures: a matchup model (0004, reverted as worse), fitting the constants (0012, overfits — train up, test down), and matching the human rate (0012, still 73% disagreement and 1.8 points worse overall). Plus 0005: perfect knowledge of the opponent's move *this turn* makes the agent worse. Hypothesis left is that human switches are plans about the game rather than the turn, which a one-turn scorer cannot express — a different shape of agent, not another constant. |
| **Target selection** | Mostly a **ceiling**, not a gap (0013). The agent is at 77.5% / 79.7% on genuine two-target choices against a 50% floor, and no computable feature predicts the human's pick better than 57%: more damaged 45.9%, faster 44.6%, more threatening 53.7%, already boosted 57.1%. Scaling a knockout by the target's threat was built and made agreement *significantly worse* on both halves (p 0.0004 / 0.004) while increasing the wrong-target count. Experiment 0011 called this "the largest gap"; that overstated it. |
| **Focus fire / joint targets** | Refuted (0011), and humans do not do it either: over 709 turns where one player attacked with both slots and both opponents were alive, they aimed at the same target 48.1% of the time (0013). The correction was kept only on the narrow ground that a Pokémon can only faint once. |
| **Opponent-knowledge modelling** | Oracle measured at +0.09 points (0005). Flat ceiling. |
| **Learned linear policy** | +4.2% agreement but 32.5% win rate (0006). Not wired in. |
| **Team Preview lead ordering** | No signal: 56.6% → 48.4% against human leads. |
| **Trick Room as a fitted value** | Degenerate under agreement — still climbing at 5,000, because a team that brought it nearly always uses it (0010). Capped deliberately. |

---

## Standing rules earned the hard way

- **Fit on train, report on test.** The split is hashed by replay id and stable
  under corpus growth. A sweep that improves train and degrades test is
  overfitting, and that has already happened once (0012).
- **Check for grid edges.** A knob that lands on the edge of its sweep has not
  converged, and seven of thirteen did (0010). Sweep past the edge to tell a
  real peak from a degenerate objective.
- **A sweep will undo a judgement made for a reason.** The full sweep re-made
  two corrections that had been reverted on principle. Re-check fitted values
  against the edge diagnostics every time.
- **≥1,500 battles across ≥2 seeds** for any strength claim, paired against the
  version being replaced, on the same teams.
- **A search for one hook shape finds only that shape.** Adaptability was
  missed when abilities were extracted by grepping the stat hooks, because it
  uses `onModifySTAB`. Cross-check an extraction against the measured residual.
- **When the corpus cannot judge, the engine must.** Fourteen support moves
  were priced this round and humans picked them sixteen times in 500 battles.
  Agreement moved 0.03 points, which says nothing either way. Twenty-nine
  tests against `moves.ts` say something.
- **Rarity in the corpus is not unimportance.** The corpus is a measuring
  instrument, not the target.
- **Check the size of a gap before trying to close it.** Target selection was
  called "the largest gap" and turned out to be 77-80% against a 50% floor,
  with the rest irreducible (0013). The knockout claim was carried as 83% and
  measured 98.1% against the engine, because the 83% came from replays where
  the opponent's spread and item are unknown. **Twice in a row the stated gap
  was several times smaller than the backlog said** -- measure the ceiling
  first, and with the instrument that removes the confound.
- **A figure is only as good as the instrument behind it.** Replay calibration
  measures the metagame *and* our arithmetic together; the engine differential
  measures the arithmetic alone. Carrying a number from one as though it came
  from the other is how 17% became a headline item.
- **A weak signal implemented as a strong one does damage.** Humans prefer the
  more threatening target 53.7% of the time; weighting that as though it were
  decisive cost significant agreement on both halves (0013).
