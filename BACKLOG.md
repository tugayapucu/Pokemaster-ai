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

**Every named measurement avenue is closed, and for the first time the project
can be run.** The engine work finished at damage 93.9%, turn order 97.8% and
the knockout claim 99.0%; the hand-priced action space was swept end to end;
the value model, richer features and search were each measured and ruled out
on evidence rather than opinion. Two changes ever improved the agent -- Mega
(+10.1) and switching (+7.8) -- and **both were actions it was choosing
wrongly**, not things it needed to know or evaluate better.

So the work changes shape here. There is no obvious next measurement, and
`AGENTS.md`'s rule -- no polished frontend before the decision engine works --
has been satisfied about as thoroughly as it can be. `python -m champions_ai
play` now puts a board, a ranked shortlist and its reasons in front of a human.

**Using it is the new instrument.** Building the terminal client took an
afternoon and immediately found two real defects that forty experiments had
not: benched Pokemon carried stale stat stages, invisible until something
displayed the bench, and the test suite was failing two runs in five. Both had
tests that *looked* like they covered the case.

### An opponent worth measuring against

**0026 found the instrument is blind, not just the pool.** Self-play reported
redirection's ceiling as exactly zero -- 0 of 2,211 attacks ever diverted --
because our agent rarely redirects, the self-play opponent *is* our agent, and
so nothing ever redirects. The measurement was reporting the agent's habits
back at itself.

That generalises to every self-play number here: **a mechanic the agent
under-uses cannot be shown to matter by playing the agent against itself.**
Speed control, Fake Out pressure, redirection -- anything humans do that we do
not is invisible to the thing that grades us.

A scripted opponent fixed it for one mechanic in an afternoon, and found four
latent engine-rejection crashes as a side effect. The item is to make that
routine rather than ad hoc: a small set of opponents that exercise the
behaviours the corpus shows and our agent does not.

Speed control was the first one to point it at, and 0036 closed it: swept 0
to 8, nothing significant, and the pre-registered confirmation came back 53.4%
with p = 0.56. So the item survives its first target rather than being
justified by it. **What is left of it is the general form** -- a small set of
opponents that exercise Fake Out pressure, redirection, hazard and status
pressure, and anything else the corpus shows and our agent does not -- and it
now has no specific mechanic behind it, which lowers it rather than removing
it.

The honest reading of 0036 is that the scripted-opponent theory has been tested
once and did not find anything. That is one test, on the mechanic with the
largest prior. Worth remembering before spending an afternoon on the second.

Not a human-imitation model. 0010 and 0013 are both cases where following the
corpus was wrong, and the point here is coverage of the *action space*, not
copying anyone's judgement.

## Done, most recent first

### ~~An honest number on the shortlist~~ — done 2026-09-04 (0042)

The recommender showed a confidence: a softmax share at a temperature of 12.0
nobody swept. `PROJECT_PLAN.md` said plainly that it is not a win probability
and that a calibrated one "comes from Milestone 7" -- which 0035 and 0037 then
measured and closed. **The route to an honest number had been removed and the
dishonest number stayed on screen.**

0041 supplied a different route. The magnitude of a score gap predicts the real
win-rate difference, so the scorer already produces the input and no value
model is needed:

    under 60        -0.7%     (-4.1% to +1.2%)
    60 to 250       -4.7%     (-6.6% to -2.8%)
    250 and above  -10.2%    (-12.8% to -7.8%)

Held out by battle over eight random splits, correctly ordered on all eight.
Three bands rather than a curve, because the deciles between them are noise at
this sample size, and whole numbers rather than decimals for the same reason.

It refuses to answer where 0041 measured nothing -- a difference spread across
both slots (5.8% of shortlist entries) and an action scored above the pick (7%
of candidates) -- because an unmeasured number on screen is indistinguishable
from a measured one.

**And it immediately said something the old number hid.** On the sample
position all four shortlisted options are inside the band where rollouts find
no difference, where the softmax had shown 19% against 11% and made the top
choice look meaningfully better.

### ~~Which status move, and when~~ — closed 2026-09-04, the pricing is fine (0041)

0040 left two candidates: price Parting Shot on its own, and ask whether a
one-turn scorer can price a multi-turn move at all. Both were answered by one
run of 0038's fork machinery, which prices any move by rollout.

**The multi-turn hypothesis is dead.** `field (many turns)` -- Reflect,
Tailwind, Trick Room, Aurora Veil -- sits exactly on the damage control
(-4.3% against -4.6%, p = 0.947), and `volatile` does too on 263 candidates. If
a one-turn scorer were blind to delayed payoff, those are the classes where it
would show.

**And Parting Shot was an artefact.** It looked like the one class above the
floor at p = 0.016, which does not survive Bonferroni for four classes. Then:
the "class" is 36 Parting Shots out of 39; its sign test is 8 better, 8 worse,
20 tied at p = 1.000; and at matched score gaps the effect is +0.7% at
p = 0.847. The classes were never score-matched -- those alternatives sat 76
below the pick against damage's 184 -- and the column added to catch that
caught it.

**What survives is better than what was looked for.** Regret tracks the score
gap monotonically: -0.5% for alternatives scored just below the pick, -4.3% in
the middle, -9.8% far below, and the same pattern for non-damaging moves. The
scorer's *magnitudes* mean something, which no earlier experiment established.

So 0040's null needs no explanation. The category is priced correctly,
including the half that pays off later, and the low per-move agreement with
humans reflects genuine ambiguity rather than our error.

### ~~Setup and status~~ — closed 2026-09-04, priced about right (0040)

The corpus survey found the disagreement with rated players was a whole
category -- eleven non-damaging moves at 3-8% agreement, on 44 to 449 plays
each. Worth re-opening because the closest existing knob, `tenure_boosts`, is a
**boolean** that 0023 and 0025 measured at two settings, which is the shape
0032 warned about.

Swept as a scalar on the non-damaging branch, per-agent, on a range checked to
bite first (0% to 54% status usage):

    0.0   26.5%  p = 0.0000        4.0   34.1%  p = 0.0003
    0.5   39.0%  p = 0.0278        8.0   15.3%  p = 0.0000
    2.0   44.9%  p = 0.3401

