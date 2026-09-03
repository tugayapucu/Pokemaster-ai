# Experiment 0036 — Speed control is priced about right

**Date:** 2026-09-03
**Result: sweeping the price of Tailwind and Trick Room finds nothing, and a pre-registered confirmation closes it.** Five scales from 0 to 8 against the shipped 1.0: none significant. The leading candidate, *never use them at all*, came back **53.4% with p = 0.56** on fresh seeds. The shipped constants stand. This was the last flat constant on a high-frequency action, so the hand-priced action space is now measured end to end.

## Why it looked promising

Every marker that made switching worth re-opening in 0032 was present:

- **flat constants** — Tailwind 45.0, Trick Room 55.0 — standing in for a trade;
- **fitted on human agreement**, the instrument that has misled this project four times, and Trick Room's is explicitly a *cap* because the fit "degenerates from worth this much into always do this";
- **never swept**. 0026 tested only *forcing* them, the strawman that also made redirection look settled;
- the comment justifying their scale still said **"about five turns"** when battles run thirteen — the identical stale assumption that made `SWITCH_HORIZON` worth re-testing;
- carried by **~48% and ~50%** of harvested teams, the highest frequency of anything still priced by a constant.

## The sweep

Both of 0033's lessons were applied before any number was read. The scale is **per-agent**, because as a module global it would be read by both sides and every setting would tie. And the range was checked to **bite** first: usage runs 0.0% at scale 0, 5.8% at the shipped 1.0, and 24.9% at scale 8, so every point changes behaviour.

```
  scale 0.0 (never use it)   28/49  = 57.1%   p = 0.32
  scale 0.5                  22/40  = 55.0%   p = 0.53
  scale 2.0                  39/68  = 57.4%   p = 0.23
  scale 4.0                  73/138 = 52.9%   p = 0.50
  scale 8.0                  88/192 = 45.8%   p = 0.25
```

Nothing significant. Three scales leaned 55-57%, which would put the shipped value in a shallow dip — but they share a baseline so they are not independent, the decided counts are thin, and five scales were tried. That is the configuration that produced 0029.

## The confirmation

One claim, fixed before it ran: **scale 0.0 beats 1.0, p < 0.05**, on fresh seeds. Scale 0.0 because it led the sweep and because it is the simplest shippable outcome — it would say the constants capture nothing useful.

```
  seed 101   16/23 = 69.6%
  seed 211   10/22 = 45.5%
  seed 307   13/28 = 46.4%

  pooled     39/73 = 53.4%   95% CI 42.1%-64.4%   p = 0.56
             50.1% over 4,200 battles, 2,009 matchups tied
```

The seeds disagree in direction, which is what noise around zero looks like. The stopping rule written down beforehand fires: closed, no third attempt.

## The smoke test that would have been a false positive

The 60-battle version of this sweep put scale 0.0 at **85.7%** — every scale beating the baseline, and the leader looking like a large win. It rested on **seven decided matchups**. At full power it is 57.1%, and on fresh seeds 53.4%.

Recorded because the difference between this and 0029 is not judgement but arithmetic: `decided_matchups` was on the output, so seven was visible at the time rather than buried inside "60 battles".

## What this closes

The hand-priced action space has now been swept end to end:

```
  Mega                +10.1              shipped
  switching           57.8% paired       shipped (0032)
  setup / tenure      null               0023, 0025
  redirection         worse when priced  0033
  speed control       null               here
  the evaluator       at its ceiling     0034, 0035
```

**Two wins, both from actions the agent was making wrongly, and neither from better evaluation.** 0035 explains the second half of that: a position is only about 63% of the answer, so there was never a better evaluation to find.

## Not established

- Whether Tailwind and Trick Room are worth *anything*. This shows the shipped constants are not detectably wrong, on a test with 73 decided matchups; it does not show they are right. Scale 0 removing them entirely being indistinguishable from the shipped price is a mildly uncomfortable fact.
- Whether speed control matters more against an opponent that exploits it. 0026's blind spot applies: both sides here share a policy.
