# Pokémon Champions AI — Agent Instructions

> **Purpose:** Repository-wide instructions for AI coding agents such as Codex and Claude.  
> **Project:** Pokémon Champions AI

## 1. Read Before Working

Before making changes, agents must:

1. Read this file.
2. Read `PROJECT_PLAN.md` for project direction and milestone priorities.
3. Inspect the existing repository, tests, configuration, and current milestone.
4. Prefer small, testable, reversible changes over large speculative rewrites.

## 2. Project Principles

### Simulator-first

Develop the AI against a deterministic, testable battle environment or simulator interface before considering live-game integration.

The core research problem is decision-making, not screen automation.

Current simulator strategy (see `PROJECT_PLAN.md` section 10): drive Pokémon Showdown's `sim` battle engine directly and headlessly (via `BattleStream`, no server/account/matchmaking layer), bridged to Python over a subprocess/stdio protocol. Not `poke-env`: that connects to a running Showdown server over WebSocket, which is unneeded overhead here and imposes its own object model where this project wants its own `BattleState`/`Observation`/`Action` types. Showdown models Champions' ranked formats directly, so this is treated as the mechanics source of truth until evidence shows it diverges from the live client. Do not silently switch to a from-scratch engine, nor add `poke-env` as a dependency, without updating the ADR in `docs/decisions/`.

### Correctness before intelligence

Battle mechanics are correctness-critical software.

Do not build advanced ML on top of mechanics that have not been tested.

Add tests for nontrivial mechanics and regression tests for discovered bugs.

### Hidden information must remain hidden

Competitive Pokémon is partially observable.

The project must explicitly distinguish:

```text
True Battle State
        |
        +--> Player Observation
        |
        +--> Opponent Observation
```

Models intended to behave like real players must consume observations, not omniscient simulator state.

In this repository that boundary is concrete: `Observation.from_battle_state(state, player)` is the only sanctioned path from `BattleState` to anything an agent sees. Agents, models, and feature encoders take an `Observation`; anything reaching for `BattleState` directly is a bug. When adding a field to an observed type, add a test proving the hidden case stays hidden — and verify that test is non-vacuous by temporarily breaking the masking and watching it fail.

Never leak information such as:

- unrevealed opponent moves;
- unrevealed items;
- exact hidden stats not inferable by the player;
- future turns;
- final battle outcome into input features;
- opponent action before the player decision;
- validation/test data into training.

### Baselines before deep learning

Do not introduce sophisticated ML before meaningful baselines exist.

Expected progression:

```text
Random Agent
    |
    v
Heuristic Agent
    |
    v
Search Agent
    |
    v
Imitation Learning
    |
    v
Reinforcement Learning
    |
    v
Self-Play
    |
    v
Hybrid Policy + Search + Opponent Model
```

### Evaluation before claims

Never report that an agent/model improved without running the relevant evaluation suite.

Model comparisons must keep the evaluation setup controlled and record:

- model/checkpoint;
- git commit;
- configuration;
- regulation;
- team pool;
- opponent pool;
- number of games;
- random seeds;
- side assignment method;
- primary metrics.

### Regulations are configurable

Do not hardcode a Pokémon Champions regulation as permanent.

Regulations must be represented as data/configuration and versioned where appropriate.

Current initial target: Gen 9 VGC 2026 Regulation M-B (Double Battles), Champions' current ranked format as of 2026-08-10. This will rotate — do not hardcode it outside the regulation config.

### Reproducibility matters

Training/evaluation runs should record:

- git commit;
- environment/dependency version;
- random seeds;
- dataset version;
- regulation;
- feature/schema version;
- model architecture;
- hyperparameters;
- team pool;
- opponent pool.

A checkpoint without provenance should not be used as a benchmark.

## 3. Scope Guardrails

Unless `PROJECT_PLAN.md` is explicitly changed, agents should not add:

