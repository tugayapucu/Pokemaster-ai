# Pokémon Champions AI

Research platform for a Pokémon Champions battle recommendation system and,
longer-term, an autonomous battle agent. See [`PROJECT_PLAN.md`](PROJECT_PLAN.md)
for vision, milestones, and current decisions, and [`AGENTS.md`](AGENTS.md)
for repository-wide rules for coding agents working here.

## Prerequisites

- Python 3.11+
- Node.js (LTS) — the battle simulator is [Pokémon Showdown](https://github.com/smogon/pokemon-showdown)'s
  `sim` engine, driven directly and headlessly (no server); see
  [`spike/showdown-bridge/notes.md`](spike/showdown-bridge/notes.md) for why.

## Setup

```bash
python -m pip install -e ".[dev]"
```

## Tests and linting

```bash
python -m pytest
python -m ruff check .
```
