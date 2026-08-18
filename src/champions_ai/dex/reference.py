"""Static reference data: what Pokemon and moves *are*, independent of any battle.

Distinct from `MoveData`, which the tracker builds per turn from the engine's
requests and which describes what may be chosen *right now*. This is the
unchanging half -- base stats, typing, move power -- loaded once and shared.

Sourced from Showdown's `champions` mod rather than a hand-maintained table, so
a regulation adding Pokemon or moves is picked up by refreshing the dump rather
than by editing data by hand (ADR 0001).
"""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

MoveCategory = Literal["Physical", "Special", "Status"]


def to_id(name: str) -> str:
    """Showdown's toID: lowercase, strip everything non-alphanumeric."""
    return "".join(character for character in name.lower() if character.isalnum())


class BaseStats(BaseModel, frozen=True):
    hp: int
    attack: int
    defense: int
    special_attack: int
    special_defense: int
    speed: int


class SpeciesInfo(BaseModel, frozen=True):
    species_id: str
    name: str
    types: tuple[str, ...]
    base_stats: BaseStats
    abilities: tuple[str, ...] = ()
    weight_kg: float = 0.0
    base_species: str = ""


class SecondaryEffect(BaseModel, frozen=True):
    """A move's rider: what it does beyond damage, and how often.

    `chance` is a percentage, and 100 means guaranteed rather than merely
    likely -- Nuzzle always paralyses, Fake Out always flinches. Treating a
    guaranteed rider as a coin flip is as wrong as ignoring it.
    """

    chance: int
    status: str | None = None
    volatile_status: str | None = None
    # Stat stages inflicted on the *target*.
    boosts: dict[str, int] = Field(default_factory=dict)
    # Stat stages applied to the *user* when the rider fires.
    self_boosts: dict[str, int] = Field(default_factory=dict)

    @property
    def is_guaranteed(self) -> bool:
        return self.chance >= 100


class MoveInfo(BaseModel, frozen=True):
    move_id: str
    name: str
    type: str
    category: MoveCategory
    base_power: int
    # None means the move bypasses accuracy checks entirely, which is not the
    # same as 100 -- Swift cannot be made to miss, a 100%-accurate move can.
    accuracy: int | None
    priority: int
    target: str
    # Whether this move drives the engine's shared "stall" counter, so a
    # consecutive use succeeds a third as often as the last. Note this is a
    # wider set than "blocks damage to the user": Endure shares the counter
    # while letting the hit land.
    stalling: bool = False
    # What the move does beyond damage. Empty means "no rider", which is not
    # the same as "unknown" -- the dump is exhaustive.
    secondaries: tuple[SecondaryEffect, ...] = ()
    # [numerator, denominator] fractions of damage dealt, or None.
    drain: tuple[int, int] | None = None
    recoil: tuple[int, int] | None = None
    # Unconditional self-boosts, as distinct from a secondary's: Close Combat
    # always drops its own defences rather than rolling for it.
    self_boosts: dict[str, int] = Field(default_factory=dict)
    flags: frozenset[str] = frozenset()

    @property
    def drain_fraction(self) -> float:
        """Share of damage dealt that heals the user."""
        return self.drain[0] / self.drain[1] if self.drain else 0.0

    @property
    def recoil_fraction(self) -> float:
        """Share of damage dealt that the user takes back."""
        return self.recoil[0] / self.recoil[1] if self.recoil else 0.0

    @property
    def flinch_chance(self) -> float:
        """Probability this move makes the target flinch, 0 to 1."""
        return max(
            (s.chance / 100 for s in self.secondaries if s.volatile_status == "flinch"),
            default=0.0,
        )

    def status_chance(self, status: str) -> float:
        return max(
            (s.chance / 100 for s in self.secondaries if s.status == status),
            default=0.0,
        )

    @property
    def guaranteed_status(self) -> str | None:
        """A status this move always inflicts -- Nuzzle's paralysis, not Scald's burn."""
        for secondary in self.secondaries:
            if secondary.is_guaranteed and secondary.status:
                return secondary.status
        return None

    @property
    def is_damaging(self) -> bool:
        return self.category != "Status" and self.base_power > 0

    @property
    def always_hits(self) -> bool:
        return self.accuracy is None

    @property
    def hit_chance(self) -> float:
        return 1.0 if self.accuracy is None else self.accuracy / 100