Every alternative at or below even, four of five significantly, in a clean
inverted U with the shipped value at the top. Nothing led, so unlike 0036 there
was no positive claim to confirm.

Turning status off costs 23 points, so the scorer is doing real work and the
shipped weight is near its optimum.

**But the framing was wrong and is corrected in the write-up.** Low per-move
agreement is not a usage gap: humans play non-damaging moves on 34.2% of move
choices against this agent's 29.6%, and it is flat across every rating band the
corpus covers. We reach for the category about as often as they do. The
disagreement is over *which* one and *when* -- and a scalar cannot move that,
which is the better explanation for the null than "humans over-use it".

So the item below replaces it rather than the whole question closing.

### ~~Survey the corpus for where we differ~~ — done 2026-09-04

`review --all` walks all 1,769 replays in ninety seconds. Overall agreement
43.9%, against the benchmark's 45.5% train and 47.3% test, which is the check
that it is wired correctly.

**It found two defects in itself before it found anything about the agent.**
Charge moves never matched in either direction, because a move that is
mid-charge prints no target and the signatures could not be equal -- Electro
Shot read as 361 plays at 0% agreement *and* 416 recommendations at 0%
adoption. `target_unobservable` already existed for exactly this and was not
used. And the switch findings turned out to be mostly the instrument: a replay
reveals only the moves a Pokemon was seen using, 2.34 of 4 on average, and a
Pokemon whose moves are unknown looks harmless, so switching away from it looks
good. The effect is monotone -- 70% at zero moves known, 8% at four -- and with
full knowledge we switch *less* than humans. The survey now prints that table
under the switch rows rather than letting a reader be misled.

**What survives both corrections is a category, not a list.** Humans play
setup, status and utility far more than we rank it: Charm 3%, Disable 4%,
Hypnosis 4%, Will-O-Wisp 4%, Reflect 5%, Substitute 6%, Roost 8%, Calm Mind 8%,
Swords Dance 8%, Yawn 8%, Parting Shot 8%, on 44 to 449 plays each.

Worth holding against it: 0023 and 0025 already measured setup pricing and
found a wash -- in self-play, which 0026 showed cannot see a mechanic the agent
under-uses. The two findings are not yet in contradiction, and separating them
is the obvious next question.

### ~~Team Preview its own screen~~ — done 2026-09-04

Six species against six and nothing else to go on, previously decided for the
player and announced in one line. Now a screen: both rosters, the full matchup
grid, the four we would bring in lead order with a reason each, and the option
to type four numbers instead.

**The grid is the product, not the recommendation** -- `matchup_table` is what
the agent decides from, and a player reading it can disagree on grounds the
agent cannot express. Two caveats are on screen rather than buried: the pick is
chosen for coverage, and the lead order was measured at 48.4% against a 50%
baseline, so the four are advice and the order is a coin toss.

A bug caught by looking at the first render: the grid came out as a field of
-1, 0 and 1, because `matchup().net` runs -1 to +1 with a median near zero and
290 of 432 real values round to zero at whole-number precision. Now -100 to
+100.

**Third time in two days that using the thing found what testing it did not.**

### ~~Review a real game~~ — done 2026-09-04

`python -m champions_ai review` walks a replay and puts the board the player
saw, what they pressed, and our ranked shortlist side by side. The human's
action is located *in* our ranking rather than scored pass/fail -- "our #3" is
a different kind of disagreement from "not in our shortlist".

It says outright that a disagreement is not a verdict, and everything excluded
is counted rather than dropped: leads and forced replacements are reported
separately, and labels reconstruction cannot express are reported as
uncomparable.

Two rendering bugs found by reading the output rather than by a test: the log
names the actor only by nickname, so a turn read "Try me: Fake Out" with no way
to tell which of four Pokemon acted, and a self-targeting move rendered as
"Tailwind -> After Me".

**Second time in two days that using the thing found what testing it did not.**

### ~~Switching~~ — shipped 2026-09-03, the first agent win since Mega (0032)

A small amount of matchup-based switching beats the flat cost: 56.1%, 57.8% and
55.4% across three independent seed sets, the middle one pre-registered.
`SWITCH_HORIZON = 2.0` and `matchup_switching` on by default.

The question had been answered wrongly three times because every attempt tested
a single horizon. The curve is monotone and crosses even between 2 and 4, so
0004 and 0027 were both measuring a real effect at the wrong point. Optimal
switch rate 4.4%, against the flat cost's 0.27% and rated humans' 11.8% --
**both ends were wrong**, and calibrating to the human rate was the specific
error.

The generalisable lesson: **sweep the parameter, do not sample it.** Tenure
setup, redirection and the richer evaluator were each tested at one or two
settings, on the old harness, and each was called a null.

### ~~Make it usable~~ — done 2026-09-04, and it found two bugs

`python -m champions_ai play` prints the board, the movesets and a ranked
shortlist with reasons, and lets you take one or disagree. Advice comes from
`Recommender`, which shares the agent's scorer, so what it suggests is what it
would play. Teams come from a Showdown export file or the frozen pool;
`--seed` fixes both the draw and the battle.

`cli/board.py` reads from `Observation` and nothing else, which makes it
structurally unable to show a player something they are not entitled to see --
the opponent's bench is a count there, so it prints a count.

**Two real defects fell out of building it**, neither of which forty
experiments had surfaced: benched Pokemon carried stale stat stages on both
sides (only visible once something displayed the bench), and the suite was
failing two runs in five because the fork tests compared Showdown's wall-clock
`|t:|` line. Both had existing tests that looked like they covered the case --
`test_boosts_accumulate_and_clear_on_switch_out` switched a Pokemon out *and
back in* before asserting, so it only ever tested arrival.

**Using the thing finds what testing the thing does not.**

### ~~Build the search, or decide not to~~ — closed 2026-09-03, it needed the oracle (0039)

