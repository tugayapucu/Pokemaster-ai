# ADR 0003: Take choice availability from the simulator, don't recompute it

## Date

2026-08-11

## Context

Milestone 1's legal-action generator (`domain/legal_actions.py`) ships with
four known gaps, all of the same shape — each needs a rule the domain layer
cannot currently evaluate:

- **Mega Evolution is never offered**, because knowing whether a Pokémon can
  Mega requires matching its species against its held item's `megaStone` map.
- **Move-lock effects** (Choice items, Encore, Taunt, Disable, Torment) are
  not applied.
- **Struggle** is not modelled.
- **Trapping** is read from a `"trapped"` volatile condition set by convention.

The obvious fix is to load species/item/ability data from the `champions` mod
and reimplement each rule in Python. Reading the simulator's source shows that
would be redundant work. `getMoveRequestData()` in `sim/pokemon.ts` builds the
payload the engine sends each player every turn, and it already carries the
answers, per active Pokémon:

```js
if (this.canMegaEvo) data.canMegaEvo = true;
```

alongside per-move `disabled` flags (set in `sim/side.ts`), `trapped`,
`maybeTrapped`, and `lockedMove`. Showdown's own example bot
(`sim/tools/random-player-ai.ts`) drives its entire action choice from exactly
this payload rather than deriving legality itself.

## Decision

Treat the simulator's per-turn request payload as the authority on which
choices are available. The environment adapter parses it into the domain
layer; the legal-action generator consumes those reported flags rather than
recomputing legality from game data.

Concretely, this means the adapter is responsible for populating what the
generator reads — including setting the `"trapped"` volatile the generator
already expects — and for carrying per-slot availability (Mega, disabled
moves) into the domain types.

## Alternatives considered

- **Reimplement legality in Python from `champions` mod data**: rejected. It
  duplicates tested engine logic, must track every regulation change, and
  fails in the worst direction — a wrong `canMegaEvo` produces an *illegal*
  action that corrupts a battle mid-run, rather than merely omitting an option.
  This is the same reasoning as ADR 0001.
- **Leave the gaps open**: rejected. Mega is central to Regulation M-B; an
  action space that structurally cannot express it would cap agent strength
  for reasons unrelated to decision quality, and would quietly invalidate any
  evaluation run against real play.

## Consequences

- The gaps close together, at the environment adapter, rather than as four
  separate pieces of rules work. No species/item/ability data loading is
  required for legal-action generation.
- `MoveData` injection stays as-is: move *target type* is static metadata that
  doesn't vary by battle state, so it's correctly loaded from data rather than
  requested per turn.
- `Side.mega_used` remains meaningful, but as *observed information* (has the
  opponent spent their Mega?) rather than as a legality check for one's own
  actions — the engine answers the latter directly.
- **Open tension, deliberately unresolved:** a generator that depends on
  engine-reported availability cannot enumerate actions for a *hypothetical*
  state the engine has not been asked about, which search (Milestone 11) will
  eventually need. This is entangled with the existing open question of whether
  search runs inside the full simulator or against a faster approximate model
  (`PROJECT_PLAN.md` section 15), and is better decided then, with the
  performance data that question needs, than guessed at now.
