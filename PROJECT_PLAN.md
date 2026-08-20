# Pokémon Champions AI — Long-Term Project Plan

> **Status:** Living project roadmap  
> **Last updated:** 2026-08-18  
> **Primary game:** Pokémon Champions  
> **Primary competitive format:** Double Battles / VGC-style play  
> **Primary objective:** Build a strong battle recommendation system and, over time, an autonomous Pokémon Champions agent using classical algorithms, supervised learning, reinforcement learning, search, opponent modelling, and self-play.

# 1. Project Vision

The long-term goal is to build an AI system that understands competitive Pokémon Champions battles well enough to perform two related tasks.

## A. Player Recommendation System

Given the information legitimately available to a player during a battle, rank the available actions and provide useful decision support.

Example:

```text
Recommended actions

1. Protect                         41%
2. Switch -> Incineroar           27%
3. Close Combat -> Slot 1         19%
4. Other                          13%
```

Long-term capabilities may include:

- turn-by-turn action recommendations;
- lead selection;
- matchup analysis;
- team composition recommendations;
- move / item / ability suggestions;
- opponent set inference;
- win-probability estimation;
- risk-aware alternatives;
- human-readable explanations.

## B. Autonomous Battle Agent

Build an agent capable of independently selecting legal battle actions and competing against increasingly strong opponents.

Development progression:

```text
Random Agent
    |
    v
Rule / Heuristic Agent
    |
    v
Search Agent
    |
    v
Imitation-Learning Agent
    |
    v
Reinforcement-Learning Agent
    |
    v
Self-Play Agent
    |
    v
Hybrid Policy + Search + Opponent-Model Agent
```

The recommendation system and autonomous agent should share battle representation, evaluation infrastructure, and model code wherever practical.

# 2. Initial Product Direction

The project initially prioritizes **Double Battles / VGC-style play**.

Singles may be supported later, but the early architecture should not make that expansion impossible.

Important principles:

- simulator-first development;
- correctness before intelligence;
- explicit partial observability;
- baselines before deep learning;
- evaluation before anecdotes;
- regulation-aware design;
- portfolio-quality engineering.

# 3. Initial Scope

## In scope

- Pokémon Champions battle representation;
- Double Battle / VGC-style decision making;
- configurable rules and regulations;
- legal action generation;
- battle-state / observation encoding;
- heuristic agents;
- search-based agents;
- supervised / imitation learning;
- reinforcement learning;
- self-play;
- opponent modelling;
- uncertainty modelling;
- move recommendation;
- recommendation confidence;
- win-probability prediction;
- offline evaluation;
- simulated tournaments;
- model-serving API;
- optional user-facing web interface;
- experiment dashboards and reports.

## Not initially in scope

- automating taps/clicks in the live Pokémon Champions client;
- account farming;
- matchmaking automation;
- bypassing anti-cheat or game protections;
- reverse engineering private game protocols;
- botting Ranked Battles;
- perfect recreation of every historical generation;
- large polished frontend before the decision engine works;
- expensive deep-RL training before useful baselines exist.

# 4. Proposed Technical Stack

This is a starting point and may change.

## Core

- **Python** — battle AI, data pipelines, ML, evaluation
- **PyTorch** — neural models
- **NumPy** — numerical work
- **Pydantic / dataclasses** — structured domain models
- **pytest** — testing

## RL / environment

Potentially:

- Gymnasium-style environment API;
- custom vectorized self-play runner;
- RL library only if it meaningfully reduces complexity.

Do not add a heavy RL framework merely because it supports PPO.

## Experiment management

Start lightweight:

- YAML/TOML configuration;
- deterministic run directories;
- CSV/JSON/Parquet metrics;
- saved model metadata.

Add a dedicated experiment-tracking platform later if needed.

## Serving / UI

Potential future stack:

- FastAPI backend;
- React + TypeScript frontend;
- WebSocket support if interactive analysis requires it.

Frontend work is secondary to the battle engine and ML evaluation.

# 5. Proposed Repository Structure

```text
pokemon-champions-ai/
|
|-- AGENTS.md
|-- PROJECT_PLAN.md
|-- README.md
|-- pyproject.toml
|-- .gitignore
|
|-- src/
|   `-- champions_ai/
|       |
|       |-- domain/
|       |-- mechanics/
|       |-- observation/
|       |-- env/
|       |-- agents/
|       |-- recommendation/
|       |-- opponent_model/
|       |-- data/
|       |-- evaluation/
|       `-- serving/
|
|-- configs/
|   |-- regulations/
|   |-- agents/
|   |-- training/
|   `-- evaluation/
|
|-- tests/
|   |-- unit/
|   |-- mechanics/
|   |-- integration/
|   `-- regression/
|
|-- scripts/
|   |-- train.py
|   |-- evaluate.py
|   |-- tournament.py
|   `-- preprocess_data.py
|
|-- experiments/
|-- notebooks/
|-- docs/
|   |-- architecture/
|   |-- decisions/
|   |-- experiments/
|   `-- data/
|
`-- data/
    |-- raw/
    |-- interim/
    `-- processed/
```

Large datasets and model checkpoints should normally not be committed directly to Git.

# 6. Core Domain Model

Before ML begins, define a battle representation that is stable, explicit, and testable.

### Implementation status (2026-08-11)

Live in `src/champions_ai/domain/`: `Regulation`, `StatSpread`, `PokemonSet` (pre-battle), `Boosts` and `BattlePokemon` (live in-battle), `Team`, `TeamPreview`, `RevealedPokemon`, `Side`, `BattleState`, `Observation`/`ObservedSide`/`ObservedPokemon`, the action types (`TargetSlot`, `MoveAction`, `SwitchAction`, `PassAction`, `JointAction`, `TeamPreviewAction`), `MoveData`, and the legal-action generator. All are immutable (frozen) Pydantic models — state changes (`with_damage`, `with_heal`, `with_status`, `Boosts.clamped_add`, `Side.with_slot`, `BattleState.with_side`) return new instances rather than mutating in place, so a battle's history is just a sequence of snapshots. Milestone 1's domain layer is complete; what it still lacks is real data (move/species/item tables from the `champions` mod) and a simulator adapter to drive it.

`Observation.from_battle_state(state, player)` is the **only** sanctioned path from simulator truth to agent input. Anything consuming `BattleState` directly is a hidden-information bug; the leak tests in `tests/unit/domain/test_observation.py` were verified non-vacuous by deliberately breaking the masking and confirming they fail.

A boundary worth keeping: the action types validate only what is true regardless of move data (index ranges, no double-switch to the same Pokémon, one Mega per turn). Anything needing move metadata — whether a move requires a target, whether a target is adjacent, whether a Pokémon is trapped — belongs to the legal-action generator, which will have access to the move data these types deliberately don't carry.

Two known soft spots to revisit rather than forget:

- `side_conditions` / `field_conditions` are plain `dict[str, int]` (name → turns remaining). `frozen=True` stops the *field* being reassigned but does not stop the dict itself being mutated in place, so these are immutable by convention only. Chosen over a fully immutable mapping because the expected construction path rebuilds state from the simulator's protocol stream each turn rather than mutating incrementally — revisit if anything starts editing conditions in place.
- Weather, terrain, status, and condition names are plain strings, not enums. Deliberate while the full set of values Champions actually uses is still being discovered; worth tightening once the simulator adapter has enumerated them in practice.

### Handling future regulations

Regulations rotate and expand — more Pokémon, items, and moves are already announced. The domain model is built so that costs nothing:

- **No roster is hardcoded.** `species`, `moves`, and `item` are plain strings, never enums. New Pokémon and moves require zero domain changes.
- **Legality is Showdown's** (ADR 0001/0003). A new regulation's roster, learnsets, and banlist arrive by updating the `pokemon-showdown` dependency; `package-lock.json` pins the exact version so runs stay reproducible until we deliberately bump it.
- **Everything a regulation varies is data on `Regulation`** — stat-point caps, team sizes, level, game type, and which special mechanics are enabled. Supporting a new regulation means adding an instance, not editing classes. `tests/unit/domain/test_stats.py` includes a hypothetical regulation with different caps to keep this honest.
- **Special mechanics are named, not booleans** (see the resolved open question in section 15), so a regulation re-enabling Terastallization is a data change.

Two things would still need real work: a genuinely new *kind* of mechanic (something neither a form change nor a move) may need new action shapes, and any regulation dropping Open Team Sheets would need `TeamPreview` to mask by regulation rather than by flag.

### Confirmed Reg M-B mechanics differences from mainline VGC (2026-08-11 spike)

Verified against Showdown's `champions` mod (see `spike/showdown-bridge/notes.md`) — do not assume mainline Gen 9 conventions when building the fields below:

