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

### 1. The rest of the unpriced support moves

23 remain of the original 54. They cluster, so each cluster is one job:

```
last-move tracking     Copycat, Instruct, Sleep Talk, Spite
type overwriting       Soak, Forest's Curse, Trick-or-Treat, Magic Powder,
                       Reflect Type
turn-order tricks      After You, Quash, Ally Switch
trapping               Block, Mean Look
one-offs               Baton Pass, Transform, Lock-On, Perish Song,
                       Guard Split, Power Split, Magnetic Flux, Swallow, Teatime
```

### 2. Make the terrain rules consult `is_grounded`

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

### 3. Speed Boost and the weather Speed abilities

What is left in the turn-order residual after Choice Scarf. Chlorophyll, Swift
Swim, Sand Rush and Slush Rush all double Speed under weather we already track;
Speed Boost needs a per-turn counter.

Turn order currently reads **97.7%** on random teams, so this is a small
remainder rather than a gap.

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
