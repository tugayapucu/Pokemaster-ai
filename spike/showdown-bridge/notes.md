# Spike: Showdown sim bridge (2026-08-11)

## Question

Can we drive Pokémon Showdown's `sim` engine directly and headlessly (no
server, no `poke-env`) for a Gen 9 Champions VGC 2026 Regulation M-B doubles
battle, and read the result from Python?

## Result

Yes. See `run-battle.js` (Node, drives `BattleStream` via
`getPlayerStreams` + two `RandomPlayerAI` instances) and `bridge.py`
(Python, spawns it as a subprocess and parses the protocol lines from
stdout). A full battle — team preview, Open Team Sheets, Intimidate,
switches, faints, a winner — runs end to end and is readable from Python
with no server or WebSocket layer involved.

## Format

`npm install pokemon-showdown` (v0.11.11) ships a dedicated `Champions`
section in `config/formats.ts` — this is not an approximation using
mainline mods, Showdown genuinely models Pokémon Champions as its own thing.

Confirmed format id for our target: `gen9championsvgc2026regmb`
(`Dex.formats.get('[Gen 9 Champions] VGC 2026 Reg M-B')`), `gameType:
'doubles'`, ruleset `['Flat Rules', 'VGC Timer', 'Open Team Sheets']`. A
Bo3 variant and a singles ("BSS") equivalent also exist but aren't in
scope.

## Mechanics differences from mainline VGC (important for the domain model)

These surprised me and change assumptions in `PROJECT_PLAN.md` section 6:

- **No classic EV/IV system.** Instead of 0–252 EVs per stat (510 total)
  and 0–31 IVs, Champions uses a **"Stat Points" system**: 0–32 points per
  stat, **66 total across all stats**, and IVs are fixed at 31 (not
  customizable) unless `Level Clause Mod` is active, which Reg M-B doesn't
  use. Implemented in `data/mods/champions/scripts.ts` `statModify()`.
  This is a much simpler, more bounded space than mainline — worth
  designing the domain model's stat-allocation representation around
  directly rather than reusing a mainline EV/IV shape.
- **Smaller, curated item pool.** Many mainline staples are unavailable
  (`isNonstandard: "Past"` in `data/mods/champions/items.ts`) — notably
  **Choice Band, Choice Specs, Assault Vest, Rocky Helmet, Air Balloon are
  all absent**. Confirmed-legal held items (73 total, non-mega/non-ball):
  see the list generated in this spike session, includes Leftovers, Sitrus
  Berry, Life Orb, Choice Scarf, Focus Sash, etc. Mega stones are present
  and standard (`isNonstandard: null`) — Champions keeps Mega Evolution
  as a core mechanic, unlike mainline Gen 9.
  Do not assume the mainline item pool when building `Item` domain data —
  query the `champions` mod's Dex, not a generic Gen 9 dex.
- **Team building is bring-6/pick-4-for-doubles** via `Picked Team Size =
  Auto` + `Min Team Size = 6` (from the `Flat Rules` base ruleset) — Team
  Preview shows all 6, `teamsize` events confirm 4 are actually brought
  into the doubles battle.
- Regulation M-B has no `Terastallize` available in this ruleset
  (`actions.canTerastallize` returns `null` in `scripts.ts`) despite the
  format listing a Tera Type on sets — worth double-checking before
  assuming Tera is part of the current regulation's action space.

## Caveats / not yet verified

- Teams were generated via Showdown's Champions **random-battle** team
  generator (`gen9championsrandombattle`), retried until they passed
  `TeamValidator` for `gen9championsvgc2026regmb` (needed up to ~100+
  retries in one run — the random generator isn't Reg M-B-aware and
  frequently trips Item Clause or event-Pokémon legality). This is fine
  for a bridge spike but is not how real team construction should work
  long-term.
- Two `RandomPlayerAI` bots played the battle, not scripted/deterministic
  actions — good enough to prove the protocol round-trips, not a
  correctness test of any specific mechanic.
- Whether Showdown's Reg M-B implementation matches the *live* Champions
  client hasn't been checked against real gameplay — this spike only
  confirms Showdown's own modeling is internally consistent and running.
  This is the follow-up open question already recorded in
  `PROJECT_PLAN.md` section 15.

## Environment setup required

Neither Node.js nor Python were installed on this machine before this
spike; both were installed via `winget` (`OpenJS.NodeJS.LTS`,
`Python.Python.3.12`) to make the bridge runnable at all. Milestone 0
should record this as a real prerequisite, not assume either is present.
