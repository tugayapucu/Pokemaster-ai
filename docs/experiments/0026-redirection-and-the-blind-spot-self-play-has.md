# Experiment 0026 — Redirection, and the blind spot self-play has

**Date:** 2026-08-31
**Result: redirection is not worth modelling, the way self-play measured it was incapable of telling us that, and four engine-rejection bugs fell out of finding a method that could.** Rage Powder is on 36% of harvested teams and modelled nowhere, which made it look like the next Mega-shaped hole. Against an opponent redirecting at **every legal opportunity**, only **2.0%** of our attacks are diverted, and forcing redirection does not beat the heuristic. The durable finding is methodological: **self-play cannot measure the value of handling an opponent behaviour our own agent does not exhibit.**

## The question, and why the obvious measurement lied

0024 put redirection on the backlog: on 36% of harvested teams, 20% of human battles, and absent from the agent — one passing comment in `legal_actions.py` and no implementation.

In the corpus it is used 0.35 times per battle, in 22.4% of battles, live on 5.0% of turns. Modest, but real.

Then self-play said the ceiling was **zero**:

```
200 self-play battles on harvested teams
  our redirectable attacks   2211
  ...actually diverted          0   (0.00%)
```

Not one attack diverted, ever. That is not a fact about redirection. Our agent rarely picks Rage Powder; the self-play opponent *is* our agent; so nothing redirects and nothing is diverted. The measurement was reporting the agent's own habits back at itself.

**This generalises, and it is the most important line in this document.** Every self-play number in this project shares the blind spot: a mechanic the agent under-uses cannot be shown to matter by playing the agent against itself. Speed control, redirection, Fake Out pressure — anything humans do that we do not — is invisible to the instrument that grades us.

## Measuring it with an opponent that actually redirects

The fix is a scripted opponent: the heuristic, forced to pick Rage Powder or Follow Me whenever one is legal. Not a good player, and deliberately far above the human rate of 0.35 per battle — an upper bound is what a ceiling wants.

```
200 battles against an opponent that always redirects
  turns where it redirected     144/2224 (6.5%)
  our single-target attacks     2255
  ...diverted                     44     (2.0%, 0.22 per battle)
```

**2.0% of our attacks, at an upper bound nobody plays.** Handling *being* redirected cannot be worth much, and that half of the backlog item is closed.

The other half — whether the agent should *use* redirection more — is answered by the same harness, with a control:

```
reported as the HEURISTIC's win rate; below 50% means the scripted agent won

vs always redirects   794/1600 = 49.6%   95% CI 47.2-52.1%   p = 0.76
vs always protects   1478/1600 = 92.3%
```

Forcing redirection is neutral. It was measured four times as the legality
bugs below were fixed, and never moved off the coin flip or reached
significance:

```
                       heuristic wins        note
  1600 battles            52.2%   p = 0.072  before the legality fixes
  1600 battles            52.2%   p = 0.080  repeat
   800 battles            50.4%              seeds split 55.0% / 45.8%
  1600 battles            49.6%   p = 0.76   with every fix in place
```

Two 400-battle halves disagreeing in direction — 55.0% and 45.8% — is what
noise around zero looks like, and is the reason none of the individual runs
should be read as a direction.

The Protect control is the reason to trust the harness rather than the result: the same forcing applied to a move available far more often is punished savagely, so a scripted agent *can* lose badly here. Redirection simply does not move the needle.

**A correction:** an earlier 400-battle run of this put the scripted opponent ahead at 44.8%, and it was reported as a probable finding. It was an underpowered run on a smaller pool. Properly powered it reverses.

## Four rejections, and the one that was diagnosed instead of guessed

Crude scripted opponents explore joint actions the heuristic never picks, and that exercised `legal_actions` in ways nothing had before. Four distinct engine refusals:

```
Can't move: Whimsicott's Protect is disabled
Can't move: Invalid target for Helping Hand
Can't move: Helping Hand needs a target
Can't move: Fake Out needs a target
```

The first three were patched from the error message alone, and **the second was caused by the fix for the first** — two patches fighting each other, which is the signal that the shape was wrong rather than the details. All of them traced to one design flaw: a last-resort branch that bypassed the targeting and legality rules the function already implements, by naming a bare move index.

That branch now re-runs the normal rules with **only the PP filter dropped**. Of the two filters that can strand a slot, PP is the one that can be stale; `disabled` arrives on the engine's own request and is authoritative under ADR 0003.

The fourth was found differently — by dumping the whole slot at the point of rejection instead of reading the message:

```
Tinkaton   moves    fakeout, helpinghand, encore, gigatonhammer
           disabled fakeout, encore, gigatonhammer
           pp       11, 16, 0, 0
Politoed   fainted, in the partner slot
```

Helping Hand was the only move the engine had *not* disabled, so it is the choice the engine expects — but its partner was gone, so our liveness check found no target. Aiming at a foe was refused; naming no target was refused. The partner's slot is now named even with nobody standing in it.

One state dump found in a single run what three rounds of message-reading had not. That is the lesson worth keeping.

## Also fixed: redirecting at nobody

Rage Powder and Follow Me now score **zero with no living partner**. They draw single-target attacks off an ally; alone they do nothing. Falling through to the flat unknown-support value had the agent picking them anyway — one battle in 200 became a fifteen-turn standoff of both sides redirecting at nobody, running to 49 turns.

What a redirect is worth *with* a partner is left deliberately unpriced. This experiment says it is not worth much, and a number we have not earned is worse than admitting ignorance.

## What this settles

- **Redirection is closed as a modelling target.** Defending against it has a 2.0% ceiling at an unrealistic upper bound; using it more is neutral.
- **Self-play has a systematic blind spot**, and scripted opponents are the instrument that sees past it. Cheap to build, and they found four latent crashes as a side effect.
- **Reading an error message is not diagnosing a bug.** Three patches from messages, one of which caused another; one state dump, one correct fix.

## Not established

- Whether other human behaviours we under-use are worth more than this one. Speed control is the obvious candidate — Tailwind and Trick Room are on ~48% and ~50% of harvested teams, and unlike redirection they change every turn that follows rather than one.
- Whether the four rejections were the only ones. All four scripted arms now run clean over 400 battles each, which is evidence and not proof.