- **Stat allocation is not EVs/IVs.** Champions uses a "Stat Points" system: 0–32 points per stat, 66 points total across all stats, IVs fixed at 31. The `effective stats` field's inputs should model this, not a 0–252/510 EV spread.
- **Held items are a curated subset**, not the full mainline item list (e.g. Choice Band, Choice Specs, Assault Vest, and Rocky Helmet are all unavailable). Item legality must be queried from the `champions` mod's data, not assumed from general Gen 9 knowledge.
- Mega Evolution is a standard, available mechanic in this mod; Terastallization is not currently enabled under Reg M-B's ruleset despite Pokémon sets carrying a Tera Type field.
- **Opponent HP carries an HP-bar colour at the threshold percentages.** Champions reports shared HP as a *floored* percentage (not rounded, minimum 1 while alive), and at exactly 20% or 50% appends a colour letter — `20y`/`20r`, `50g`/`50y` — because those are the in-game bar's colour boundaries and the percentage alone is ambiguous there. This is real information the player has from looking at the bar, so `domain/health.py` preserves it. Confirmed in the `champions` branch of `Pokemon.getHealth()` (`sim/pokemon.ts`).
- **The Pokédex and learnsets are restricted**, not just the item pool. Confirmed while hand-building a legal team (2026-08-11): Amoonguss does not exist in Champions at all, Charizard cannot learn Tailwind, and Grimmsnarl cannot learn Thunder Wave. Never assume a mainline Pokémon, or a mainline moveset, is available — validate against the format.
- **Open Team Sheets is opt-in, not automatic.** Reg M-B's `Open Team Sheets` rule (as opposed to `Force Open Team Sheets`, used by the Bo3 variant) shows both players an Accept/Deny prompt at Team Preview; nothing extra is revealed unless *both* accept. On a normal ranked match this essentially never happens, so by default a player only sees species/level/gender for the opponent's team. Even when accepted, **Stat Points allocation is never revealed** — confirmed directly from `showOpenTeamSheets()` in Showdown's `sim/battle.ts`, which hardcodes `evs: null`. `TeamPreview.opponent_team` models this with `RevealedPokemon`, a type that has no stats field at all rather than one that's merely set to `None` by convention.
- Team building is bring-6/pick-4 for doubles (Team Preview shows 6, only 4 are brought into the battle).

## Pokémon state

Possible fields:

```text
species
form
level
types
ability
item
moves
base stats
effective stats
current HP
maximum HP
status
volatile conditions
stat stages
active / benched
revealed-information flags
```

## Field state

Possible fields:

```text
turn number
weather
terrain
room effects
side conditions
slot-specific effects
active Pokémon
remaining Pokémon
special-mechanic availability
```

## Action representation

For Double Battles, each active Pokémon may potentially:

- use a move;
- choose a legal target;
- switch;
- use an allowed special mechanic.

The environment must distinguish:

```text
Individual Action
Joint Turn Action
```

## Observation representation

Maintain separate concepts:

```text
BattleState
Observation
```

`BattleState` may contain complete simulator truth.

`Observation` contains only information legally available to the relevant player.

# 7. Long-Term Roadmap

## Where the project actually is (2026-08-18)

A single place to see status, because the per-milestone notes below have grown
long. Each line links to where the detail lives.

### Done and measured

| | Status |
|---|---|
| **Domain model** (§6) | Complete. Immutable, `Observation` is the only path from truth to agent, leak tests verified non-vacuous. |
| **Simulator bridge** (M1–2) | Showdown `sim` driven headlessly, per-player streams, seeded replay exact, 97.2% protocol coverage. |
| **Legal actions** (M1) | Engine-reported availability (ADR 0003). Gap: Struggle unmodelled. |
| **Baseline agents** (M3) | Random, Heuristic, Search. Heuristic beats Random 96.3%. |
| **Evaluation harness** (M3) | Teams exchanged per matchup, Wilson intervals, conservative significance. |
| **Damage model** (M1) | Verified exactly against engine output across 38 non-crit hits. |
| **Replay pipeline** (M5) | Fetch, filter, choice labels, observation reconstruction, provenance manifests. Usage-terms gate resolved. |
| **Human-agreement benchmark** (M5) | 1,061 labels from 50 rated games. The first external metric this project has. |
| **Team Preview** (M13) | Implemented and explainable. **Not yet validated** — see below. |

### Measured results worth remembering

```
CORPUS: 500 rated replays, 3,503 turns, 6,137 decision points, 11,133 labels
        Elo 1500-1848, median 1614, zero reconstruction failures

heuristic-v1 vs random           96-99%  significant
search-v1    vs heuristic-v1     49.3%   not significant   (experiment 0001)
heuristic-v1 human agreement     43.1%   vs 22.2% random   (CI 42.1-44.0%)
lead selection vs human leads     56.6%   vs 50.0% random   NOT significant
matchup-switch                   REVERTED                  (experiment 0004)
```

At 11,133 labels the agreement interval is **±0.9 points**, which is enough to judge a single scoring change on its own rather than only in aggregate.

**Correction to an earlier claim.** A previous version of this section reported that human agreement and head-to-head strength had "disagreed, both significantly, in opposite directions", and drew a methodology rule from it. That rested on a 600-battle result of 59.0% which **did not replicate**: 1,600 battles across two seeds give 52.9%, one seed null, and the change is *worse* against Random. The metrics were never in conflict — agreement said no, strength said very little, and an underpowered run made it look like a disagreement. See experiment 0004.

The rule that survives is narrower and about power, not arbitration:

- **agreement is the sensitive instrument** for scoring changes, detecting at p<0.01 what 800 self-play battles could not (experiment 0003);
- **do not conclude a head-to-head from under ~1,500 battles**, and always run at least two seeds over a pool of ten or more teams. Twice now the first number has been wrong in the same direction.

**The two metrics have now disagreed, both significantly, in opposite directions** (experiment 0004). Matchup-based switching *lowers* human agreement (43.6% → 41.7%, McNemar chi2 = 13.69 against) while *winning* head to head (354-246 over 600 battles). Neither instrument is broken — they measure different things:

- **agreement is the more sensitive detector** for scoring changes, catching at p<0.01 what 800 self-play battles could not (experiment 0003);
- **head-to-head is the arbiter when they conflict**, because it measures the objective rather than a stand-in for it;
- a change that moves them oppositely is **interesting, not broken**, and gets recorded rather than resolved by dropping the inconvenient half.

### Known gaps, in the order the evidence says to fix them

0. **The heuristic's decision rule is the limit, not its inputs** (experiment
   0005). Perfect opponent knowledge moves agreement by less than a tenth of a
   point, and Protect still accounts for 853 misses under the strongest
   possible oracle. Learning the policy from the 11,133 human labels is now the
   evidence-backed next step, rather than adding more features to a rule that
   cannot use them.
1. **Move effects are not modelled at all** — see below. The heuristic prices
   every move as expected damage, so a flinch, a status, a stat drop, recoil
   and drain are all invisible. This is a *data* gap before it is a scoring
   gap, and it sits underneath every other item here.
2. **Switching — still open, and now honestly so.** Rated humans switch on
   11.5% of decisions and the agent on 2.1%, agreeing on 113 of 1,281 switch
   labels. A matchup-based replacement was built and **reverted** (experiment
   0004): it tripled switch agreement and lost on everything else. The likelier
   cause is not how switching is scored but what the agent cannot see — an
   opposing switch, a Pokémon worth preserving — which is Milestone 10, not a
   scoring term.
3. **Team Preview lead ordering carries no signal.** 48.4% against a 50%
   baseline over 547 decisions (was 56.6% on 53 — the small sample flattered).
   More data did not rescue it, so "lead with the best average matchup" is
   likely the wrong rule rather than an undertrained one. The *pick-four* half
   remains unmeasured, deliberately.
4. **Targeting.** ~17% of remaining disagreements are the right move aimed at
   the wrong Pokemon.
5. ~~**Opponent modelling** (M10).~~ **Dropped off the critical path 2026-08-20
   (experiment 0005).** Measured before building it: an oracle handed the
   opponent's *entire* moveset gains **+0.09 points** of agreement (chi2 = 0.4),
   and an oracle handed the move they actually use this turn is **worse**
   (−0.49%, chi2 = 8.8). The binding constraint is the policy, not the features.
   The assumed-STAB prior stays as the placeholder it is.
6. **Struggle** is unmodelled, and is the whole of the benchmark's remaining
   unscorable labels.
7. **Mega Evolution** is never offered by a reconstructed observation, so it is
   excluded from agreement rather than scored.
8. **Nature** is stored as a name with no table mapping it to a stat, so
   matchup maths treats every Pokemon as neutral-natured.
9. **The random baseline is very slightly optimistic.** It is computed as
   uniform over *slot* actions, while `RandomAgent` picks uniformly over
   *joint* actions, and `JointAction` validation filters some combinations —
   so the marginals differ. Invisible at 1,091 labels (20.3% against a
   predicted 21.3%), detectable at 11,133 (23.1% against 22.2%). More data did
   not break the metric, it exposed an approximation that was always in it.

### Move effects: the gap underneath the others (identified 2026-08-18)

`HeuristicAgent` scores every move as expected damage. Nothing else about a move reaches the score, and `MoveInfo` has no field to carry it — the bridge discards Showdown's `secondary`, `secondaries`, `drain`, `recoil` and `self` at the dump. **This is a data gap before it is a scoring gap.**

What that costs, on real Reg M-B moves:

| Move | What we see | What it is |
|---|---|---|
| Nuzzle | 20 BP, near worthless | **100% paralysis** |
| Icy Wind | 55 BP spread | **100% Speed drop on both** — core VGC speed control |
| Rock Slide | 75 BP spread | **30% flinch on both** |
| Fake Out | 40 BP | **100% flinch, +3 priority**, first turn out only |
| Zap Cannon | 120 BP at 50% accuracy | **100% paralysis**, which is what justifies the accuracy |
| Flare Blitz | 120 BP | 120 BP **minus 33% recoil** |
| Drain Punch | 75 BP | 75 BP **and heals half the damage dealt** |

Measured on the 1,061-label benchmark: **41% of move labels (401/974) involve an effect we do not model.**

**The headline number is misleading in our favour, and that is the important part.** Agreement on those moves is *higher* than on moves without them — 52.9% against 41.9% — because secondary effects cluster on high-base-power moves (Flare Blitz, Close Combat, Wave Crash, Moonblast are all 95–120 BP). A damage-first scorer picks them, humans pick them, and **we agree for the wrong reason**. The score conceals broken reasoning rather than exposing it.