0038 measured a one-ply search at +1.4 points and named its own largest
uncontrolled factor: the search was handed the opponent's actual move, and a
real one has to guess. The backlog said measure that before building anything.
Measured, and the whole effect was the oracle:

    search chose the agent's own action     210   (73%)
    search chose something different         76   (27%)

                                     all points   where they differ
    the agent's own pick                  48.1%              44.0%
    guessed-opponent search               48.2%              44.6%

    ahead 27  behind 25  tied 24     p = 0.7815    NOT CONFIRMED
    noise floor, same action twice:  mean 5.7%, sd 8.8%

**The guesser is not the excuse.** At 39.0% per slot against a 30.5% floor it
beats a model that knows nothing by nine points, and recovers none of the gain.
The reason is structural: a one-ply search needs the opponent's whole *turn* to
step the engine, and 39% per slot compounds to **8.4%** jointly. Doubles makes
opponent modelling exponentially harder in exactly the place a search spends it.

**Milestone 11 is closed on much better grounds than 0022's.** 0022 found the
lookahead inert and nine points worse when woken, and left the reason as a
hypothesis. The reason is now measured.

It also resolves the contradiction with 0005, which found perfect knowledge of
the opponent's move *this turn* made the agent worse. That information went
into the heuristic's scorer in the wrong currency; 0038 put it into an engine
fork where it cannot be mispriced and it was worth +1.4. Both were right --
and it is unobtainable regardless.

One route survives and is not tested: **scoring candidates against a
distribution of opponent replies rather than a single guess.** That is the
standard answer to simultaneous moves, and the only design that could work at
8.4% joint accuracy, because it never needs the single right answer.

Kept from the work: the engine fork itself (`replay(..., stop_after=k)` plus
`reseed`), which is general infrastructure and now has tests.

### ~~Richer features, or nothing~~ — closed 2026-09-03, they do not move it (0037)

0035 left one door open: the aggregates discard species, movesets, items and
matchup entirely, so maybe the ceiling was a property of the *view* rather than
of the game. `mechanics.matchup` is that view, and it already existed. Twelve
matchup features added to the twelve aggregates, same two probes as 0035:

    shipped evaluate_position    64.2%
    aggregates only              63.5%
    matchup only                 56.0%
    aggregates + matchup         64.5%
    bucket-oracle ceiling        63.1%   (was 62.7%, now at 82% coverage)

**+1.0pp, and +0.4pp on the ceiling.** The pre-registered bar -- clear 62.7% by
enough to justify building a model on top -- is not cleared, and it was written
down before the run.

Two things worth keeping. **Matchup alone is 56.0%**, far below aggregates
alone: how much health each side has left tells you more about who wins than
what the actives can do to each other. And the hand-written four-term
`evaluate_position` trails the best fitted model by 0.3pp here and 0.6pp in
0035, inside the split-to-split spread both times -- it has never been beaten
by anything fitted.

**The value-model line is finished, and with it the last named item in this
list.** What is not ruled out is a learned *representation* -- embeddings over
species and moves rather than hand-crafted features -- and the ranking task
rather than the prediction one. Both are new directions, not continuations.

### ~~Speed control pricing~~ — closed 2026-09-03, priced about right (0036)

The last flat constant on a high-frequency action, and it carried every marker
that made switching worth re-opening: flat, fitted on agreement, never swept,
tested only by a strawman, and justified by an "about five turns" comment when
battles run thirteen. On ~48% and ~50% of harvested teams.

Swept 0 to 8: nothing significant. The leading candidate -- never using them at
all -- was pre-registered and came back 53.4%, p = 0.56, with the three seeds
disagreeing in direction.

Its 60-battle smoke test had said 85.7%, on seven decided matchups. Visible at
the time because `decided_matchups` is now printed, which is the whole point of
that guard.

**The hand-priced action space is now swept end to end.** Two wins (Mega,
switching), both from actions the agent was making wrongly; nothing from better
evaluation, which 0035 explains -- a position is only ~63% of the answer.

### ~~A learned value model~~ — ceiling measured 2026-09-03, ~1pp of headroom (0035)

Measured the ceiling instead of building the model. Winner prediction from a
position saturates at ~63% and the hand-written evaluator is already there, so
Milestone 7 as specified is not worth the work. Superseded by the richer-feature
question above, which has its own ceiling to measure first.


### ~~Sweep the evaluator's extra terms~~ — done 2026-09-03, no rescue (0034)

0032's lesson said sweep before believing a null. Swept, the scale curve peaks
at roughly where 0030 already tested:

    scale 0.25  +0.28pp    scale 2.0  +0.57pp
    scale 0.5   +0.53pp    scale 4.0  -0.95pp
    scale 1.0   +1.00pp    scale 8.0  -2.87pp

So 0030 sampled the best available point -- unlike 0027, whose answer changed
sign at settings nobody had tried. The gain is small and not stably estimated:
the same computation over the same data gives +0.2pp with 8 splits and +1.00pp
with 24, and repeated CV folds are not independent so the usual standard error
does not apply.

Nothing ships. `evaluate_position` has no production caller, so it matters only
if search is re-opened.

**Sweeping is not a universal rescue** -- worth recording, since it worked
spectacularly for switching and did nothing here.

### ~~Redirection, priced~~ — closed 2026-09-03, it loses (0033)

0026 called redirection a null from a strawman test. 0032's lesson said sweep
the price first. Swept on the fixed harness, priced against the shipped
unpriced agent:

    weight  4   23.5%  p = 0.029      weight 16   24.0%  p = 0.009
    weight  8   25.0%  p = 0.025      weight 32   26.7%  p = 0.011

Negative everywhere, with and without a tempo cost for the turn it spends. A
stopping rule was written down before the second run and fired.

The ceiling matters as much as the sign: pricing it at all only changes 17-31
matchups in 798, so even a version that worked is worth about a point. Not
where the remaining value is.

Two bugs found in the measurement, both worth remembering: a module-global
weight made both agents priced and tied every matchup, which reads exactly like
a null; and the first sweep ran across weights 0.5-2.0, where the parameter
does not change behaviour at all.

### ~~An evaluator that can price more than HP~~ — ruled out 2026-09-01 (0030)

Adding status, boosts, screens, Tailwind and Trick Room to `evaluate_position`
is worth **+0.2pp** of winner prediction, sd 1.4, positive in four of eight
splits over 19,035 human positions. The weights are well determined and
sensible -- a slept Pokemon prices at about three quarters of a Pokemon -- and
they are simply redundant once HP and living count are known.