- automation of taps/clicks in the live Pokémon Champions client;
- account farming;
- matchmaking automation;
- anti-cheat bypasses;
- reverse engineering of private game protocols;
- Ranked Battle botting;
- large frontend work before the decision engine is useful.

If live-game automation is ever considered, it must first be added to project scope after a separate Terms-of-Service/policy review.

## 4. Architecture Rules

Do not silently change:

- battle-state semantics;
- observation semantics;
- action representation;
- legal-action behavior;
- regulation handling;
- evaluation methodology;
- dataset definitions;
- repository-wide architectural decisions.

Domain model objects (`src/champions_ai/domain/`) are immutable snapshots, not mutable state: state transitions (e.g. `BattlePokemon.with_damage`, `Boosts.clamped_add`) return a new instance rather than mutating in place. This keeps a battle's history a plain sequence of states, which matters for replay, debugging, and later training-data generation. Follow this pattern for new domain types rather than introducing mutable ones.

Major architectural decisions should be documented in `docs/decisions/` as ADRs.

Suggested ADR structure:

```text
Context
Decision
Alternatives considered
Consequences
Date
```

## 5. Model and Experiment Rules

Agents may implement experiments, but should not invent scientific conclusions.

Every experiment should be able to answer:

- What hypothesis is being tested?
- What baseline is being compared against?
- What information is available to the agent?
- What metric determines whether the change helped?
- Can the result be reproduced?
- Does the improvement generalize beyond the training teams/opponents?

Store meaningful experiment summaries under:

```text
docs/experiments/
```

Recommended template:

```text
Experiment ID:
Date:
Git commit:
Hypothesis:
Model:
Dataset:
Ruleset/regulation:
Training config:
Baseline:
Evaluation opponent pool:
Primary metric:
Result:
Conclusion:
Next action:
```

Failed experiments should be documented when they provide useful information.

## 6. Testing Requirements

### Unit tests

Use for pure functions and domain rules.

### Mechanics tests

High priority. Add regression tests for discovered mechanics bugs.

### Integration tests

Examples:

- two agents complete a battle;
- replay reproduces the same battle;
- legal-action masking matches the environment;
- observation does not expose hidden fields.

### ML smoke tests

Training scripts should support tiny fast configurations that verify:

- model forward pass;
- backpropagation;
- checkpoint save/load;
- evaluation;
- deterministic data pipeline behavior where practical.

## 7. Agent Interface Guidance

Autonomous agents should share a common interface similar to:

```python
class Agent:
    def select_action(self, observation, legal_actions):
        ...
```

A richer future interface may return:

```python
ActionDecision(
    action=...,
    scores=...,
    probabilities=...,
    value_estimate=...,
    metadata=...,
)
```

Recommendation systems and autonomous agents should share this output structure where practical.

## 8. Battle Logging

Simulated battles should be stored as structured trajectories, not only human-readable logs.

Conceptually:

```text
Battle metadata
Initial teams
Regulation
Seed

Turn 1
  observation P1
  observation P2
  legal actions
  selected actions
  resolved events

Turn 2
  ...

Result
```

Logs should support:

- debugging;
- replay;
- training;
- evaluation;
- counterfactual analysis.

## 9. Things Agents Must Not Do

Do not:

- build a neural network before understanding the action space;
- replace tests with implementation-specific mocks just to make CI pass;
- remove failing mechanics tests without documenting why;
- use omniscient simulator state as player input;
- train/test on overlapping battle trajectories;
- claim an agent is better based on a few matches;
- optimize only against one opponent;
- hardcode current metagame assumptions into general domain objects;
- introduce live-client automation as a shortcut;
- generate large abstractions before they are needed;
- silently change evaluation pools between model comparisons;
- use an LLM explanation as evidence that an action is correct.

## 10. Living-Document Rule

Keep this file focused on **how agents should work in the repository**.

Project vision, roadmap, milestones, research directions, and product goals belong in `PROJECT_PLAN.md`.

When repository-wide agent behavior changes, update this file.