The real cost concentrates where base power is low or bad and the effect is the whole point: Fake Out (40 BP, 27 misses), Zap Cannon (50% accuracy bought with guaranteed paralysis, 12 misses), Rock Slide (7). Recoil and drain distort even the moves we get right.

Planned in two stages, deliberately separated:

- [x] **Data (done 2026-08-18).** `secondary`/`secondaries` (chance, status, boosts, volatile), `drain`, `recoil` and self-boosts now travel through the bridge dump into `MoveInfo`, guarded by an integration test against the engine — the same pattern that caught the missing `allies` target and the missing `endure` stall move. Cheap, low-risk, and required by everything after it.
- [x] **Drain and recoil scored (done 2026-08-18).** Priced in the same currency as damage dealt, because that is what they are, and clamped to what is available — healing above full is wasted, recoil cannot take more HP than the Pokémon has. **Agreement 42.2% → 42.5%, McNemar chi2 = 0.64, not significant** (14 discordant labels of 1,091). Exactly the outcome predicted below: where we already agreed by coincidence, correcting the reason changes nothing the metric can see. Kept because Flare Blitz genuinely costs a third of its own bar and Drain Punch genuinely heals, the explanations are now truthful — which Milestone 4's recommendation system depends on — and it is a prerequisite for a position evaluator that counts HP honestly.
- [x] **Status and stat changes scored (done 2026-08-18).** Expected value, except that a *guaranteed* rider is treated as certain — Nuzzle's paralysis and Zap Cannon's are the whole reason those moves are worth pressing at 20 base power and 50% accuracy. Type immunities are respected (Electric cannot be paralysed, Fire cannot be burned) and a status never stacks on an already-statused target. **Defensive self-drops are priced against the incoming threat** rather than at a flat rate: Close Combat's own -1 Def/-1 SpD is a bill that only arrives if we are still there to be hit, and charging full price made the agent avoid one of the format's best attacks.
- [x] **Flinch scored and first-turn moves gated (done 2026-08-18).** Flinch is the one rider whose value depends on turn order — denying a target its turn is worth nothing once it has acted — so it is scaled by the chance we move first (priority settles it outright, otherwise speed, with a tie counting half). **Fake Out agreement doubled, 4 → 8 of 31 labels**, and the agent still under-presses it (18 against a human 31) rather than over-correcting.

  Fake Out, First Impression and Mat Block are refused by the engine after the first turn out, and it does that at *runtime* rather than reporting them as disabled — confirmed by a human in our own replay data pressing Fake Out on turn two and getting the failure hint. So `BattleTracker` now records when each Pokémon arrived, for both sides, and `turns_on_field` reaches the agent through `BattlePokemon` and `ObservedPokemon` alike. Zero means *unknown* rather than "long ago", because blocking a legal move on missing data is worse than allowing an illegal one.

**Cumulative result of the whole move-effects effort, paired on identical labels:**

```
damage-only    460/1091 = 42.2%
effects-aware  476/1091 = 43.6%
30 labels newly correct, 14 newly wrong
McNemar chi2 = 5.11  -- significant at p<0.05
```

No individual step cleared significance on its own — drain/recoil 0.64, status and stat changes 1.39, flinch 1.23 — but the accumulation does.

**A measurement trap worth recording, because it nearly buried the result.** The first attempt at this cumulative figure compared against a baseline that disabled the rider scoring but still inherited the first-turn gate, since that gate lives in `_score_move` rather than in the rider pass. The contaminated baseline read 42.6% and gave chi2 = 2.70 — not significant. Only a genuinely clean baseline showed 42.2% and chi2 = 5.11. When an A/B differs by several changes, it is worth checking that "A" really is A. Fake Out additionally needs its first-turn-out restriction, which the engine enforces at runtime rather than reporting as `disabled` — confirmed by a human in our own data selecting it on turn 2 and getting the failure hint.

Expect this to improve *reasoning* more than the agreement figure, for the same reason experiment 0003 found: where we already agree by coincidence, fixing the reason changes nothing the metric can see.

### What the measurements have actually settled (2026-08-20)

Four attempts to improve the agent by giving it *better information or better hand-written rules* have now been measured, and three failed:

| Attempt | Outcome |
|---|---|
| One-turn search (0001) | Inert — diverged from the heuristic on 6% of turns |
| Move effects (0002-0003) | **Worked** — +1.4 points cumulative, chi2 = 5.11 |
| Matchup switching (0004) | Reverted — worse on agreement, Random, and a head-to-head that did not replicate |
| Team Preview lead ordering | No signal — 48.4% against a 50% baseline |
| Opponent-knowledge oracle (0005) | **+0.09 points.** The ceiling itself is nearly flat |

The pattern is consistent and it is not about information. A rule that prices *damage now minus damage taken now* cannot express why a human protects, switches or leads, and handing it perfect knowledge of the opponent does not change that — it makes Protect worse, because the assumed-threat prior had been compensating for the missing reasoning.

**So the next step is to learn the policy rather than write it.** The features are adequate; the mapping from features to actions is what is missing, and there are 11,133 labelled human decisions to learn it from.

### Deliberately not done

- Bulk collection beyond research use: the replay logs carry no licence, so the
  corpus is never redistributed (§12, and `CollectionManifest.usage_note`).
- Anything in §3's out-of-scope list — client automation, matchmaking, botting.
- A learned model. Baselines first, and the benchmark to judge them by now
  exists.


## Milestone 0 — Research, Scope, and Reproducible Skeleton

### Goal

Create a clean repository and freeze the first experimental scope.

### Tasks