0029 reported +3.0/+4.4 from a single split and was wrong; 0030 records that,
and that this is the third time this project has published from an
underpowered run after writing down the lesson (0003, 0004, now 0029).

The stopping rule agreed before the work fires here: improve the evaluator
first, re-test search second, stop if the first does not move. It did not move,
so **search is not re-opened on this basis**.

What survives: self-play cannot measure evaluator features either (screens are
non-zero in 0.0% of self-play positions and 7.8% of real ones), so human
positions are the instrument for this class of question.

### ~~Switch more, like humans do~~ — ruled out 2026-08-31, it costs games (0027)

The agent switches on **0.3%** of free decisions against a human **11.8%**, the
widest behavioural gap left in it, and `_score_switch` gives no credit at all
for the matchup a switch buys. Experiment 0004 built the matchup version and
reverted it on the old pool; 0027 restored it and re-measured on harvested
teams:

    horizon 8.0 (matches the human rate)   46.4%   p = 0.004
    horizon 4.0                            48.4%   p = 0.21

Both below even and monotone -- more switching is worse. The 0.3% rate is right
for this format, and human agreement was the wrong target for the third time
(after 0010's Trick Room and 0013's targets).

Kept behind `matchup_switching`, default off. Found on the way:
`legal_switch_actions`, because replacing a fainted Pokemon was crashing on
move data it never needed.

### ~~Redirection~~ — ruled out 2026-08-31, ceiling is 2.0% (0026)

Rage Powder on 36% of harvested teams and modelled nowhere looked like the
next Mega-shaped hole. Against an opponent redirecting at *every* legal
opportunity -- far above the human rate of 0.35 a battle -- only **2.0%** of
our attacks are diverted. Forcing redirection is neutral against the heuristic
(52.2%, p = 0.072), while the same forcing applied to Protect loses 92.3%,
which is the control that says the harness can detect a bad policy.

Kept from it: redirection now scores zero with no living partner (it drew
attacks off nobody, and one battle in 200 became a fifteen-turn standoff), and
four engine-rejection bugs in `legal_actions` are fixed. What a redirect is
worth *with* a partner is deliberately still unpriced.

Kept rather than deleted: several of these are refutations, and the
evidence for *not* doing something is as easy to lose as the evidence for
doing it.

### ~~Give search the evaluator it does not use~~ — tried, and it is not one change (0022)

Two findings, one good and one uncomfortable.

**The lookahead was inert.** `SearchAgent._threats` counted only *revealed*
damaging moves, so the retaliation term had a **median of exactly zero** across
404 decisions and changed the chosen action 9.4% of the time. More than half
the time the search was the heuristic wearing a hat.

0001 diagnosed this correctly and its fix — assume a standard STAB attack from
an opponent that has revealed nothing — was written into
`HeuristicAgent._threat_from` and **never applied to the search**. That also
explains why 0001's recorded reason ("opponent knowledge is the bottleneck")
sent 0005, 0018 and 0019 all looking for value in opponent knowledge: the
diagnosis was nearly right and the actionable form of it landed in the wrong
module.

**Waking it up made the agent significantly worse.**

```
median |lookahead|   0.0 -> 27.6      decisions changed  9.4% -> 18.2%

seed 1   336/800  = 42.0%
seed 7   320/800  = 40.0%
pooled   656/1600 = 41.0%   (95% CI 38.6%-43.4%)   p < 0.0001
```

Reverted. A baseline nine points worse for an unfixed reason is not a useful
baseline.

The likely cause is the currency mismatch: `immediate - threat * exposure`
subtracts position-value units from the heuristic's fitted action score. While
the threat was zero that was harmless; live, it is a mis-scaled penalty, and
too large a penalty makes an agent over-buy Protect and switching against a
threat it is assuming rather than seeing. Same direction as 0005's finding that
perfect knowledge of their move *this turn* made the agent worse — **correct
information, wrongly priced, hurts.**

### ~~Does the position evaluator predict the winner?~~ — yes, 79.7% (0021)

```
turns 1-2   71.0%      slim   (<50)     66.1%
turns 3-5   81.0%      clear  (50-150)  82.7%
turns 6-9   85.7%      large  (>150)    86.2%
overall     79.7%
```

Well calibrated — monotone in its own confidence, which is the property search
actually needs and not one a hand-written function was guaranteed to have.

**A bias fixed on the way.** Unrevealed opponents scored 100 while one of ours
at full health scored 140, so a dead-even turn-one board read **+80 in our
favour**. A Pokemon that has not been sent out is at full health. Fixing it
took 77.6% → 79.7%, and slim advantages 59.8% → 66.1%.

**And a flaw in the measurement that would have inverted the conclusion.** The
first run reported turns 1–2 at 43.7% — worse than a coin flip on n=900 —
because battles were paired without exchanging teams, so player 0 held one side
of every matchup. `evaluate` does the exchange by construction; a hand-rolled
loop has to remember.

### ~~Infer stat spreads from the damage~~ — done 2026-08-25. It works and it does not matter

Experiment 0019. The inference is real; the effect is not.

```
against the true spreads (only the engine can grade this)
  flat prior (11 everywhere)   mean error 16.0 points
  inferred from damage         mean error 14.7 points

head-to-head, concentrated pool, 800 battles x 2 seeds
  pooled   813/1600 = 50.8%   (95% CI 48.4%-53.3%)   p = 0.516
```

Predicted flat before running — 8% of the distance to truth, against 0018's
+3.6-point ceiling, is roughly +0.3 — and flat is what it is.

**Three structural reasons it cannot easily do better**, all of which would
have to change together: the observations are scarce (111 stats across 200
battles, because strict attribution is the only thing keeping wrong beliefs
out), each one is noisy (±7.5% from the damage roll alone, before an unknown
item shifts it), and no dataset outside the engine can grade a spread.

One thing worth keeping from the build: the first estimator walked 45% toward
each observation and **never travelled far enough from its starting guess to
beat it** (15.4 against a 16.0 prior). Taking the mean of the implied values
instead roughly doubled the improvement. An estimator can be too timid to be
worth having.

