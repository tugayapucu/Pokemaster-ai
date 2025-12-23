# Move data
Source: Smogon (Pokemon Showdown) move data, collected as JSON snapshots by
generation.

## Files
- `gen1-moves.json` through `gen9-moves.json`

## Format
- Top-level object keyed by move id (lowercase, no spaces).
- Each value is a move object with common fields like `name`, `type`,
  `category`, `basePower`, `accuracy`, `pp`, `priority`, `target`, and `num`.
- `flags` is an object mapping flag names to `1`.
- Optional fields cover special mechanics (`secondary`, `secondaries`,
  `status`, `boosts`, `drain`, `recoil`, `multihit`, and more).
- Some special behavior markers from upstream data are kept as strings
  (for example `onHit` or `onTry`).

## Notes
- Keys vary by generation; handle missing fields with defaults.
- `null` values appear in some optional fields (for example `secondary`).
- If you plan to redistribute this data, verify Smogon usage terms.
