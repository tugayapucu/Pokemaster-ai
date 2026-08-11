# ADR 0001: Drive Pokémon Showdown's sim engine directly, not poke-env

## Date

2026-08-11

## Context

Pokémon Champions has no public simulator or datamined mechanics reference
of its own. Building a battle engine from scratch would mean re-implementing
hundreds of moves, abilities, and interactions — exactly the kind of
correctness-critical work this project's own principles say not to
duplicate if a tested implementation already exists.

Pokémon Showdown (`pokemon-showdown` on npm, Node/TypeScript) ships a
dedicated `champions` mod with real Champions formats, including our
target regulation. This makes Showdown's simulator the natural mechanics
source of truth. The open question was *how* to integrate it, since it's
a Node codebase and this project's ML/RL stack is Python (see
`PROJECT_PLAN.md` section 4).

Two integration paths existed:

1. **poke-env** — a Python client library that connects to a *running*
   Showdown server over the real WebSocket client-server protocol (the
   same protocol a human browser client uses: login, matchmaking-style
   room join, etc.), and parses the wire format into its own Python
   `Battle` object model.
2. **Drive `sim`'s `BattleStream` directly** — Showdown's core battle
   engine can run headlessly, in-process, with no server, accounts, or
   matchmaking layer at all, via `BattleStream`/`getPlayerStreams`. A thin
   bridge we own (subprocess + line protocol) would connect this to
   Python.

## Decision

Drive Showdown's `sim` engine directly via `BattleStream`, bridged to
Python over a subprocess/stdio protocol we own. Do not add `poke-env` or
any Showdown *server* as a dependency.

## Alternatives considered

- **poke-env**: rejected. It's built for bots that behave like human
  clients connecting to a live server — real-time WebSocket protocol,
  login, matchmaking. None of that is needed for local battles or
  self-play, and it's pure overhead (a server process, network I/O per
  battle) for what should eventually be a high-throughput RL training
  loop. It also imposes its own `Battle`/`Pokemon` object model, where
  this project wants its own `BattleState`/`Observation`/`Action` types
  (`PROJECT_PLAN.md` section 6) shaped around our own hidden-information
  and evaluation needs.
- **Build a battle engine from scratch in Python**: rejected for now.
  More upfront work, more surface area for subtle mechanics bugs, and
  duplicates a well-tested implementation that already models Champions'
  formats directly. Could be revisited if Showdown's implementation is
  found to diverge materially from the live Champions client.

## Consequences

- The project depends on Node.js as a runtime, in addition to Python.
  Documented in `README.md` as a prerequisite.
- We own the Python↔Node bridge protocol (currently a subprocess reading
  Showdown's line-based protocol from stdout). This is more code than
  poke-env would have required, but keeps the dependency surface small
  and the data flowing straight into our own domain types.
- Validated in `spike/showdown-bridge/`: a full Gen 9 Champions VGC 2026
  Reg M-B doubles battle runs end to end and is readable from Python with
  no server involved (see `spike/showdown-bridge/notes.md`).
- Not yet verified: whether Showdown's Reg M-B implementation matches the
  *live* Champions client in every mechanical detail. Tracked as an open
  question in `PROJECT_PLAN.md` section 15.