The code stays, `infer_spreads=False` and named as unused. 0018's ceiling is
real and a materially better inference could still claim some of it; what is
dead is *this* inference and the assumption that damage alone is enough.

### ~~Spend the belief where it changes a decision~~ — moot

The belief is not good enough to spend. Reading it into `_threat_from` and the
knockout claim would propagate a 14.7-point error into two places that
currently carry a 16.0-point one, for no measurable gain.

### ~~Measure the ceiling first~~ — done 2026-08-25. It is +4.3, and it is all spreads

Experiment 0018. The oracle knows the opponent's spread, item and ability
exactly, measured on win rate over 1,600 battles across two seeds.

```
generator's own spreads     811/1600 = 50.7%   (95% CI 48.2%-53.1%)   flat
concentrated spreads        869/1600 = 54.3%   (95% CI 51.9%-56.7%)
difference between arms     z = 2.05,  p = 0.040
```

**The first run nearly lied, and the reason is worth keeping.** Showdown's
generator hands out `(11, 11, 11, 11, 11, 11)` to 49 of every 72 Pokemon —
*exactly* what `assumed_opponent_points = 11` already assumes. The agent was
already right about the whole test population, so the spread half of the oracle
was inert and the run silently measured item and ability knowledge alone. The
pool was the blind instrument this time, not the harness.

Rewriting every spread into a competitive shape (32 into the attacking stat, 32
into Speed, revalidated through the engine) moved the mean max-min gap from 2.8
to 32.0 and the answer from flat to significant.

**It decomposes cleanly, and not the way this list assumed:**

```
item + ability knowledge      ~0 points     the flat arm is 50.7%
spread knowledge             ~3.6 points    the difference between arms
everything together          +4.3 points
```

So `_known_ability` and the item-gated moves — which this backlog cited as the
motivation — are *not* where the value is. Spread inference is.

**And the honest scale**, on the same instrument and the same bar:

```
scoring the Mega forme (one afternoon)      +10.1 points
perfect opponent knowledge (a milestone)     +4.3 points
```

The entire ceiling is less than half of what one afternoon's mechanical fix
delivered. Worth doing, worth doing *scoped*, and worth having measured before
committing rather than after.

### ~~The support moves that remain unpriced~~ — done 2026-08-25

Seven more priced. **Twenty-two flat down to fifteen**, and of those fifteen,
eight resolve the moment an ability or item shows itself — leaving **seven**
genuinely unpriced against **four** groups of reason.

```
Swallow        the Stockpile count was already a tracked volatile --
               the engine announces `|-start|...|stockpile1`
Wish           `slot_condition: "Wish"`, a delayed half-bar heal
Healing Wish   the health somebody on the bench gets back, minus the
               health we throw away making it
Guard Split    averaging two stats: a pure transfer, worth doing exactly
Power Split    when theirs are higher than ours
Magnetic Flux  +1 Def/SpD, and only to an ally with Plus or Minus
Lock-On        the accuracy gap on whichever of our moves stands to gain
```

**Two come out negative and are left that way.** Swallow hands back six
defensive stages to heal one health bar; Healing Wish faints its user. Both are
honest readings of the currency, the same call this project already made for
Rest — and the one case neither can see is a Pokemon about to be knocked out,
which a one-turn scorer has no way to express.

**A latent crash was found on the way.** The Struggle fallback added earlier
today returned `MoveAction(move_index=0)` when every move was spent — and a
reconstructed replay knows only the moves it actually saw used, so a Pokemon
can have an empty list and index 0 points at nothing. It never showed against
the engine, only against replays. Fixed at the source and guarded in the
scorer.

No regression from rewriting `_boost_value`, which every Swords Dance and Growl
goes through:

```
                        before    after
TRAIN                    45.45%  ->  45.46%
TEST                     47.30%  ->  47.45%
TEST, unseen team only   43.13%  ->  43.56%
```

### ~~The support moves that are still unpriced~~ — worked 2026-08-25

Opening this found something the item did not claim: **six moves were not
unpriceable, they were scored wrong.** `_boost_value` had two branches, "us"
and "them", and counted only rises on our side and only drops on theirs. Every
move that hands a *positive* boost to somebody who is not the user fell
through:

```
Decorate       normal        {atk +2, spa +2}    for an ally
Coaching       adjacentAlly  {atk +1, def +1}    for an ally
Aromatic Mist  adjacentAlly  {spd +1}            for an ally
Swagger        normal        {atk +2}            for an opponent
Flatter        normal        {spa +1}            for an opponent
Spicy Extract  normal        {atk +2, def -2}    for an opponent
```

Decorate is one of the strongest support moves in doubles and took the flat
unknown-support value. Swagger's +2 Attack to an opponent — the price paid for
the confusion — cost us nothing at all.

Stages are now scored against **whoever receives them**, and whatever the move
inflicts follows the same rule: aiming Swagger at our own partner buys the
Attack *and* the confusion, and the confusion is ours. Decorate reads +48 at an
ally and −48 at an opponent; Swagger is a near-wash either way, mirrored.

### ~~Whether the agent should Mega at all~~ — done 2026-08-25

It never did. Measured before touching anything: **offered 84 times across 60
battles, chosen 0 times.** `action.special` was unread, so a Mega and a
non-Mega of the same move scored identically, and `max` returns the first of
equal maxima while the enumeration puts `None` first. The mechanic was thrown
away entirely, in a format where 149 of 150 generated teams carry a stone.

A Mega action is now scored **as the Mega forme** — its stats, its ability, its
typing — so the damage model decides. No "Mega is good" constant was invented;
the model already knows what 40 base Attack and a new ability are worth.

```
paired head-to-head, teams exchanged, 800 battles x 2 seeds

  seed 1   488/800 = 61.0%   (95% CI 57.6%-64.3%)
  seed 7   474/800 = 59.2%   (95% CI 55.8%-62.6%)
  pooled   962/1600 = 60.1%  (95% CI 57.7%-62.5%)
```

**A data fix was needed first.** The bridge dumped
`Object.keys(entry.megaStone)[0]` — the base species — and threw away the
value, which is the resulting forme. Charizardite X and Y both read
"Charizard" and were indistinguishable. Both halves are dumped now.

