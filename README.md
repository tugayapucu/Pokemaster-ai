# Pokemaster
A toolkit for building and benchmarking Pokemon battle AI agents.

## Data
Move data lives in `data/moves/genX-moves.json` for generations 1-9.
Type chart data lives in `data/typeChart/genX-typeChart.json` for generations
1-9.
Pokedex data lives in `data/pokedex/genX-pokedex.json` for generations 1-9.

Move JSON files are collected from Smogon move data (Pokemon Showdown) and
stored as snapshots to support offline experimentation. Each file is a JSON
object keyed by move id (lowercase, no spaces), where each value is a move
object with core fields like `name`, `type`, `category`, `basePower`,
`accuracy`, `pp`, `priority`, and `target`, plus optional fields for special
mechanics. See `data/moves/README.md` for details.

Type chart files mirror the Pokemon Showdown `TypeChart` format, with each
defending type keyed to a `damageTaken` map.

Pokedex files mirror Pokemon Showdown `Pokedex` data, keyed by species id
(lowercase, no spaces). Each entry includes fields such as `name`, `types`,
`baseStats`, `abilities`, `weightkg`, and `num`.
