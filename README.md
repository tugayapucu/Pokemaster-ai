# Pokémon Champions AI

Research platform for a Pokémon Champions battle recommendation system and,
longer-term, an autonomous battle agent. See [`PROJECT_PLAN.md`](PROJECT_PLAN.md)
for vision, milestones, and current decisions, and [`AGENTS.md`](AGENTS.md)
for repository-wide rules for coding agents working here.

## Prerequisites

- Python 3.11+
- **Node.js 22.18 or newer** — the battle simulator is [Pokémon Showdown](https://github.com/smogon/pokemon-showdown)'s
  `sim` engine, driven directly and headlessly (no server); see
  [`spike/showdown-bridge/notes.md`](spike/showdown-bridge/notes.md) for why.

## Setup

```bash
python -m pip install -e ".[dev]"
npm install
npm run build:sim        # required -- see below
```

`npm install` fetches Pokémon Showdown, whose battle engine is driven directly
(no server) by the bridge in [`src/champions_ai/simulator/`](src/champions_ai/simulator/).

**The build step is not optional.** Showdown is pinned to a specific upstream
commit rather than an npm release, because Regulation M-C reached the
repository on 2026-09-09 and the last npm publish was 2026-07-28 — and the
version bump that triggers a publish is a manual, unscheduled decision, so
there is no release to wait for. A package installed from git gets no `dist/`,
because upstream has no `prepare` script, and `require('pokemon-showdown')`
fails without it. `npm run build:sim` compiles it.

To move to a different upstream commit, change the pin in `package.json`,
reinstall, rebuild, and **delete `data/dex-*.json`** — the base `champions` mod
is whichever regulation is current, so the same filename can hold a different
game's roster. `tests/integration/test_regulation_mods.py` fails loudly if a
regulation's `mod` no longer matches what the engine reports.

## Tests and linting

```bash
python -m pytest
python -m ruff check .
```

Tests marked `integration` spawn a real Showdown process and are skipped
automatically when Node isn't installed:

```bash
python -m pytest -m "not integration"
```