**A limitation, pinned in a test rather than hidden.** Mega Evolution is free
and permanent, so it is nearly always right the moment it is offered. This
scorer only asks what the forme is worth to *this turn's move*, so a turn where
it adds nothing scores the two equally and the mechanic is declined — 21 of 31
offers taken rather than 31. Pricing a lasting resource needs a scorer that
can see past one turn, which a one-turn heuristic cannot.

### ~~The harness cannot see a stat change made earlier in the same turn~~ — done 2026-08-25

`DamageCollector` read both sides from a snapshot taken *before* the turn
resolved. Across turns that is right; within one it lagged, so a hit landing
after a Swords Dance, an Intimidate or a Close Combat was scored against stale
stages. It now tracks `-boost`/`-unboost` through the chunk.

**The timing is the whole trick.** Stages are frozen at the `|move|` line
rather than read at flush time, because a self-lowering move must not weaken
its own hit — Close Combat drops the user's defences *after* it lands. Reading
them a moment later would apply the drop to the hit that caused it.

The deltas reset each chunk, because the next snapshot already includes them
and counting twice would double them. Both edges have tests.

```
                                         before    after
a stage changed earlier in the turn       82.5%  →  87.3%   (n=1167)
no stage change that turn                 88.9%  →  89.3%   (n=3804)
```

The gap closes from 6.4 points to 2.0, and because 23% of hits were affected it
is the largest global gain of the day:

```
never Mega    92.1%  →  93.9%
always Mega   85.2%  →  86.9%
```

**Every damage figure measured before this was slightly pessimistic**, this
session's included. The instrument was wrong, not only the model.

### ~~Mega Sol and Contrary~~ — done 2026-08-25, and only one needed code

**Mega Sol** does not *set* sun. It makes the weather read as sun while its
holder is acting, and the engine keys that off `activePokemon`, so the whole
calculation sees sun -- the defender's own weather check included -- and sees
the real weather again the moment anybody else moves:

```js
if (this.battle.activePokemon?.hasAbility('megasol') && ...) return 'sunnyday';
```

In this dex the practical effect is Solar Beam, which we halve in any weather
that is not sun, and snow is everywhere in this format. Meganium-Mega went from
55.3% (n=215) to off the worst-offenders list; overall 79.5% → 80.4%.

**Contrary needed nothing at all.** It inverts through `onChangeBoost`, which
runs *before* the boost is applied and announced -- so the `|-boost|` line
already carries the inverted value, and boosts have been tracked on both sides
since the own-side fix. Predicted no change and measured none: Staraptor-Mega
61.1% → 62.0% with nothing written for it.

Which leaves the question of why Staraptor-Mega is now the worst thing on the
list, and the answer is the item below.

### ~~The weather Speed abilities~~ — done 2026-08-25

Chlorophyll, Swift Swim, Sand Rush and Slush Rush double Speed under their own
weather, and Unburden does it once the holder's item is gone. Measured on
identical pairs:

```
before   15673/16322 = 97.0%    339 backwards
after    15807/16322 = 97.8%    210 backwards   (-38%)
```

**The harness could not have measured these before.** `OrderCollector` tracked
Trick Room and Tailwind and never looked at the weather, so a Chlorophyll user
in sun was indistinguishable from one on a clear field. It tracks weather now.

Two corrections to this item as it was written:

- **Speed Boost needs nothing.** It raises the stat with `this.boost({spe: 1})`,
  which announces itself as an ordinary `|-boost|` line, and boosts are already
  tracked on both sides. A per-turn counter would double-count it.
- **Protosynthesis and Quark Drive are out of scope** — zero species in this
  dex have either, so they were never candidates.

Remaining, and not chased: snowscape pairs read 96.6% (n=3649) against 98.1%
on a clear field (n=12581). Slush Rush is one species in this dex, so that gap
is something else.

### ~~Make the terrain rules consult `is_grounded`~~ — done 2026-08-25

`is_grounded` had been written, exported, and called by nothing. It now has
five callers, and the five rules no longer hand terrain bonuses to Flying
types and Levitate users:

```
electricterrain  if (move.type === 'Electric' && attacker.isGrounded())
expandingforce   if (isTerrain('psychicterrain') && source.isGrounded())
mistyexplosion   if (isTerrain('mistyterrain') && source.isGrounded())
terrainpulse     onModifyType(move, pokemon) { if (!pokemon.isGrounded()) return; }
risingvoltage    if (isTerrain('electricterrain') && target.isGrounded())
```

**Rising Voltage is the odd one out** and the reason to read the engine rather
than pattern-match: it follows the *target's* footing while every other rule
follows the attacker's. A Levitating attacker still doubles it; a Flying target
still escapes it. Getting that backwards would be invisible in ordinary play
and wrong exactly where it matters.

The test that pins it also caught a wrong expectation of mine: the doubling and
the Electric Terrain type bonus are separate hooks and **stack**, so a grounded
attacker into a grounded target gets 70 → 182, not 140.

`estimate_damage` gained `field_conditions`, because Gravity drags everything
down and footing cannot be decided from a Pokemon's own type and item alone.
Both flags default to True so a caller that does not track footing keeps the
common case rather than silently losing the bonus for everyone.

### ~~Spread moves are eight points worse~~ — done 2026-08-25

We were counting the wrong thing. The engine sets `spreadHit` from how many
targets the move **selects**:

```js
if (targets.length > 1 && !move.smartTarget) move.spreadHit = true;   // 551
...
if (move.spreadHit) this.battle.attrLastMove('[spread] ' + hitSlot.join(','));   // 618
```

and emits `[spread]` if and only if that flag is set. The names it lists are
the *survivors*, after immunity, Protect and faints have removed the rest — so
**the tag's presence is the condition, and the count of names in it is
irrelevant.** `predict` was testing `spread_targets > 1`.

A Blizzard that selected two targets and landed on one still takes the 0.75,
and we were giving it full damage:

```
                        before            after
1 named, 1 hit      1.8%  (median 0.743)  91.2%  (median 1.000)
all spread hits    85.1%                  89.2%
```

