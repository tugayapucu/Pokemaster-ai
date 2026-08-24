# Backlog

Near-term work, in order. `PROJECT_PLAN.md` is the big picture and the record
of what was measured; this is the short list of what happens next.

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

### 1. Target selection

The largest measured gap: **858 of 2,477 missed attacks (35%) are the right
move aimed at the wrong Pokémon** — 9.5% of all labels.

Two causes already eliminated: not focus fire (0011), and not a slot bias
(495 vs 432, near-symmetric). What is left is that the agent rates the two
opponents almost equally and picks near-randomly, while the human had a reason.

**One untested hypothesis:** removing a *dangerous* opponent is worth more than
removing a harmless one, and nothing in the score says so — while
`_incoming_threat` already computes exactly that per opponent and is used only
for Protect.

**Done when** the hypothesis is measured on train and reported on test, kept or
refuted either way.

### 2. Focus Sash and the knockout claim

"Guaranteed knockout" is wrong about **17%** of the time. Focus Sash is the
likeliest cause: it measured at 0.985 for *damage*, meaning it does nothing
there, which is exactly why the damage harness cannot see it. It is a survival
mechanic, so it needs the KO calibration rather than the differential.

**Done when** a "guaranteed" claim is right at least ~90% of the time, or the
remaining error is attributed to something else.

### 3. Ability tracking

Five support moves need it — Skill Swap, Role Play, Entrainment, Worry Seed,
Simple Beam — and `revealed_ability` is already tracked, so this is the same
shape of job as item tracking was.

Expected to be agreement-neutral, like item tracking. It is on the list for
the same reason: the model should describe the game, not the sample.

### 4. The rest of the unpriced support moves

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

### 5. Speed Boost and the weather Speed abilities

What is left in the turn-order residual after Choice Scarf. Chlorophyll, Swift
Swim, Sand Rush and Slush Rush all double Speed under weather we already track;
Speed Boost needs a per-turn counter.

Turn order currently reads **97.7%** on random teams, so this is a small
remainder rather than a gap.

### 6. Grounding

**New, found while wiring `modifies_type`.** Several rules turn on whether a
Pokémon is *grounded*, and nothing models it — a Flying type or a Levitate
user is not:

```
Terrain Pulse       only changes type for a grounded user
Rising Voltage      only doubles against a grounded target
Expanding Force     only boosted for a grounded user
Misty Explosion     same
the terrain damage bonuses   same
```

Each of these currently applies to everyone, so a Flying-type gets terrain
effects it should not. Small individually, and one concept fixes all of them.

**Done when** a `is_grounded` helper exists and every terrain rule consults it.

### ~~7. Critical hits~~ — done 2026-08-24

Folded into expected damage as part of item 1. Deliberately *not* folded into
the range: a crit is a different calculation, not a lucky end of the ordinary
roll. They remain excluded from the differential calibration for the same
reason.

---

## Ruled out, with evidence

Kept here so the same ground is not covered twice.

| Direction | Why it is off the list |
|---|---|
| **Switching** | Three independent failures: a matchup model (0004, reverted as worse), fitting the constants (0012, overfits — train up, test down), and matching the human rate (0012, still 73% disagreement and 1.8 points worse overall). Plus 0005: perfect knowledge of the opponent's move *this turn* makes the agent worse. Hypothesis left is that human switches are plans about the game rather than the turn, which a one-turn scorer cannot express — a different shape of agent, not another constant. |
| **Focus fire / joint targets** | Refuted (0011). The correction was kept only on the narrow ground that a Pokémon can only faint once. |
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
- **Rarity in the corpus is not unimportance.** The corpus is a measuring
  instrument, not the target.
