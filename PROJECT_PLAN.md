# Pokémon Champions AI — Long-Term Project Plan

> **Status:** Living project roadmap  
> **Last updated:** 2026-08-10  
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
  - **No rating in the listing.** The search endpoint gives players and format but no Elo, so "high-level play" needs a separate signal — ladder standings, or restricting to players who appear in tournament results.
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