n=57 in that bucket, and a median of 0.743 is 0.75 wearing a false moustache.
The spread-vs-ordinary gap narrows from ~7.6 points to ~3.3.

Two remain, both with the conditional-effect signature (good bias, poor
accuracy) and neither large: **Hyper Voice** 77.5% (n=40, median 0.949) and
**Blizzard** 80.9% (n=141, median 0.991).

### ~~The `-ate` cluster~~ — done 2026-08-25, and it was dead code

`ATE_MULTIPLIER` was applied to `power` **twenty-six lines after** `base` had
already consumed it:

```python
base = (2 * level // 5 + 2) * power * attack_stat // ...   # line 449
...
if rewritten is not None:
    power = modify(power, ATE_MULTIPLIER)                   # line 475
```

So the bonus modified a variable nothing read again. **Refrigerate, Pixilate
and Dragonize have never once paid it** — a flat 20% under-prediction on every
Normal move an -ate user throws, well outside a 17.5%-wide interval, and
diluted in the median because their other moves are unaffected. That is
exactly the perfect-median/poor-accuracy signature that led here.

```
ATK Glalie-Mega    50.7% -> 87.5%   (+36.8, identical 136 hits)
Altaria-Mega and Feraligatr-Mega both leave the worst-26 list entirely
overall, on this Mega-dense population   79.0% -> 79.5%
```

**All 1092 tests passed with the bug in place.** The suite tested every piece
-- `rewritten_type` returned "Ice", `stab_multiplier` returned 1.5 -- and
never checked that the assembled number moved. Unit tests on components cannot
see a wiring error between them. The regression test added here asserts the
damage actually changes, and was verified by reverting only `damage.py` and
watching it fail.

### ~~Measure the width of our predictions~~ — refuted too, 2026-08-25

The interval is not too narrow. Measured on 12,507 hits across both arms:

```
                        never Mega        always Mega
inside the interval       91.3%             84.4%
fell below                 4.7%              8.5%
fell above                 4.0%              7.1%
median miss, below        1.36 widths       1.06 widths
median miss, above        2.50 widths       2.22 widths
within half a width        6-8%             11-21%
```

A too-narrow interval puts misses *just* outside. These land one to two and a
half interval-widths out, and near-symmetrically — so the failures are a
minority of hits being **badly** wrong in both directions, not a majority
being marginally wrong.

**Fixed on the way:** Skill Link narrowed only the expected count and left
`hit_range` alone, so a Pokemon that always lands five hits still carried a
two-to-five prediction. The previous commit's message claimed the range was
narrowed and the code had not done it.

**Four hypotheses are now eliminated** for the Mega gap: field effects (0016),
a broad systematic bias (the control arm carries the same background),
per-forme damage errors (0017), and interval width (here). What is left is that
a *minority of specific hits* are badly wrong, roughly as often high as low.

### ~~The rest of the eleven points~~ — not the Mega formes (0017)

A targeted 19,802-hit measurement across **71 distinct Mega Stone holders**
(149 of 150 generated teams carry one) settles it:

```
total misses in the sample:              ~4158
misses inside the six worst formes:       ~270   (6.5%)
fixing all six to perfect would give:    +1.36 points
```

Ninety-three percent of the misses sit in formes that look individually fine.
No amount of further ability transcription will find this gap.

**Both standing leads were noise.** Ampharos-Mega read 1.650 on n=14 and
**0.990 on n=61/115**. Implementing on the thin sample, which this list was one
step from doing, would have added a wrong multiplier and then confirmed it
against the same thin sample.

**Ranking by bias was the wrong question.** Pyroar-Mega: median 1.003,
accuracy 65.2%. The gap is measured in accuracy, and a median-based hunt is
structurally blind to a conditional-in-the-model, unconditional-in-the-game
effect. Re-ranking by accuracy found the real list immediately.

Fixed: **Fire Mane** (filed as a pinch ability on the strength of its name; the
engine has no HP condition — Pyroar-Mega 65.2% → 86.4% on identical hits) and
**Skill Link** (engine-correct, but its contribution here is *not* demonstrated
— Heracross never appeared among the worst by accuracy).

### ~~The field effects a Mega brings~~ — refuted 2026-08-25

Experiment 0016. Bystander hits are marginally **better** with a Mega on the
field, in both seeds (88.8% vs 86.7%, and 84.9% vs 83.9%). Weather setters,
auras and Intimidate are still unmodelled and still real mechanics — they are
just not the explanation for this gap.

What the test found instead: the two arms are **identical through turn 3**
(89.0% vs 89.2%) and then the Mega arm loses ~11 points and never recovers,
with near-identical hit counts per turn band. So it is something a Mega leaves
behind, not a mix effect and not the moment of evolving.

Following that residual found **Parental Bond**, now implemented: the engine
scales the second hit by 0.25 in this generation, so the pair is **1.25x**, not
the 1.5x this backlog had written down. Measured at 1.200 over 92 hits first.
Mismatches from turn 3 on fell 449 -> 391 on identical samples, and
Kangaskhan-Mega, Crunch and Sucker Punch all left the worst-offenders list.

### ~~Mega — measured 2026-08-25~~, and the priority was upside down

Experiment 0015. **Enabling Mega costs the damage model about seven points,
and 75–85% of that loss is on hits that do not involve a Mega at all.**

```
                    seed 1                 seed 7
never Mega        93.9% (n= 9991)       91.2% (n=10156)
always Mega       87.3% (n= 9717)       83.2% (n=10042)
  involves a Mega 88.3% (n= 1751)       78.6% (n= 1583)
  no Mega on field 87.0% (n= 7966)      84.0% (n= 8459)
```

The non-Mega bucket is the stable finding: −6.9 and −7.2 points across two
seeds on ~8,000 hits each. The Mega bucket is *not* stable (88.3% vs 78.6% on
~1,700), so nothing is concluded from it.

Getting there needed two measurement bugs fixed first, both of which had
already produced plausible-looking numbers: `active_by_ident` silently dropped
every Mega'd Pokemon's hits, and `TeamPool.generated` was unseeded so two runs
drew different teams.

### ~~Split by team, not only by replay~~ — done 2026-08-24, and the answer was no

