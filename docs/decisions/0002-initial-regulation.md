# ADR 0002: Target Gen 9 Champions VGC 2026 Regulation M-B first

## Date

2026-08-11

## Context

`PROJECT_PLAN.md` requires an initial supported regulation to be frozen
before Milestone 1 (battle representation, legal-action generation) can
be built — regulation determines the legal Pokémon pool, banlist, and
ruleset the domain model needs to respect.

Pokémon Champions organizes competitive play into rotating regulations,
the same way mainline VGC does. As of 2026-08-10/11, the current ranked
Double Battles format is publicly known as "Regulation M-B" — confirmed
via web search (Game8, Serebii, Pokémon.com, pokemon-zone.com) as running
from June 17 to late August/early September 2026.

Showdown's `champions` mod (see ADR 0001) has this exact format
implemented: `Dex.formats.get('[Gen 9 Champions] VGC 2026 Reg M-B')`
resolves to id `gen9championsvgc2026regmb`, `gameType: 'doubles'`,
ruleset `['Flat Rules', 'VGC Timer', 'Open Team Sheets']`.

## Decision

Target Gen 9 Champions **VGC 2026 Regulation M-B** (Double Battles,
format id `gen9championsvgc2026regmb`) as the first supported regulation.
The singles equivalent ("BSS Reg M-B") is not in scope, matching the
project's existing Doubles/VGC-first orientation
(`PROJECT_PLAN.md` section 2).

## Alternatives considered

- **Wait for a more stable/longer-lived regulation**: rejected. Every
  regulation eventually rotates; picking "the current one" and treating
  the regulation as configurable/versioned (already a stated principle in
  `AGENTS.md`) is more useful than waiting for a regulation that won't
  change.
- **Target the Bo3 variant** (`VGC 2026 Reg M-B (Bo3)`): deferred, not
  rejected outright. Best-of-3 adds team-sheet/game-state carryover
  complexity (`Force Open Team Sheets`, `Best of = 3`) that isn't needed
  to prove out the core battle/action representation. Can be added later
  without changing the core domain model.

## Consequences

- Regulation-specific facts discovered while validating this choice (a
  Stat Points system instead of EVs/IVs, a restricted held-item pool, no
  Terastallization under this ruleset despite Tera Type being a set
  field) are recorded in `PROJECT_PLAN.md` section 6 and must inform the
  domain model — they should not be assumed away as "the same as
  mainline VGC."
- When Regulation M-B rotates to the next regulation, this ADR's decision
  becomes historical context, not a currently-active constraint;
  `PROJECT_PLAN.md` section 10's "Initial regulation" row is the
  authoritative current value and should be updated at that time, not
  this file.