- [x] Initialize repository.
- [x] Add `AGENTS.md` and `PROJECT_PLAN.md`.
- [x] Create `README.md`.
- [x] Add Python project configuration.
- [x] Add formatter/linter/test tooling. (`pyproject.toml`: pytest + ruff, verified passing)
- [ ] Define configuration strategy.
- [ ] Define experiment-output format.
- [x] Define initial target regulation. (Gen 9 VGC 2026 Regulation M-B — section 10)
- [ ] Document supported mechanics. (Partial: `spike/showdown-bridge/notes.md` + section 6 cover what the spike surfaced; not a full mechanics doc yet)
- [x] Decide simulator strategy. (Drive Showdown's `sim` engine directly via `BattleStream` — proven working in `spike/showdown-bridge/`)
- [x] Create initial architecture decision records. (`docs/decisions/0001-simulator-strategy.md`, `docs/decisions/0002-initial-regulation.md`)

### Definition of done

A new developer/agent can clone the repository, install it, run tests, and understand the first supported battle format.

### Current repository state (2026-08-11)

`src/champions_ai/` is a src-layout package with `pyproject.toml` (pytest + ruff) — installable via `pip install -e ".[dev]"`. Its `domain/` subpackage now has real Milestone 1 content (see section 6's implementation status); 32 tests passing, lint clean. The other subpackages from section 5's proposed structure (`mechanics/`, `env/`, `agents/`, etc.) are intentionally not pre-created; add them when there's real code to put in them.

`spike/showdown-bridge/` is a throwaway (but committed, for reference) proof that the simulator strategy works: a Node script drives Showdown's `sim` engine directly for a full Reg M-B battle, and a Python script drives it as a subprocess and parses the result. See `spike/showdown-bridge/notes.md` for mechanics findings that feed into section 6.

The `data/` folder that previously held gen1–gen9 Showdown JSON snapshots was leftover from an earlier, unrelated project and has been removed (2026-08-10). Fresh reference data, scoped to the current Champions regulation, should be pulled during Milestone 1 instead of reusing the removed gen1–8 data.

---

## Milestone 1 — Battle Representation and Legal Action Engine

### Goal

Represent Pokémon Champions battle states and enumerate valid player actions.

### Deliverables

- [x] Pokémon domain objects. (`PokemonSet` — pre-battle team-sheet entry; `BattlePokemon` — live in-battle snapshot with HP/status/boosts)
- [x] Team representation. (`Team`)
- [x] Team Preview representation. (`TeamPreview`, `RevealedPokemon` — the pick-4-of-6 decision point, added after realizing it's chronologically the first decision in a match and needed its own hidden-information handling; not in the original deliverable list below, added here)
- [x] Battle state representation. (`BattleState` + `Side` — full simulator truth: turn, both sides' brought Pokémon, slot occupancy, weather/terrain, side/field conditions, terminal + winner detection)
- [x] Observation representation. (`Observation`, `ObservedSide`, `ObservedPokemon` — `Observation.from_battle_state(state, player)` is the single masking boundary)
- [x] Hidden-information masking. (Opponent HP as rounded percentage; item/ability only once revealed; moves only once used; unbrought Pokémon exposed as a count, not a roster. `ObservedPokemon` has no field capable of holding a secret, so leaks are structurally impossible rather than merely avoided)
- [x] Regulation representation. (`Regulation`, `REGULATION_M_B`)
- [x] Move target representation. (`TargetSlot` — explicit `side`/`slot`, translated to Showdown's signed convention at the adapter boundary)
- [x] Individual action representation. (`MoveAction`, `SwitchAction`, `PassAction` as a discriminated union; plus `TeamPreviewAction` for the pick-N-of-6)
- [x] Joint Double Battle action representation. (`JointAction`)
- [x] Legal-action generator. (`legal_slot_actions` / `legal_joint_actions`, generated from `Observation` so the hidden-information boundary holds by construction; takes injected `MoveData` rather than loading data itself)
- [x] Serialization to/from JSON. (Pydantic gives this per-object via `model_dump_json`/`model_validate_json`, with round-trip tests on `PokemonSet`, `BattleState`, and `JointAction`; no dedicated serialization module — none is needed while the models carry it themselves)
- [x] Unit tests. (99 passing, covering everything built to date, including non-vacuous hidden-information leak tests)

### First useful demo

Given a JSON battle state:

```bash
python -m champions_ai.actions state.json
```

return all legal actions.

This demo should exist before any neural network.

**Status:** the library half is done — `legal_joint_actions(Observation.from_battle_state(state, player), move_data)` already returns the answer, verified on a realistic VGC position (12 and 8 slot options, 94 joint actions). The CLI wrapper is not written, and can't be honestly finished until move data is loadable from the `champions` mod rather than hand-supplied, since a real `state.json` would reference arbitrary moves. That data adapter is the natural next slice.

### Carried into the next slice

Known gaps left by Milestone 1 — **Mega Evolution never being offered**, **move-lock effects** (Choice, Encore, Taunt, Disable, Torment) and **Struggle** being unmodelled, and **trapping** being read from a `"trapped"` volatile set by convention.

These are one problem, not four. Showdown's per-turn request payload (`getMoveRequestData()` in `sim/pokemon.ts`) already reports `canMegaEvo`, per-move `disabled`, `trapped`/`maybeTrapped`, and `lockedMove` for each active Pokémon, so all four close together at the environment adapter by consuming the engine's answer rather than reimplementing legality from species/item data. See **ADR 0003**, which also records the one genuinely open tension: engine-reported availability can't enumerate actions for hypothetical states, which search (Milestone 11) will eventually need.

---

## Milestone 2 — Deterministic Battle Environment

### Goal

Create or integrate an environment in which agents can play complete battles.

### Required capabilities

- [x] reset battle; (`ShowdownBridge.start_battle`)
- [x] retrieve observation; (`BattleTracker.observation()`, built from the player-visible stream)
- [x] enumerate legal actions; (`legal_joint_actions` running against live battle state, with move target types learned from the engine's requests)
- [x] submit joint actions; (`format_joint_action` renders a `JointAction` into a Showdown choice)
- [x] resolve turn;
- [x] detect terminal state; (`|win|` in the protocol stream)
- [x] return winner;
- [x] log battle trajectory; (`Trajectory` — seed + ordered decisions, ~6KB per battle, replayable)
- [x] replay battle deterministically when randomness is seeded. (Verified: same seed reproduces a battle exactly. `|t:|` lines carry wall-clock time and must be excluded from comparison — a test fails loudly if anything *else* becomes nondeterministic.)

### Progress (2026-08-11)

`src/champions_ai/simulator/` holds a long-lived Node process (`bridge.js`) running Showdown's engine, driven from Python (`bridge.py`), plus `tracker.py` (protocol → `Observation`) and `choices.py` (domain actions → Showdown choice strings). The round trip is closed and tested: a full battle plays with both players driven entirely through domain types, so any disagreement between model and engine surfaces immediately as a rejected action.

ADR 0003 is now implemented, not just decided. `BattlePokemon.disabled_moves` and `available_specials` are populated from the engine's request, so Choice lock, Encore, Taunt, Disable, Torment and Mega availability all work without reimplementing a rule.

Two findings worth carrying forward:

- **No move data file is needed for legal-action generation.** Requests carry each active move's `target`, so `MoveData` is learned live. A shipped move table is only needed once we want data about moves that are *not* currently active — evaluation and search, not legality.
- **Stat Points are the one thing the engine never sends back.** Everything else about our own side comes from the request; the declared team is needed only to recover the point allocation.

`src/champions_ai/env/` adds `BattleEnv`, which owns the bridge and both trackers and exposes `reset` / `observation` / `decision` / `legal_actions` / `step`. Agents see `Observation` and `JointAction` and nothing else — a working random agent is four lines. Verified over 16 seeded battles with random agents on both sides: every generated action accepted, both sides winning, replay exact.

Running real battles caught three bugs that reasoning had missed, all the same mistake — **inventing data the engine never sent**:

- Forced switches were enumerated per slot independently, losing the case where one slot takes the last living replacement and the other must pass; with one bench Pokémon left this produced *no* legal action at all.
- A Pokémon locked mid-Solar Beam gets a request listing only that move, **with no `pp` field**. Defaulting the absence to 0 read as "no PP left" and filtered out its only legal move.
- The same entry also **omits `target`**, because a locked move's target is already fixed. Falling back to the move's usual target type produced a choice the engine rejected.

The general lesson, worth applying to the rest of the adapter: a missing field in a request means *unknown or not applicable*, never zero or a default. `BattlePokemon` now carries the engine's per-turn `choosable_moves` and `choosable_move_targets`, which take precedence over static move data — and move indices in a submitted choice refer to that trimmed list, not the declared moveset.

`src/champions_ai/data/` completes the milestone with `Trajectory`. Because a seeded battle replays exactly, a record stores the *inputs* — format, seed, packed teams, ordered decisions — rather than every state. A full battle is ~6KB, and the record cannot drift out of internal consistency the way a parallel copy of derived state can. Verified end to end: record, save, reload from disk, replay to the same winner, turn count and protocol.

Two decisions worth carrying into Milestone 5's data pipeline:

- **Observations are not stored.** Replaying regenerates them, so training data is produced by the *current* observation code rather than whatever version recorded it. `git_commit` is captured so a replay that no longer reproduces its recorded result is detectable rather than silently wrong.
- **`legal_action_count` is recorded per decision.** Choosing one action out of ninety is not the same evidence as choosing it out of two, and imitation learning needs that context to weight a choice.

### Definition of done — met

Two random agents repeatedly complete valid battles without environment corruption, verified over 16 seeded battles with every generated action accepted by the engine.

### Definition of done

Two random agents can repeatedly complete valid battles without environment corruption.

---

## Milestone 3 — Baseline Agents and Evaluation Harness

### Goal

Establish benchmark opponents before ML.

### Progress (2026-08-11)

`Agent` (`src/champions_ai/agents/base.py`) has two methods, not one: picking N of 6 happens *before* a battle exists, so there is no `Observation` to reason from — only a `TeamPreview`. Conflating them would force one of the two to misrepresent what information is available. This also put `TeamPreview`/`RevealedPokemon` to work for the first time.

`evaluate()` (`src/champions_ai/evaluation/runner.py`) is the ruler, built before the things it measures. It swaps sides every other battle, derives all battle seeds from one run seed, and reports a Wilson interval — chosen over the normal approximation because early runs are small and lopsided, exactly where the naive interval suggests impossible win rates and collapses to zero width at 0% and 100%. `is_significant` is conservative on purpose: an interval overlapping 0.5 means the run supports no claim either way, not that the agents are equal.

**Baseline established:** two `RandomAgent`s over 200 battles across **43 distinct matchups** from a generated `TeamPool` finished 103–97 (51.5%, 95% CI 44.6–58.3%, correctly reported not significant), reproducible from seed, ~28 battles/sec. A mirror match coming out skewed would have meant the harness itself was biased and every later comparison would inherit it, so this is an integration test.

Team-pool sampling landed *before* the first heuristic on purpose — while there is still nothing to overfit. Each matchup is played twice with the teams exchanged, so seat advantage and team strength both cancel by construction rather than being assumed to average out.

Running a real pool also exposed a crash worth recording: a generated team containing **Zoroark-Hisui** sends `|replace|` when Illusion breaks, a line that carries no HP field and reveals that the species recorded on switch-in was a *lie*. The tracker now corrects the identity in place, keeping the HP and status that belonged to the real Pokémon. Moves credited to the disguise while it held remain misattributed — a known limitation, since untangling them needs Illusion-aware bookkeeping.

### Agent 0: Random Agent

- [x] Select uniformly among legal joint actions. (`RandomAgent`, owning its own RNG so runs reproduce independently of unrelated code)

### Reference data (2026-08-15)

`src/champions_ai/dex/` loads species typing and base stats, move power/type/category/accuracy, and a resolved type-effectiveness matrix from `Dex.mod('champions')` via a `dexdump` bridge command. Refreshing the dump picks up a new regulation's roster; no table is maintained by hand.

Two things this confirmed and one it fixed:

- **Champions' roster is genuinely restricted**: 357 species and 500 moves, against mainline's ~1000+.
- **`accuracy: null` is not the same as 100.** A move that bypasses accuracy checks cannot be made to miss; a 100%-accurate one can.
- Levels were being read by splitting the details field on the letter `L`, so **Lopunny parsed as level "opunny"** — a silent, species-dependent crash that only a team pool would surface. Now matched on the `, L<number>` field.

`Dex` is deliberately separate from `MoveData`: `MoveData` is per-turn, engine-reported, and describes what may be chosen *now*; `Dex` is the unchanging half, loaded once. The tracker also now keeps the computed stats the engine sends for our own side, which damage calculation needs and which were previously discarded.

### Agent 1: Heuristic Agent — built, and measured

**Result: 289–11 over 300 battles across 74 matchups — a 96.3% win rate (95% CI 93.6–97.9%, significant), ahead in 72 of 74 matchups.** Average battle length fell from Random's ~10.7 turns to 5.4.

The 72/74 is the number that matters. Winning overall while losing most pairings would mean exploiting particular teams rather than playing better — precisely what team-pool sampling was added to expose.

Scoring is written to be legible rather than tuned: expected damage as a fraction of the target's remaining HP is the baseline currency, and everything else is priced against it. Each component emits a human-readable reason, which Milestone 4's recommendation system needs, and which let the unit tests assert on the *reasoning* rather than the win rate — a good score can hide bad logic.

Two judgement calls worth carrying forward:

- **A guaranteed knockout requires even the worst damage roll**, and is scored separately from one that needs a high roll. Treating an average as a certainty is how an agent leaves things alive at 3 HP.
- **Missing dex data scores neutrally, not last**, so a gap in the data cannot masquerade as a judgement about the move.

Implemented signals: expected damage, knockout certainty, type effectiveness, immunity avoidance, accuracy discounting, Protect valuation, switch cost. Not yet implemented from the list below: speed/priority reasoning, support-move value beyond a flat score, and board position.

### Agent 1: Heuristic Agent

Potential signals:

- expected damage;
- knockout probability;
- type effectiveness;
- speed / priority;
- protecting vulnerable Pokémon;
- avoiding obviously ineffective attacks;
- switching away from severe disadvantage;
- support-move value;
- board position.

### Agent 2: Simple Search Agent — built, and it did **not** help

**Result: 148–152 over 300 battles (49.3%, 95% CI 43.7–55.0%, not significant), ahead in 28/74 matchups.** Marginally *worse* than the heuristic against Random. Written up in `docs/experiments/0001-one-turn-search.md`.

Instrumenting live battles explains it: search picks a different action from the heuristic on **6% of turns**. Two policies that agree 94% of the time split a head-to-head near 50% however well the other 6% is reasoned. The lookahead is inert rather than wrong.

It is inert because **the opponent's moves are largely unknown** — a mean of ~3 revealed moves across their entire team per decision, 10% of decisions with none at all, in battles lasting 5–6 turns. A threat model built only on revealed moves has nothing to work with.

**The finding worth carrying:** at this depth and in this format, search depth is not the bottleneck — *opponent knowledge* is. That is direct evidence for the ordering of section 9's research questions 5 and 6, and a concrete argument for reaching opponent modelling (Milestone 10) before investing in deeper search (Milestone 11).

`SearchAgent` is kept as a baseline and as scaffolding — its threat model gains real inputs the moment a prior over unseen movesets exists. It is not the strongest agent; `HeuristicAgent` is.

Also landed: `evaluate_position`, which scores a board rather than an action — the hand-written baseline Milestone 7's learned value model is meant to replace.

### Agent 2: Simple Search Agent

Possible approaches:

- one-turn expected-value search;
- shallow expectimax;
- sampled opponent responses;
- limited lookahead.

### Evaluation harness

Support:

- [x] repeated matches; (`evaluate(..., battles=N)`)
- [x] side swapping; (every other battle, so a seat advantage cancels rather than being credited to an agent)
- [x] deterministic seeds; (whole run reproduces from one integer)
- [x] team-pool sampling; (`TeamPool`, with each matchup played twice from *exchanged* team assignments so team strength cancels rather than being credited to whichever agent drew it)
- [x] win rate;
- [x] confidence intervals; (Wilson, with a conservative `is_significant`)
- [ ] Elo or another rating method; (only meaningful once there are more than two agents)
- [x] per-matchup results; (`MatchResult.matchup_scores` — so a win rate resting on a few favourable pairings is visible rather than hidden in the aggregate)
- [x] battle logs; (`keep_trajectories=True` attaches replayable `Trajectory` records)
- [ ] runtime / decisions per second. (measured ad hoc at ~33 battles/sec; not yet reported by the harness)

---

## Milestone 4 — Recommendation System V1

### Status (2026-08-15): V1 built

`src/champions_ai/recommendation/` ranks legal actions with confidences and human-readable reasons, driven by the *same* scorer the agent plays with — a test asserts advice and play agree, since a recommender that suggests what the agent would not do is describing someone else.

Real output from a live position:

```text
TURN 1  --  considering 106 legal actions

1. Charizard: Solar Beam -> the opposing Garchomp | Garchomp: Rock Slide  64%
2. Charizard: Protect | Garchomp: Rock Slide                              16%
3. Charizard: Flamethrower -> the opposing Charizard | Garchomp: Rock Slide 7%
4. Other                                                                  13%

why: Solar Beam deals ~35% of Garchomp's remaining HP; Rock Slide deals ~94%
     of Charizard's remaining HP; knockout on a high roll; super effective
     (4x); 90% accurate
```

Two fixes came from reading real output rather than from tests: at the first softmax temperature a *decisive* recommendation displayed as 11%, and `Flamethrower -> Charizard` was ambiguous because mirror matches are routine in Reg M-B (now "the opposing Charizard" / "your Venusaur").

**Confidence is a share of a softmax over scores, not a win probability**, and is documented as such — a number shown to a human is read as a probability unless it says otherwise. A calibrated one comes from Milestone 7.

Known gap carried forward: the heuristic does not model what Mega Evolution does to stats, so `X` and `X (+mega)` score identically. Indistinguishable options are collapsed in the shortlist, which hides the gap rather than fixing it.

Still open from the deliverables below: search value and rollout value as alternative rankers, and the metrics (regret against a stronger reference, ranking stability, latency).

### Goal

Turn the decision engine into a player-facing action ranker.

### Input

Player observation + legal actions.

### Output

Ranked candidate actions.

Early recommendation approaches:

1. heuristic score;
2. search value;
3. simulated rollout value.

Potential metrics:

- chosen-action expected value;
- estimated win probability;
- regret relative to stronger search;
- action ranking stability;
- computation time.

Initially generate explanations from structured reasons, not an LLM.

---

## Milestone 5 — Data Pipeline and Expert Decision Dataset

### Goal

Create a trustworthy dataset for supervised learning and opponent modelling.

Potential data categories:

- simulated battles;
- self-play trajectories;
- manually labelled positions;
- publicly available battle data where permitted;
- high-level player decisions where legally and technically obtainable.

Every dataset should record:

```text
source
collection method
date
game / ruleset
regulation
battle format
schema version
license / usage considerations
processing version
```

Important split strategies may include:

- unseen battles;
- unseen players, if identity exists;
- unseen team compositions;
- future metagame period;
- different regulation when scientifically meaningful.

### Implementation status (2026-08-18)

Human replays are the only source of real expert decisions this project has, and the parsing half of the pipeline is built and validated against real ladder games:

- [x] `data/replay.py` — fetch/parse a replay, read per-player Elo, filter visible bots, flag turns no replay can observe;
- [x] `data/choices.py` — the **labels**: what each player actually chose, excluding four things that look like choices and are not;
- [x] `data/reconstruct.py` — the **features**: what each player could legally see at each decision point, with the own/opponent knowledge boundary enforced and leak-tested;
- [x] `data/collect.py` — collection from the public API. **The usage-terms gate is resolved (2026-08-18);** see the note below. 50 rated games collected as a first batch;
- [x] provenance records — `CollectionManifest` stores source, timestamp, git commit, filters and per-reason rejection counts next to the data, as section 4 requires;
- [ ] split strategy (unseen players / unseen teams / future period) for the collected set;
- [x] `evaluation/agreement.py` — the human-agreement benchmark that consumes both halves. Heuristic 44.1% vs a 21.3% random baseline; see section 12 and `docs/experiments/0002`.

Measured yield: **~3.1 usable free-choice labels per turn**, or roughly 18,000 labelled human decisions per day at observed replay volume. Details, including the moveset-recovery bias that inflates agreement, are in section 12's open questions.

### Usage terms — resolved 2026-08-18

Checked directly rather than assumed. **Programmatic access is the documented, intended path**: `WEB-API.md` in the Showdown client repository states that "most PS APIs that you would want to access programmatically are available by adding `.json` to the URL", documents `search.json` with `before=` pagination, and serves everything with `Access-Control-Allow-Origin: *`. Its single "obviously don't _scrape_ it" remark is, in context, about the **HTML replay page**, and steers readers toward this API rather than away from it. `replay.pokemonshowdown.com` publishes no robots.txt (404); `smogon.com`'s names only Amazonbot.

Two constraints follow from what the terms do **not** say, and both are now enforced in code rather than left to memory:

- **No licence covers the replay logs.** MIT covers Showdown's *server code*; the privacy policy does not mention replays at all. So the corpus is collected for local research use, `CollectionManifest.usage_note` carries the constraint alongside the data, and `data/replays/` is gitignored with the reason written next to it. **Derived statistics and model weights are a separate question from redistributing the logs.**
- **No rate limit is published**, which makes throttling our courtesy obligation rather than their permission. Every request passes through a deliberate delay (1/sec as used), and anything already on disk is never refetched — including *rejected* replays, so re-running with a looser filter costs no traffic.

First batch, 2026-08-18: 436 listings considered → **50 kept**, 344 network requests. Rejections are themselves informative — **101 bot games (23%)**, 213 below the 1500 bar, 72 unrated. Bot names are visible in the listing, so those are skipped before any download.

---

## Milestone 6 — Imitation Learning

### Goal

Predict strong player actions from battle observations.

Initial formulation:

```text
Observation -> Action Distribution
```

Potential architecture progression:

1. simple MLP baseline;
2. embedding-based structured network;
3. attention/transformer-style representation if justified.

Metrics:

- top-1 action accuracy;
- top-k action accuracy;
- negative log likelihood;
- calibration;
- expected battle value;
- full-battle win rate.

High action-prediction accuracy does not automatically imply a strong autonomous agent.

---

## Milestone 7 — Value Model / Win Probability Model

### Goal

Estimate:

```text
P(win | observation)
```

Uses:

- recommendation ranking;
- search evaluation;
- rollout truncation;
- training signal;
- player-facing win probability;
- turning-point analysis.

Metrics:

- log loss;
- Brier score;
- calibration error;
- reliability plots;
- accuracy/AUC where useful.

---

## Milestone 8 — Reinforcement Learning

### Goal

Learn policies optimized for winning rather than merely copying observed actions.

Start only after:

- environment is stable;
- Random baseline exists;
- Heuristic baseline exists;
- evaluation harness exists;
- state/action leakage tests exist;
- runtime is acceptable.

Candidate approaches may include:

- policy gradient;
- actor-critic;
- PPO-style algorithms;
- value-based methods where suitable;
- offline RL if a suitable dataset exists.

Default research reward:

```text
win  = +1
loss = -1
```

Any reward shaping must be documented and evaluated carefully.

---

## Milestone 9 — Self-Play Curriculum

### Goal

Train against a diverse and evolving opponent population.

Maintain an opponent pool such as:

```text
Random
Heuristic
Search
Older checkpoints
Current checkpoints
Specialized strategies
Potential expert-inspired agents
```

Evaluate for:

- exploitability;
- strategy collapse;
- overfitting to a single opponent;
- forgetting;
- team-specific overfitting.

---

## Milestone 10 — Opponent Modelling and Belief State

### Goal

Model information that is uncertain or hidden.

Conceptually:

```text
P(hidden opponent set | observations so far)
```

Possible hidden variables:

- move set;
- item;
- ability;
- stat investment;
- strategic archetype.

Potential observations:

- revealed move;
- damage dealt;
- damage received;
- speed ordering;
- switch behavior;
- ability activation;
- item activation.

Start with an interpretable probabilistic approach before introducing more complex learned inference.

---

## Milestone 11 — Search + Learned Policy Hybrid

### Goal

Combine learned intuition with tactical search.

Potential architecture:

```text
Observation
    |
    +--> Policy model -> promising actions
    |
    +--> Value model -> state evaluation
    |
    `--> Opponent model -> opponent action distribution

             |
             v

      Selective Search / Rollouts

             |
             v

       Final Action Ranking
```

This is a major long-term target.

---

## Milestone 12 — Recommendation System V2

### Goal

Create a useful battle-analysis product rather than only an agent benchmark.

Possible features:

### Before battle

- matchup overview;
- likely opponent archetype;
- lead recommendation;
- risk analysis.

### During battle

- ranked joint actions;
- safe/aggressive alternatives;
- win probability;
- opponent-action predictions;
- revealed-information tracking.

### After battle

- key turning points;
- high-regret decisions;
- alternative actions;
- win-probability graph;
- recurring mistakes.

---

## Milestone 13 — Team Recommendation and Team Building

### Goal

Extend from battle decisions into roster decisions.

Possible tasks:

- Pokémon recommendation;
- teammate synergy;
- moveset selection;
- item selection;
- ability choice;
- stat spread recommendation;
- lead-pair recommendation;
- matchup coverage analysis.

Potential methods:

- metagame statistics;
- recommender approaches;
- graph-based synergy models;
- supervised ranking;
- optimization/search;
- simulation-based evaluation.

---

### Implementation status (2026-08-18)

**Team Preview selection is implemented** — `HeuristicAgent.select_team_preview`, with `explain_team_preview` for the recommendation system. This was the project's original stated use case ("which 4 pokémon should I pick after seeing the opponent's 6") and had been silently inherited from the base class, which takes the declared order and ignores the opponent entirely.

Scored as **coverage**, not as a sum of individually strong Pokémon: for each of their six, take our best answer among the four under consideration, and add those up. Four Pokémon that all beat the same threat and lose to everything else score badly, which is the intent. Six choose four is fifteen combinations, so the exhaustive answer is cheaper than approximating it.

The matchup maths lives in `mechanics/matchup.py` rather than in the agent, because **switching asks the same question** — is what I would bring in better placed than what is out — and that is the next gap to close. It also absorbed the assumed-attack prior the Protect work introduced, so "we cannot see their moves" is modelled in exactly one place.

**Measured, and it is no better than guessing — the larger sample made this worse, not better:**

```
 53 decisions (50 games) : 56.6%   CI 43.3%-69.0%
547 decisions (500 games): 48.4%   CI 44.3%-52.6%    baseline 50.0%
```

The first figure looked mildly encouraging. At ten times the data the lead ordering sits *below* chance with the interval straddling it, so **the honest reading is that it carries no signal at all.** Same shape as experiment 0004: a small-sample number that flattered, then did not survive.

Worth separating two decisions that were being treated as one:

- **which four to bring** is scored as coverage and is *not* measured at all (see the circularity trap below), so nothing here says it is wrong;
- **which two lead** is what these numbers cover, and "lead with the best average matchup" appears to be simply the wrong rule. Real leads turn on speed control, Fake Out pressure, Trick Room setters and what the opponent is likely to lead — none of which an average-matchup score expresses.

One caveat on the measurement itself: a decision is skipped when any of the four brought Pokémon never revealed a move (453 of 1,000 were), which selects for longer games where all four acted. That is a mild bias of unknown direction, not an explanation for a null result.

Two things limit that measurement, and the first is a trap worth recording:

- **"Did we pick the same four?" is deliberately not measured.** A replay reveals a Pokémon's moves only if it was brought *and* used them, so the two left behind have no moveset, would score zero offence, and would never be picked. We would "predict" the human's four for a circular reason. That is a self-fulfilling metric, so only the lead ordering *among the four they brought* is scored.
- Even that tilts our way: leads spend more turns on the field, so more of their moves are revealed, and the scoring rewards a known moveset.

53 scorable decisions gives a ±13 point interval. **This needs more games, not more code.**

## Milestone 14 — User Interface and Productization

### Goal

Expose the system in an intuitive interface.

Potential components:

- FastAPI inference service;
- React/TypeScript frontend;
- battle-state editor;
- replay viewer;
- model comparison UI;
- recommendation explanation panel;
- experiment dashboard.

---

## Milestone 15 — Advanced Research Directions

Possible future areas:

- multi-agent learning;
- distributional value modelling;
- risk-sensitive decision making;
- metagame adaptation;
- continual learning;
- uncertainty-aware recommendations;
- counterfactual analysis;
- representation learning;
- human + AI evaluation.

These are research directions, not commitments.

# 8. Evaluation Framework

## Core battle metrics

Track:

- win rate;
- Elo / rating;
- matchup-specific win rate;
- average battle length;
- decision latency;
- invalid-action rate;
- timeout rate.

## Recommendation metrics

Track:

- top-1 agreement;
- top-k agreement;
- action value;
- regret;
- confidence calibration;
- decision latency.

## The missing benchmark

Everything measured so far is against agents we wrote ourselves. Beating Random 96.3% says nothing about how the system compares to a competent human — there is currently **no external reference point at all**, and that is the largest gap in knowing whether the project is actually good.

Human replays supply one **without playing anyone**, which matters because automating ladder play is explicitly out of scope (section 3). On a held-out set of real games, the agent can be scored on how often it chooses what the human chose, and on how its evaluation of a position compares with how that game actually turned out. That is an external benchmark obtained purely by observation.

This is what section 9's research questions 3 and 4 are asking, and it should be built before, not after, investing in RL — otherwise a self-play agent can only be measured against itself.

## Generalization tests

Evaluate on:

- unseen team compositions;
- unseen opponent agents;
- different seeds;
- held-out battle trajectories;
- metagame shifts;
- future regulations where compatible.

# 9. Initial ML Research Questions

The project should eventually investigate questions such as:

1. How strong can a hand-built heuristic policy become?
2. How much does shallow search improve over static heuristics?
3. How accurately can expert actions be predicted?
4. Does imitation accuracy correlate with battle win rate?
5. How much does explicit hidden-information modelling help?
6. Does a learned opponent model outperform simple empirical priors?
7. How well does self-play generalize to unseen team compositions?
8. Does policy-guided search outperform either policy or search alone?
9. How quickly do models become stale after regulation/metagame changes?
10. Can calibrated uncertainty identify positions where the recommender should avoid strong claims?

These questions are more important than committing early to any specific neural architecture.

# 10. Current Project Decisions

| Decision | Current choice |
|---|---|
| Game | Pokémon Champions |
| Initial format | Double Battles |
| Competitive orientation | VGC-style |
| Core language | Python |
| Development style | Simulator-first |
| Simulator strategy | Drive Pokémon Showdown's `sim` battle engine directly and headlessly (via `BattleStream` — no server, accounts, or matchmaking layer), bridged to Python over a subprocess/stdio protocol we own. Not `poke-env`: that talks to a *running* Showdown server over WebSocket, which is unnecessary overhead for local/self-play use and imposes its own object model where we want our own `BattleState`/`Observation`/`Action` types. Showdown already models Champions' ranked formats directly (see Regulation M-B below), which de-risks this significantly — reconsider only if Showdown's implementation is found to diverge from live Champions mechanics. |
| Initial regulation | Gen 9 **VGC 2026 Regulation M-B** (Double Battles) — Champions' current ranked format as of 2026-08-10 (running through late Aug/early Sep 2026). Singles equivalent on Showdown is "BSS Regulation M-B"; not in initial scope. Regulations rotate over time — revisit this value periodically rather than treating it as permanent. |
| Initial intelligence | Heuristics + search |
| First ML stage | Imitation learning |
| RL timing | After stable baselines/evaluation |
| Partial observability | Explicitly modelled |
| Regulations | Configurable/versioned |
| Primary autonomous metric | Battle win rate / rating |
| Primary recommendation goal | Rank legal actions |
| Live client automation | Out of scope for now |
| UI | Later milestone |
| Agent coding tools | Codex + Claude or equivalent |

# 11. Immediate Project Backlog

## P0 — Do first

- [ ] Create repository skeleton.
- [ ] Add packaging/test configuration.
- [ ] Create `README.md`.
- [ ] Define initial supported Champions regulation.
- [ ] Write ADR for simulator strategy.
- [ ] Define `BattleState`.
- [ ] Define `Observation`.
- [ ] Define `Action`.
- [ ] Define `JointAction`.
- [ ] Define `Regulation`.
- [ ] Add JSON schemas / serialization.
- [ ] Add hidden-information tests.
- [ ] Add legal-action tests.

## P1 — Next

- [ ] Build/integrate battle environment.
- [ ] Implement Random Agent.
- [ ] Run automated random-vs-random battles.
- [ ] Add structured battle logs.
- [ ] Implement tournament runner.
- [ ] Add win-rate statistics.
- [ ] Implement heuristic damage baseline.
- [ ] Add first fixed benchmark positions.

## P2 — Once stable

- [ ] Implement shallow search.
- [ ] Build recommendation CLI/API.
- [ ] Establish data schema for trajectories.
- [ ] Evaluate legal sources of expert battle data.
- [ ] Build first supervised dataset.
- [ ] Train simple imitation baseline.
- [ ] Compare imitation agent against heuristic/search baselines.

# 12. First Concrete End-to-End Target

Before serious deep learning, achieve this:

```text
1. Load regulation
2. Load two teams
3. Start simulated Double Battle
4. Generate player observation
5. Enumerate legal joint actions
6. Random/heuristic agents choose actions
7. Resolve battle until completion
8. Save structured replay
9. Run 1,000+ automated evaluation battles
10. Produce reproducible win-rate/rating report
```

This is **Version 0.1** of the research platform.

# 13. Suggested Version Progression

## v0.1 — Battle Research Platform

- domain model;
- simulator/environment;
- legal actions;
- Random Agent;
- Heuristic Agent;
- evaluation harness.

## v0.2 — Tactical Recommendation Engine

- search;
- action ranking;
- basic explanation;
- CLI/API.

## v0.3 — Imitation Learning

- dataset pipeline;
- action prediction;
- learned policy;
- calibrated probabilities.

## v0.4 — Autonomous ML Agent

- value model;
- RL;
- full-battle evaluation.

## v0.5 — Self-Play

- checkpoint league;
- population evaluation;
- stronger policy.

## v0.6 — Partial-Information Intelligence

- opponent modelling;
- belief state;
- uncertainty.

## v0.7 — Hybrid Competitive Agent

- learned policy;
- learned value;
- opponent model;
- selective search.

## v0.8 — Player Assistant

- web interface;
- recommendations;
- explanations;
- post-game analysis.

## v0.9 — Team Intelligence

- team recommendation;
- synergy modelling;
- matchup analytics.

## v1.0 — Portfolio / Research Release

A documented, reproducible system with:

- tested environment;
- multiple baseline agents;
- trained ML agents;
- strong evaluation suite;
- recommendation interface;
- technical write-up;
- clear experimental findings.

# 14. What Would Make This Project Successful

Success is not defined only as "the AI becomes good at Pokémon."

A strong outcome should demonstrate:

## Software engineering

- clean architecture;
- testable domain logic;
- reproducible pipelines;
- reliable simulation;
- usable API/UI.

## Machine learning

- careful feature/state representation;
- strong baselines;
- supervised learning;
- RL/self-play where justified;
- calibrated models;
- rigorous evaluation.

## AI research thinking

- partial observability;
- opponent modelling;
- search;
- exploration;
- generalization;
- nonstationary metagame;
- uncertainty.

## Product thinking

- useful recommendations;
- understandable explanations;
- latency awareness;
- user-facing confidence;
- post-battle feedback.

The final repository should tell a coherent story from **simple baseline to sophisticated decision system**.

# 15. Open Questions

- [x] Which simulator strategy should be used? — **Resolved 2026-08-10:** drive Showdown's `sim` engine directly via `BattleStream`, no server/`poke-env` (see section 10). Write the ADR in `docs/decisions/` during Milestone 0 to record alternatives considered.
- [ ] How closely does Showdown's Regulation M-B implementation match live Champions mechanics in practice? (Assumed close given Showdown models the format directly, but not yet verified against the real client.)
- [ ] What is the best canonical action representation for Double Battles?
- [ ] How should simultaneous joint actions be encoded for neural models?
- [~] Which public/expert battle datasets are legally and practically usable? — **Partly answered 2026-08-15.** Real human replays for our exact format exist in volume: `replay.pokemonshowdown.com/search.json?format=gen9championsvgc2026regmb` returns current Reg M-B games, and the timestamps span ~50 replays per 70 minutes — on the order of **1,000 human games per day**. So imitation learning (Milestone 6) is *not* blocked for want of data.
  Three things still to settle before building on it:
  - **Terms of use.** Bulk downloading needs Smogon's usage terms checked first. This is data collection from public pages, not matchmaking automation or ladder botting, so it does not touch the scope guardrails in `AGENTS.md` section 3 — but "public" is not the same as "licensed for redistribution".
  - **Bot contamination.** Accounts like `pcrlbot12d159c39a` appear repeatedly in the listing. Training an imitation model on bot games and calling it "expert play" would be a silent quality failure, so replays need filtering by player identity before use.
  - **Ratings are available after all.** The search listing omits them, but the replay itself carries Elo on its player lines (`|player|p1|audino316|byron|1553`, `|player|p2|sauan2|2|1643`) plus a top-level `rating` field. Filtering for high-level play is therefore possible without any external source.

**The real constraint is what a replay does *not* contain.** A replay is the *spectator* view:

- **HP is a percentage for both sides**, never the exact value either player saw of their own team.
- **There are no `|request|` lines**, so the legal action set a player was choosing from is absent — we see what they picked, not what they could have picked.
- **Movesets and PP are absent**; moves become known only as they are used.

So a model trained on replays learns "what would a player do given the *spectator* view", which is strictly less information than the player actually had. That is workable, and it is not the same thing as imitating a player — the difference should be stated in any result, not glossed. Reconstructing a decision point must also use only what was revealed *up to that turn*: the full log makes it trivially easy to leak later moves and the outcome backwards into a feature, which `AGENTS.md` explicitly forbids.

Verified directly against three replays (2026-08-15), which also turned up four things worth knowing before building the dataset:

- **Some decisions are simply unobservable.** `|cant|` appears when a Pokémon was unable to act — paralysis, flinch, a disabled move. The log then records *that it could not move*, never the action its player actually chose. Those decision points must be dropped from a training set rather than treated as a choice, or the model learns from labels that were never a decision.
- **Open Team Sheets was accepted in 0 of 3 games.** It needs both players to opt in, so assume sheets are absent; handle `|showteam|` if it ever appears rather than relying on it.
- **Mega Evolution is visible** — `|-mega|` followed by `|detailschange|` to the Mega forme. So Mega usage *is* learnable from replays, which matters given the heuristic currently cannot tell a Mega action apart from a normal one.
- **The top-level `rating` field does not match the player lines.** One replay reported `rating: 1578` while its players were 1553 and 1643 — neither value, nor their mean. Its meaning is unclear, so `parse_ratings` reads the per-player Elo from `|player|` lines and the top-level field is ignored.

The event vocabulary is also wider than the tracker handled. Unknown line types are skipped rather than failing, so this degrades quietly — so it is now **measured**, not assumed: `simulator/coverage.py` classifies every protocol line as handled, unhandled, or cosmetic.

**Measured against real human replays: 75.6% → 97.2%** after closing the gaps it named. The remaining 2.8% is `|cant|` (already treated as an unobservable decision), `|teampreview|`, and `|-fieldactivate|`.

Two things that exercise found, both worth more than the number:

- **`|detailschange|` was unhandled, which was a *live* bug rather than a replay one.** It is the line sent when a Pokémon Mega Evolves, so an opponent that Mega'd kept being modelled as its base forme for the rest of the battle — with the wrong base stats behind every damage estimate the heuristic makes, in a format where Mega is central.
- **Handler dispatch conflated major and minor lines.** Names were derived by stripping a leading dash, so `|start|` (the battle begins) and `|-start|` (a volatile condition begins) resolved to the same handler and crashed on the first real battle. They are now separate namespaces, with a test asserting they cannot collide.

Coverage should be re-measured whenever replays are ingested in volume, rather than assumed to have held.

### Recovering human choices (2026-08-15)

`data/choices.py` extracts what each player actually chose. Most of the work is *refusing* to count things that look like choices but are not — each would quietly poison a training set:

- a move used `[from]` Sleep Talk or Dancer was selected by the game, not the player;
- `|drag|` is a Pokémon forced out by Roar, which its owner did not ask for;
- a switch replacing something that just fainted is a **replacement** decision, a different question from choosing to switch a healthy Pokémon out;
- the **opening leads appear as switches before turn 1**, but are the outcome of Team Preview. This one is not theoretical: separating them dropped the apparent free-choice count across three replays from 71 to 59, so leaving them in would have inflated how often players appear to switch by about 20%;
- `|cant|` means the choice never executed, so that player's turn is dropped entirely.

Measured on real replays: 19 turns produce 39 decision points and **~3.1 usable free-choice labels per turn**. At ~1,000 games/day of roughly 6 turns each, that is on the order of 18,000 labelled human decisions per day — ample for imitation learning, subject to the usage-terms check.

### Reconstructing what each player saw (2026-08-18)

`data/reconstruct.py` supplies the other half of a supervised example: `choices.py` recovers *what* a player did, this recovers *what they were looking at*. Both trackers are fed the same spectator log, each treating the other player as its opponent, which makes the knowledge boundary asymmetric on purpose:

- the **acting player's own side** is assembled from the whole replay. They knew their four picks and their movesets from the moment the battle started, so reading a move off turn 9 to populate their turn 2 view recovers knowledge they genuinely had;
- the **opponent's side** is limited to what the log had revealed by that turn. Anything else is the future-leak `AGENTS.md` forbids, and it flatters results — the agent would "predict" a human's move while secretly knowing what the human did not.

Validated on three real ladder replays — 33 decision points, 59 labels:

- the move the human chose was in the reconstructed action set **58 of 58** times, so every move label is scorable;
- **zero future leaks**, checked against ground truth read straight off the log rather than against the tracker that produced the observation;
- 5.8 legal actions per slot on average.

**The caveat is measured, not asserted.** Only **1.81 of 4 moves** are recoverable per Pokémon — a move never used leaves no trace — and 13 of 132 Pokémon-views had *none*. A smaller action set means fewer distractors, so this **inflates** agreement. Every decision therefore carries `known_move_counts`, and any agreement figure quoted without it overstates the result.

Two live bugs surfaced from this work, neither of them replay-specific:

- **`MoveData` was missing the `allies` move target.** Showdown's vocabulary has fifteen values and ours had fourteen. Champions uses `allies` for **Howl** and **Life Dew**, both ordinary VGC moves, so the tracker raised a `ValidationError` while parsing the engine's own request payload the moment either was active. Now guarded by an integration test that checks our enum against the real dex dump — a unit test could not have caught it, because the value we had never heard of was missing from our test data too.
- **`|teamsize|` reports the *picked* team size, not the declared one.** Verified against both a live engine battle and a published replay: it is emitted *after* Team Preview and reads `|teamsize|p1|4`. The tracker was already correct; this is recorded because the opposite assumption is the natural one and would silently double the opponent's apparent hidden bench.

### The human-agreement benchmark (2026-08-18)

`evaluation/agreement.py` scores an agent against what a rated human actually did. **This is the first measurement in the project that is not our code grading our own code** — every win rate before it compares agents we wrote against agents we wrote, so a shared blind spot is invisible.

Measured on **50 rated ladder games** (both players ≥1500, Elo 1500–1782, median 1589), 603 decision points, **1,061 free-choice labels** (full write-up in `docs/experiments/0002-human-agreement.md`):

```
heuristic-v1  418/1061 = 39.4%  (95% CI 36.5%-42.4%)  vs 21.1% random   beats random: yes
random        228/1061 = 21.5%  (95% CI 19.1%-24.1%)  vs 21.1% random   beats random: no
```

**`RandomAgent` landing on 21.5% against its own predicted 21.1% baseline is the check that matters** — the baseline is computed analytically rather than sampled, and a random policy lands where the theory says it should. That validates the metric before any claim is made with it.

A 3-game pilot first reported 44.1% (CI 32.2–56.7%). The 50-game figure sits inside that interval, so nothing contradicts, but **the honest number is ~39%** and the interval narrowed from 24 points to 6. Recorded because the pilot figure was published first.

Agreement is *not* strength: it rewards imitating the reference player, so a genuinely better move counts as a miss. Three numbers are reported with every figure because each moves it more than the agent does — the random baseline, the action-set size, and what could not be scored.

**The disagreements are the useful part.** Of 643: **37% are status moves the heuristic passed over** (Protect 90, Tailwind 20, Encore 14, Hypnosis 10, Trick Room 8, Rage Powder 8…), and **16% are the right move aimed at the wrong slot**.

Splitting by action kind exposed something the pilot could not see — it contained exactly one switch label:

```
move labels  :  944, agreed on 410  (43.4%)
switch labels:  117, agreed on   8  ( 6.8%)
```

**Humans switch on 11.0% of decisions; the heuristic switches on 1.7%.** All 117 switch labels had a matching switch available in our action set, so this is policy, not a reconstruction gap.

That is one finding, not two. Protect and switching are both *decisions not to attack this turn*, and the heuristic attacks on 98.3% of turns against a human 89%. Every action is priced in damage dealt **now**, so anything paying off later — Protect, Tailwind, Trick Room, Rage Powder, switching — is invisible to it. Experiment 0001 reached the same limitation from the opposite direction, where one-turn search was inert because opponent replies were unknown. Both say the bottleneck is knowledge of what happens next, not search depth.

### Acting on it: Protect scoring (2026-08-18)

First change driven by the benchmark rather than by intuition. Full write-up in `docs/experiments/0003-protect-scoring.md`.

Protect carried a flat 18 points plus a bonus below 35% HP, which cannot express either case that matters — a healthy Pokemon facing a knockout should protect, a weakened one facing nothing should not. It is now worth **the damage it avoids**, in the same currency as damage dealt, discounted by the engine's own stall rule (each consecutive use succeeds a third as often). The old code also matched the literal move id `protect` and silently missed Detect, Spiky Shield, King's Shield and the rest.

Paired on identical labels — **McNemar's test, because comparing overlapping confidence intervals is the wrong test when both runs see the same 1,061 labels**:

```
old  418/1061 = 39.4%      only OLD agreed : 10
new  439/1061 = 41.4%      only NEW agreed : 31
McNemar chi2 = 9.76 on 41 discordant labels -> significant at p<0.01
```

It is calibrated rather than merely more eager, which was the risk: humans protect on **14.1%** of decisions, the heuristic now on **14.2%**.

**Play strength did not move, and that is stated rather than buried.** 800 battles against the previous version give 51.6% (CI 48.2–55.1%, not significant); both score ~96% against Random. A 200-battle run had suggested 55.5% — noise, recorded because stopping there would have produced a false claim.

Two lessons carried forward:

- **Self-play head-to-head is the wrong primary instrument for scoring tweaks.** The two versions differ on ~14% of slots and agree on half of those, so they split near 50% whatever the merits — the same effect experiment 0001 hit. Worse, self-play cannot see a blind spot both agents share. Human agreement detected at p<0.01 a change that 800 battles could not distinguish from noise. Use self-play to confirm no regression; use agreement to detect improvement.
- The change was **kept without claiming it wins more**: better-motivated, fixes a real coverage bug, replaces a magic constant with the game's rule, measurably closer to human judgement, no measurable cost.

Also fixed on the way, a live bug: `|-singleturn|` effects never expired, so a Pokemon that used Protect once read as protected for the rest of the battle. The handler's own docstring said the point was that consecutive Protects grow likely to fail — which a permanent flag cannot express. Effects now expire at the turn boundary and a separate streak carries the signal, tracked for both sides.
- [ ] What information does the Champions client expose during a battle?
- [x] What should the first supported regulation be? — **Resolved 2026-08-10:** Gen 9 VGC 2026 Regulation M-B (Doubles). Revisit when the regulation rotates.
- [ ] How should team preview and lead selection be represented?
- [ ] What rating system should be used for internal agents?
- [ ] What latency budget should the recommendation system target?
- [x] How should special mechanics be represented generically across regulations? — **Resolved 2026-08-11:** as a named mechanic (`SpecialMechanic`, using Showdown's own choice-string vocabulary — `mega`/`terastallize`/`dynamax`/`zmove`/`ultraburst`) carried on `MoveAction.special`, with each `Regulation` declaring which it enables via `special_mechanics`. A regulation turning Terastallization back on is then a data change, not a schema change. Replaced an earlier `MoveAction.mega: bool` that had baked one mechanic into the type.
- [x] Should search operate directly in the full simulator or through a faster approximate model? — **Measured 2026-08-15:** the full simulator is viable for interactive use, and reimplementing it is not warranted. Showdown supports `Battle.toJSON()`/`fromJSON()`; a battle serialises to ~27 KB in ~0.7 ms and restores in ~1.4 ms, and the fork advances in **complete isolation** from the original (verified: fork took damage and reached turn 2 while the original stayed untouched at turn 1). That is ~460 forks/sec.
  - **Recommendation/analysis use** (one decision, ~1 s budget): comfortably affordable — hundreds of exact forks per decision.
  - **RL self-play** (millions of decisions): far too slow at ~2.2 ms per node; end-to-end battle throughput is currently ~35–50 battles/sec and forking would collapse it. This is where an approximate model earns its place.
  - **Reimplementing battle resolution stays ruled out** (ADR 0001). Forking is exact by construction; a reimplementation of 500 moves plus abilities and items would diverge silently, and silent divergence means searching a game that is not the real game.
  - Not urgent regardless: `docs/experiments/0001` found search depth is not the current bottleneck.
- [ ] How should common opponent-set priors be constructed?
- [ ] When does a neural architecture become justified over a structured baseline?

These should not be resolved by assumption when the answer materially affects architecture.

# 16. Project North Star

The long-term system should eventually be able to answer:

> **Given everything a strong Pokémon Champions player could legitimately know at this point in the battle, what should I do, how confident are you, what do you think the opponent will do, and why?**

The autonomous version should demonstrate the quality of that answer through repeatable competitive performance.

# 17. Living-Document Rule

This file contains the project vision, roadmap, milestones, and research direction.

Detailed implementation decisions should move into `docs/`, while repository-wide coding-agent behavior belongs in `AGENTS.md`.

Update this plan when scope, milestones, or long-term technical direction changes.