**A clean team-level split is impossible on this corpus, and the leakage was
inflating every reported figure by about four points.** Written up as
experiment 0014.

Grouping replays so a roster lands wholly on one side fails because every
replay has two rosters, so replays chain — A brings X and Y, B brings Y and Z,
and now A and B must share a side:

```
500 replays -> 46 components, the largest holding 427 (85.4%)
a strict team-disjoint test set could reach 14.6% at most,
and it would be the least-connected replays: obscure teams, one-off players
```

Subsetting whole replays fails too: 55 test replays have both teams already
seen, 38 have one new, **2 have neither**. Two replays is not a measurement.

What works is splitting the **sides** rather than the replays. Scoring only the
player whose own team is new turns two replays into 42 player-sides and 466
labels:

```
TRAIN, everything                45.45%   (9057 labels)
TEST,  everything                47.30%   (2076 labels)
TEST,  unseen team only          43.13%   ( 466 labels)
TEST,  team seen in training     48.51%   (1610 labels)

z = 2.047,  p = 0.041
```

So the test half has been reporting the model on teams it has already seen.
`CorpusSplit.summary()` now states the contamination, and
`unseen_team_sides` is the subset to quote when the claim is about
generalisation.

The split itself is **unchanged**. Reshuffling would invalidate every prior
result while fixing nothing — the contamination is a property of the corpus,
not of the hash.

Two things follow, both recorded rather than done:

- **Collect for team diversity, not volume.** 500 replays gave 448 distinct
  rosters and only 42 usable clean sides. More games from the same ladder
  population will not move that.
- **For a variety of teams, the engine differential harness is the better
  instrument and already is one.** It generates random teams, so it has
  unlimited diversity by construction, and it is where damage (92–94%), turn
  order (97.7%) and the knockout claim (99.0%) are measured. Replay agreement
  measures something narrower, and now says so.

### ~~The rest of the unpriced support moves~~ — mostly done 2026-08-24

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

### ~~Abilities~~ — done 2026-08-24

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

### ~~Roost, and the Flying type~~ — done 2026-08-24

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

### ~~Focus Sash and the knockout claim~~ — done 2026-08-24

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

### ~~Read the fields we already dump~~ — done 2026-08-24

All six wired. It found a real bug, as this shape of check keeps doing:
**the four one-hit knockout moves read as status moves** — the *fourth*
distinct reason a move in this dex can carry a zero base power, after the
per-hit callbacks, the situational multipliers and the damage callbacks.

`modifies_type` was the other substantial one: Weather Ball, Terrain Pulse,
Raging Bull and Aura Wheel were all read on the wrong row of the type chart.

Agreement train 45.36 → 45.42%, test 47.06 → **47.25%**. Damage prediction
holds at ~95% on the control team.


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

**Declined, on the project owner's call: the team discovery lab.** Evaluating
candidate teams by their matchup floor is Milestone 13, and pulling it forward
would jump milestones 6 through 11. Asked and answered on 2026-08-24: *"right
now lets not focus on a team and prepare me for variety of teams."*

That decision cuts the opposite way to how it sounds. Preparing for a **variety
of teams** makes generalisation the thing to measure, which is exactly what
item 1 turned out to be about — and it is why the engine differential harness,
which generates random teams and therefore has unlimited team diversity, is the
primary instrument here rather than replay agreement.

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
- **Check the instrument can see the effect before modelling it.** Three
  times now the harness was blind to the thing being fixed: `active_by_ident`
  dropped every Mega'd Pokemon, the turn-order collector never read the
  weather, and the damage collector cannot see a stage change made earlier in
  the same turn. Verification against a blind instrument is vacuous.
- **Test the assembled number, not only the pieces.** The -ate bonus was dead
  code for its whole life and 1092 tests were content, because each piece
  behaved and nothing checked that the damage moved. A component suite cannot
  see a wiring error between components.
- **Where a miss lands tells you which bug it is.** Misses clustered just
  outside the interval mean it is too narrow; misses one to two widths out
  mean specific hits carry a multiplier you do not model. Measuring *how far*
  wrong, in units of the interval, separated those in one run.
- **Bias and accuracy are different questions.** Ranking suspects by median
  ratio is blind to any effect that is conditional in the model and
  unconditional in the game: Pyroar-Mega read a perfect 1.003 median at 65%
  accuracy. Rank by the metric the gap is measured in (0017).
- **A thin sample does not become right by being acted on.** Ampharos-Mega
  read 1.650 on n=14 and 0.990 on n=61. Widen before implementing.
- **Name where the loss *is*, not where it is not.** 0015 measured that the
  loss fell on "hits that do not involve a Mega" and let that phrase become
  "hits affected by a Mega's field presence" without a measurement in between.
  0016 tested it directly and refuted it. An attribution inferred by
  elimination is a hypothesis, not a result.
- **An unseeded pool is not a measurement.** Two runs of the Mega comparison
  disagreed in direction because `TeamPool.generated` redrew the teams each
  time, and that swing was larger than the effect. Seed anything whose number
  gets reported.
- **Long runs visit states short runs do not.** 800-battle runs found two
  legality bugs that 90-battle runs never reached, both reachable in ordinary
  play and both fatal to the agent in a long game.
- **A lookup that fails silently deletes your evidence.** `active_by_ident`
  returned None for any Mega'd Pokemon, so the hits were dropped rather than
  mis-attributed and the harness looked healthy while measuring nothing. When
  a harness filters, count what it discarded.
- **A held-out set is only held out along the axis you split it on.** The
  replay-id hash separated battles and left 74% of test-side teams present in
  training; agreement on genuinely unseen teams is four points lower (0014).
  Before quoting a test figure, ask what it is held out *from*.
- **When the corpus cannot judge, the engine must.** Fourteen support moves
  were priced this round and humans picked them sixteen times in 500 battles.
  Agreement moved 0.03 points, which says nothing either way. Twenty-nine
  tests against `moves.ts` say something.
- **Blocked work belongs in the plan, not the backlog.** The seven support
  moves that cannot be priced are recorded in `PROJECT_PLAN.md` under
  *Deliberately not done*, with the capability each is waiting on. This file
  is for work that can start now.
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
