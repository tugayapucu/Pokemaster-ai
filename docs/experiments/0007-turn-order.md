# Experiment 0007 — Does the agent know who moves first?

**Date:** 2026-08-24
**Result: it did not, and now it does.** The turn-order rule is verified against the engine at **99.6%** of the pairs it commits to. The agent's use of it went from consulting priority for our own move only to reading both sides plus every field effect that reorders a turn. End to end on random teams: **85.0% → 91.0%**. Play strength is unchanged, which was the expectation before the work rather than after.

## Why this, and why now

The damage formula had just been verified to 94.8% (see the plan). Move order was the next thing that decides whether damage happens at all, and unlike most open questions it came with a confession already written into the code:

```python
# Priority settles it when the move has any -- Fake Out's +3 means its
# flinch always lands, while Rock Slide's only pays when we outspeed.
# Opposing priority is not modelled, so this is optimistic for a move
# that could be beaten to the punch.
if move.priority > 0:
    return 1.0
```

Priority is not a modelling choice. It is a static field on every move, dumped from the engine, running **+5 (Helping Hand) to −7 (Trick Room)** in this dex. We had the number the whole time and only ever asked whether it was greater than zero.

## What that one line cost

| What was ignored | Effect |
|---|---|
| Their priority | A Quick Attack we had *watched them use* still scored us as moving first |
| Our negative priority | Everything not above zero read as zero, so Focus Punch, Avalanche, Counter, Dragon Tail and Trick Room were scored as moving first whenever their user was faster |
| Stat stages | Raw Speed, so an Icy Wind or an Agility changed nothing |
| Paralysis | Halves Speed; applied to neither side |
| Tailwind | Doubles it; applied to neither side |
| Trick Room | Reverses the comparison entirely; not consulted |

Every one of those was already on the `Observation`. Two were not, and turned out to be the same silent-data bug the project keeps finding: **`tracker.terrain` was declared, read into every Observation and never once assigned**, and **side conditions were recorded for the opponent only**, so our own Tailwind was invisible to us.

## The instrument

`evaluation/turn_order.py`, built the same way as the damage differential and for the same reason — except more direct: the order the engine resolved moves in **is** the order the `|move|` lines appear in, so there is nothing to infer.

It tests the **rule**, not the prediction. The harness is omniscient and knows what both sides picked. An agent choosing an action does not, and that uncertainty is measured separately — conflating the two is exactly what made the damage residual unreadable for a whole session.

Two parsing bugs had to be fixed before the numbers meant anything, and both were about *when* state is read:

- **The field state is the state at the start of the turn**, because the engine sorts every action once before any of them runs. Reading it when the `|turn|` line arrives got the last turn of *every* Trick Room backwards: the moves were ordered under it, then it expired in the residual phase before the line arrived.
- **A `|move|` line carrying `[from]` is a called move** — Metronome, Sleep Talk — not the action its user chose.

## What it measured

```
random teams, items and abilities        85.0%    (1,131 ordered pairs)
control teams, no items                  93.6%
control, no Speed or priority abilities  97.8%    99.6% of committed pairs
```

The gaps between those three rows are the whole finding, and each is attributable:

- **items** — Choice Scarf, ×1.5 Speed. The backwards cases clustered on Passimian, Toxicroak, Pangoro and Heracross: middling-speed physical attackers, which is exactly who Showdown's generator hands a Scarf.
- **abilities** — 74 of 83 remaining errors were a *Status* move going first. That is Prankster, +1 priority, on seven Pokémon here including Grimmsnarl, Whimsicott, Klefki and Sableye. The rest were Chlorophyll doubling Speed in sun.

A lesson worth keeping: **a control team is a control for one measurement, not in general.** The deny-list built for the damage harness deliberately allowed Prankster and Chlorophyll through, because neither touches damage. Both decide turn order outright.

With Prankster, Gale Wings and Stall modelled, control teams carrying them read **99.0%, with no Status move left among the mistakes at all**, and random teams went **85.0% → 91.0%**.

## What is deliberately not modelled

**Quick Draw** is a 30% chance of +0.1 fractional priority, not a certainty. Folding it into a function that reports priority as a fact would turn a coin flip into one. Only Slowbro-Galar carries it here.

**The opponent's move** is the one genuinely uncertain input, and it is handled explicitly: their priority is the highest we have *actually seen them use*, ability included once revealed, and unrevealed moves are assumed ordinary. That is optimistic on purpose — assuming a priority move nobody has shown would make our own priority moves useless against every Pokémon on the turn it arrives, which is every Pokémon at some point.

## Strength

1,600 paired battles across two seeds, against a copy of the agent carrying the old rule, on the same teams:

```
seed 4242   51.7%   (95% CI 48.3-55.2, not significant)   margin -0.00
seed   99   47.0%   (95% CI 43.6-50.5, not significant)   margin -0.08
```

**Strength-neutral**, with the two seeds disagreeing in direction. The first attempt at this measurement was thrown away: it ran each agent against Random on *independently generated* team pools, so the two numbers were not comparable at all. Paired, same teams, and at the project's own bar of ≥1,500 battles across ≥2 seeds.

That result is the expected one and not a disappointment. `_moves_first` feeds flinch scoring, both agents shared the blind spot, and the project's stated first goal is a correct model rather than a higher win rate. What it changes is whether a recommendation that says *"your flinch will land"* is true — which is a trust property, not a win-rate one.

## What this leaves open

- **Choice Scarf**, and items generally. Now a clean measurement from two directions rather than one.
- **Weather Speed abilities** — Chlorophyll, Swift Swim, Sand Rush, Slush Rush all double Speed under their weather, which we already track.
- **Unburden and Quick Feet**, which need item-consumption and status state respectively.
- **Speed ties** are reported honestly as 0.5 and the engine really does shuffle them, so there is nothing to fix — but 20-88 of every run's pairs are ties, and an agent that treats a coin flip as a plan is making a different mistake.
