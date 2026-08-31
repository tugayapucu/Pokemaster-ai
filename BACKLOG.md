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

**Measure on the frozen pool.** `data/pool-eval.txt` holds 200 validated teams
harvested from the train split of a 1,769-replay corpus, and
`harvested_pool(..., cache=...)` reloads it without touching the corpus. Use it
for anything compared across runs.

The reason is recorded in 0027: while the corpus was being collected the train
split moved 405 -> 923 -> 1,427, so `harvested_pool` drew different teams every
time, and two runs of the same A/B on identical seeds disagreed by 1.4 points.
Within a run both arms share the pool and the comparison holds; across runs it
did not, and nothing said so. Results published before this was frozen were
each internally valid and are not comparable to each other.

What the frozen pool carries, against the generated pool 0024 replaced:

    protect 100.0%   fakeout 60.0%   tailwind 50.5%   trickroom 47.5%
    ragepowder 35.5%   helpinghand 17.5%   followme 8.0%
    swordsdance 8.0%   knockoff 12.0%   uturn 1.0%   stealthrock 0.0%


**Direction set by experiment 0020: what the agent chooses is worth more than
what it knows.** Damage accuracy converts at ~0.23 points of win rate per
point, which prices out the Mega gap (~1.6) and the rest of the mechanical
work. The largest improvement ever measured here was +10.1 from a *decision*
the agent was not making.

Two things make this a live direction rather than a fresh guess, and both were
found by reading what is already there:

- **`evaluate_position` exists, is exported, has unit tests, and has no
  production caller.** Its own docstring says search needs it and that
  Milestone 7 replaces it with a learned model. Nothing has ever checked
  whether it predicts anything.
- **`search.py`'s stated reason for not doing real search is refuted.** It
  says *"0001 found search depth is not the bottleneck, opponent knowledge
  is"* — and 0005, 0018 and 0019 have since measured opponent knowledge at
  +0.09 agreement, a +4.3 ceiling, and a null. Forking the engine was measured
  viable at ~460 forks/sec with verified isolation. It was set aside on a
  premise that stopped being true.

### 1. An opponent worth measuring against

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

Speed control is the first one to point it at. Tailwind is on ~48% of
harvested teams and Trick Room ~50%, and unlike redirection they change every
turn that follows rather than a single attack -- a much larger prior than the
2.0% ceiling redirection turned out to have.

Not a human-imitation model. 0010 and 0013 are both cases where following the
corpus was wrong, and the point here is coverage of the *action space*, not
copying anyone's judgement.

### 2. An evaluator that can price more than HP

**Confirmed worth doing by 0029, and the confirmation nearly went the other
way.** Fitted on self-play positions the extra features looked worthless
(+1.4); fitted on reconstructed human positions they are worth +3.0 held out
and +4.4 against the shipped evaluator. Screens are non-zero in 0.0% of
self-play positions and 7.8% of real ones -- the agent never uses them, so
self-play could not see them. Grade this work on human positions, not
self-play.

**Also from 0028.** 0028 re-measured
`evaluate_position` on the frozen pool and it is weaker than 0021 reported:

    turns 1-2         57.6%   was 71.0%     <- barely better than a coin flip
    turns 3-5         71.8%   was 81.0%
    clear (50-150)    72.6%   was 82.7%
    overall           74.6%   was 79.7%

It scores only HP and fainting, so on turn one -- when nobody has taken damage
-- its whole signal is which side has revealed less. That correlated with
something on the generated pool and does not on real teams.

**A search compares positions one or two turns ahead, which is exactly where
this is now weakest.** So it is not a refinement of Milestone 7; it is the
precondition for search being worth trying at all.

What survives is the property search actually needs: it is still monotone in
its own confidence (65.2% slim, 72.6% clear, 85.6% large). It knows when it is
guessing. Anything replacing it must keep that and beat the numbers above, on
the frozen pool, graded against who won.

Honest order: improve the evaluator to a measured target *first*, re-test
search *second*, and stop if the first step does not move. 0022 is a standing
reminder that a better evaluator may still not make search pay.

### 3. A learned value model, once there is something to learn against

79.7% is a high floor for a hand-written function, so Milestone 7's headroom
over it is real but modest. Worth less than giving search an evaluator it
currently ignores.

The weakest cell is the one search cares most about: **66.1% on slim
advantages**, which is exactly where a lookahead compares close positions. If a
learned model is built, that is the number to improve, not the headline.



Only after item 1 says the evaluator is worth maximising.

0001 found one-turn search inert (49.3%, not significant) and blamed opponent
knowledge. That explanation is dead, so the result needs a better one — the
likeliest being that the "search" scores actions with the heuristic's own
per-move numbers rather than evaluating positions, so it never had anything to
look ahead *with*.

Fix the docstring either way: it currently cites a refuted claim as settled.

---

## Done, most recent first

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