class TypeChart(BaseModel, frozen=True):
    """Resolved multipliers, keyed [attacking][defending].

    Stored as multipliers rather than Showdown's damageTaken codes because the
    engine already resolved them; re-deriving the semantics here would be a
    second implementation to keep in step.
    """

    multipliers: dict[str, dict[str, float]] = Field(default_factory=dict)

    def effectiveness(self, attacking_type: str, defending_types: tuple[str, ...]) -> float:
        """Combined multiplier against a (possibly dual-typed) defender."""
        row = self.multipliers.get(attacking_type)
        if row is None:
            raise KeyError(f"unknown attacking type {attacking_type!r}")
        total = 1.0
        for defending in defending_types:
            if defending not in row:
                raise KeyError(f"unknown defending type {defending!r}")
            total *= row[defending]
        return total


class Dex(BaseModel, frozen=True):
    """The reference tables a heuristic or evaluator needs."""

    species: dict[str, SpeciesInfo] = Field(default_factory=dict)
    moves: dict[str, MoveInfo] = Field(default_factory=dict)
    types: tuple[str, ...] = ()
    type_chart: TypeChart = TypeChart()

    def get_species(self, name: str) -> SpeciesInfo:
        """Look up by name or id. Raises rather than returning a default.

        A missing species would otherwise silently flatten every type
        calculation involving it, which is far harder to notice than a crash.
        """
        found = self.species.get(to_id(name))
        if found is None:
            raise KeyError(f"no species data for {name!r}")
        return found

    def get_move(self, name: str) -> MoveInfo:
        found = self.moves.get(to_id(name))
        if found is None:
            raise KeyError(f"no move data for {name!r}")
        return found

    def effectiveness(self, move: MoveInfo, defender: SpeciesInfo) -> float:
        return self.type_chart.effectiveness(move.type, defender.types)

    @classmethod
    def from_payload(cls, payload: dict) -> "Dex":
        """Build from the bridge's `dexdump` response."""
        species = {
            species_id: SpeciesInfo(
                species_id=species_id,
                name=entry["name"],
                types=tuple(entry["types"]),
                base_stats=BaseStats(
                    hp=entry["baseStats"]["hp"],
                    attack=entry["baseStats"]["atk"],
                    defense=entry["baseStats"]["def"],
                    special_attack=entry["baseStats"]["spa"],
                    special_defense=entry["baseStats"]["spd"],
                    speed=entry["baseStats"]["spe"],
                ),
                abilities=tuple(entry.get("abilities", ())),
                weight_kg=entry.get("weightkg", 0.0),
                base_species=entry.get("baseSpecies", entry["name"]),
            )
            for species_id, entry in payload["species"].items()
        }
        moves = {
            move_id: MoveInfo(
                move_id=move_id,
                name=entry["name"],
                type=entry["type"],
                category=entry["category"],
                base_power=entry["basePower"],
                accuracy=entry["accuracy"],
                priority=entry["priority"],
                target=entry["target"],
                stalling=bool(entry.get("stallingMove", False)),
                secondaries=tuple(
                    SecondaryEffect(
                        chance=secondary.get("chance", 100),
                        status=secondary.get("status") or None,
                        volatile_status=secondary.get("volatileStatus") or None,
                        boosts=dict(secondary.get("boosts") or {}),
                        self_boosts=dict(secondary.get("selfBoosts") or {}),
                    )
                    for secondary in entry.get("secondaries") or ()
                ),
                drain=tuple(entry["drain"]) if entry.get("drain") else None,
                recoil=tuple(entry["recoil"]) if entry.get("recoil") else None,
                self_boosts=dict(entry.get("selfBoosts") or {}),
                flags=frozenset(entry.get("flags", ())),
            )
            for move_id, entry in payload["moves"].items()
        }
        return cls(
            species=species,
            moves=moves,
            types=tuple(payload["types"]),
            type_chart=TypeChart(multipliers=payload["chart"]),
        )

    @classmethod
    def load(cls, bridge, *, mod: str = "champions") -> "Dex":
        """Pull fresh reference data from the simulator."""
        for event in bridge.request(cmd="dexdump", mod=mod):
            if event["type"] == "dex":
                return cls.from_payload(event)
            if event["type"] == "error":
                raise RuntimeError(f"dex dump failed: {event.get('message')}")
        raise RuntimeError("simulator returned no dex data")

    @classmethod
    def cached(cls, bridge, path: Path, *, mod: str = "champions") -> "Dex":
        """Load from `path`, dumping from the simulator first if it is missing.

        The cache is a convenience, not a source of truth: delete it after
        updating `pokemon-showdown` so a new regulation's roster is picked up.
        """
        if path.exists():
            return cls.model_validate_json(path.read_text(encoding="utf-8"))
        dex = cls.load(bridge, mod=mod)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dex.model_dump_json(), encoding="utf-8")
        return dex

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(), encoding="utf-8")


def load_payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
