"""A hand-described position, and the `Observation` it produces.

Two sides with very different amounts of information, which is the whole shape
of this module:

- **Ours** is a `Side` of real `BattlePokemon`, seeded from the engine so the
  stats, PP and Mega availability are the engine's own numbers rather than
  recomputed here (ADR 0003). Edits change only what a player watches change:
  HP, status, stat stages, who is out.
- **Theirs** is `ObservedPokemon`, the type that is structurally incapable of
  holding a secret. A player types what they can see and nothing else, so
  there is no field here for an opponent's stats or exact HP to be invented
  into.

Every edit returns a new `Position`. That is not ceremony: the command layer
above validates a typed line by *applying* it, and an edit that turns out to be
illegal has to leave the position it came from untouched.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from champions_ai.domain import (
    Boosts,
    Observation,
    ObservedPokemon,
    ObservedSide,
    Regulation,
    Side,
)
from champions_ai.domain.boosts import BOOST_FIELDS

US = "us"
THEM = "them"
SideName = Literal["us", "them"]

# Showdown's status ids. Listed so a typo becomes a refusal rather than a
# status nothing in the scorer has ever heard of, which would read as "no
# status" everywhere downstream and never be noticed.
STATUSES = ("brn", "par", "psn", "tox", "slp", "frz")


class Target(BaseModel, frozen=True):
    """One Pokemon, on one side. Indices are into `own.team` or `their_seen`."""

    side: SideName
    index: int


class Position(BaseModel, frozen=True):
    """What is on the screen, as far as the person typing can see it."""

    regulation: Regulation
    own: Side
    # The six species from Team Preview, as dex ids. Not part of the
    # `Observation` -- there is nowhere in it for "declared but not brought",
    # and inventing one would claim knowledge a player does not have. Kept
    # because it is what a typed name is checked against.
    their_team: tuple[str, ...] = ()
    # Only those actually seen on the field. Which four of the six were brought
    # is hidden information until they appear.
    their_seen: tuple[ObservedPokemon, ...] = ()
    their_active: tuple[int | None, ...] = (None, None)
    their_side_conditions: dict[str, int] = Field(default_factory=dict)
    their_mega_used: bool = False
    weather: str | None = None
    terrain: str | None = None
    field_conditions: dict[str, int] = Field(default_factory=dict)
    turn: int = 1

    @model_validator(mode="after")
    def _validate(self) -> "Position":
        self.check()
        return self

    def check(self) -> None:
        """Raise if this position could not exist in a battle.

        Called on construction *and* from `observation()`. Pydantic does not
        re-run validators on `model_copy`, which is what every edit here uses,
        so a validator alone would guard the first position built and nothing
        after it. Checking again on the way out means anything handed to the
        recommender has been checked however it was assembled.
        """
        slots = self.regulation.active_slots_per_side
        if len(self.their_active) != slots:
            raise ValueError(
                f"{self.regulation.game_type} has {slots} slots a side, "
                f"got {len(self.their_active)} for the opponent"
            )
        occupied = [i for i in self.their_active if i is not None]
        for index in occupied:
            if not 0 <= index < len(self.their_seen):
                raise ValueError(f"opponent slot {index} is not a Pokemon that has been seen")
        if len(set(occupied)) != len(occupied):
            raise ValueError("the same Pokemon cannot be in two opposing slots at once")
        if len(self.their_seen) > self.regulation.picked_team_size:
            raise ValueError(
                f"{len(self.their_seen)} opposing Pokemon seen, but only "
                f"{self.regulation.picked_team_size} are brought"
            )

    # -- reading -------------------------------------------------------------

    def observation(self) -> Observation:
        """The position as the rest of the project consumes it.

        `unrevealed_count` is what is *brought* and not yet seen, not what is
        declared and not yet seen. A player who has seen three of the four
        knows one is left, regardless of having watched all six at preview.
        """
        self.check()
        return Observation(
            regulation=self.regulation,
            turn=self.turn,
            player=0,
            own_side=self.own,
            opponent_side=ObservedSide(
                revealed=self.their_seen,
                active_slots=self.their_active,
                unrevealed_count=max(
                    0, self.regulation.picked_team_size - len(self.their_seen)
                ),
                side_conditions=dict(self.their_side_conditions),
                mega_used=self.their_mega_used,
            ),
            weather=self.weather,
            terrain=self.terrain,
            field_conditions=dict(self.field_conditions),
        )

    def species_at(self, target: Target) -> str:
        if target.side == US:
            return self.own.team[target.index].pokemon_set.species
        return self.their_seen[target.index].species

    def is_active(self, target: Target) -> bool:
        if target.side == US:
            return target.index in self.own.active_slots
        return target.index in self.their_active

    def seen_index(self, species: str) -> int | None:
        """Where a species sits in `their_seen`, if it has been out at all."""
        for index, mon in enumerate(self.their_seen):
            if mon.species == species:
                return index
        return None

    # -- editing -------------------------------------------------------------

    def _with_own(self, index: int, **changes) -> "Position":
        mon = self.own.team[index]
        return self.model_copy(
            update={"own": self.own.with_pokemon_at(index, mon.model_copy(update=changes))}
        )

    def _with_theirs(self, index: int, **changes) -> "Position":
        updated = list(self.their_seen)
        updated[index] = updated[index].model_copy(update=changes)
        return self.model_copy(update={"their_seen": tuple(updated)})

    def with_hp(self, target: Target, percent: int) -> "Position":
        """Set a Pokemon's remaining HP, as the percentage the bar shows.

        Champions shows the opponent's HP as a floored percentage, so that is
        the only figure available for them. Ours is stored as real HP against a
        real maximum, and 1 is the floor while alive -- rounding a survivor
        down to 0 would tell the scorer it had fainted.
        """
        if not 0 <= percent <= 100:
            raise ValueError(f"HP is a percentage from 0 to 100, got {percent}")
        if target.side == THEM:
            return self._with_theirs(target.index, hp_percent=percent, fainted=percent == 0)
        maximum = self.own.team[target.index].max_hp
        current = 0 if percent == 0 else min(maximum, max(1, round(maximum * percent / 100)))
        return self._with_own(target.index, current_hp=current)

    def with_fainted(self, target: Target) -> "Position":
        """Mark a Pokemon as knocked out, and take it off the field."""
        position = self.with_hp(target, 0)
        if target.side == THEM:
            position = position._with_theirs(target.index, fainted=True)
            active = tuple(
                None if i == target.index else i for i in position.their_active
            )
            return position.model_copy(update={"their_active": active})
        side = position.own
        for slot, index in enumerate(side.active_slots):
            if index == target.index:
                side = side.with_slot(slot, None)
        return position.model_copy(update={"own": side})

    def with_boost(self, target: Target, stat: str, stage: int) -> "Position":
        """Set a stat stage to what the arrows on screen show.

        Set rather than add, deliberately. A player reads a total off the
        screen; typing the total is idempotent, so correcting a mistake means
        typing the right number rather than working out a correction to a
        number they cannot see.
        """
        field = BOOST_FIELDS.get(stat)
        if field is None:
            raise ValueError(f"{stat} is not a stat with stages: {', '.join(BOOST_FIELDS)}")
        if not -6 <= stage <= 6:
            raise ValueError(f"stat stages run from -6 to +6, got {stage}")
        current = (
            self.own.team[target.index].boosts
            if target.side == US
            else self.their_seen[target.index].boosts
        )
        boosts = current.model_copy(update={field: stage})
        if target.side == US:
            return self._with_own(target.index, boosts=boosts)
        return self._with_theirs(target.index, boosts=boosts)

    def with_status(self, target: Target, status: str | None) -> "Position":
        if status is not None and status not in STATUSES:
            raise ValueError(f"{status} is not a status: {', '.join(STATUSES)}")
        if target.side == US:
            return self._with_own(target.index, status=status)
        return self._with_theirs(target.index, status=status)

    def with_revealed_move(self, target: Target, move: str) -> "Position":
        """Record a move we have watched an opposing Pokemon use.

        Only meaningful for them -- we know our own moveset from the team
        sheet, and `revealed_moves` on our side is what *they* have seen.
        """
        if target.side == US:
            raise ValueError("our own moves come from the team sheet, not from watching")
        mon = self.their_seen[target.index]
        return self._with_theirs(
            target.index, revealed_moves=mon.revealed_moves | {move}, last_move=move
        )

    def with_their_item(self, target: Target, item: str | None) -> "Position":
        """An opposing item, once something has shown what it is.

        `None` means we watched one leave: that is `item_consumed`, which is a
        stronger statement than "we have not seen one" and is treated as such
        by the scorer.
        """
        if target.side == US:
            raise ValueError("our own items come from the team sheet")
        if item is None:
            return self._with_theirs(target.index, revealed_item=None, item_consumed=True)
        return self._with_theirs(target.index, revealed_item=item, item_consumed=False)

    def with_their_ability(self, target: Target, ability: str) -> "Position":
        if target.side == US:
            raise ValueError("our own abilities come from the team sheet")
        return self._with_theirs(target.index, revealed_ability=ability)

    def with_them_out(self, slot: int, species: str) -> "Position":
        """Put an opposing species into a field slot.

        A species seen for the first time joins `their_seen` here, which is the
        moment it stops being one of the unrevealed count. It must be one of
        the six declared at Team Preview: at a tournament the likeliest reason
        it is not is a typo, and accepting it would put a Pokemon that is not
        in the game onto the board.
        """
        if self.their_team and species not in self.their_team:
            raise ValueError(f"{species} is not one of the six they showed at Team Preview")
        index = self.seen_index(species)
        position = self
        if index is None:
            if len(self.their_seen) >= self.regulation.picked_team_size:
                raise ValueError(
                    f"that would be {len(self.their_seen) + 1} opposing Pokemon, "
                    f"and only {self.regulation.picked_team_size} are brought"
                )
            index = len(self.their_seen)
            position = self.model_copy(
                update={
                    "their_seen": (
                        *self.their_seen,
                        ObservedPokemon(
                            species=species, level=self.regulation.level, hp_percent=100,
                            fainted=False,
                        ),
                    )
                }
            )
        if position.their_seen[index].fainted:
            raise ValueError(f"{species} has fainted and cannot come back out")
        # Whatever was in this slot leaves, and a Pokemon that leaves the field
        # drops its stat stages. Missing that is a bug this project has already
        # had once, in the tracker, where benched Pokemon kept stale stages.
        active = list(position.their_active)
        if index in active:
            active[active.index(index)] = None
        leaving = active[slot]
        active[slot] = index
        position = position.model_copy(update={"their_active": tuple(active)})
        if leaving is not None and leaving != index:
            position = position._with_theirs(
                leaving, boosts=Boosts(), volatile_conditions=frozenset(), protect_streak=0
            )
        return position

    def with_us_out(self, slot: int, index: int) -> "Position":
        """Put one of ours into a field slot, dropping the leaver's stages."""
        if not 0 <= index < len(self.own.team):
            raise ValueError(f"we brought {len(self.own.team)} Pokemon; {index + 1} is not one")
        if self.own.team[index].fainted:
            raise ValueError(
                f"{self.own.team[index].pokemon_set.species} has fainted and cannot come back out"
            )
        side = self.own
        if index in side.active_slots:
            side = side.with_slot(side.active_slots.index(index), None)
        leaving = side.active_slots[slot]
        side = side.with_slot(slot, index)
        position = self.model_copy(update={"own": side})
        if leaving is not None and leaving != index:
            position = position._with_own(
                leaving, boosts=Boosts(), volatile_conditions=frozenset(), protect_streak=0
            )
        return position

    def with_field(self, *, weather: str | None = ..., terrain: str | None = ...) -> "Position":
        """Set weather or terrain. `None` clears one; omitting it leaves it alone.

        The two are separate fields in a battle -- sun and Grassy Terrain are
        both up at once often enough -- so setting one must not clear the
        other, and `...` is what tells them apart from an explicit `None`.
        """
        changes = {}
        if weather is not ...:
            changes["weather"] = weather
        if terrain is not ...:
            changes["terrain"] = terrain
        return self.model_copy(update=changes)

    def with_side_condition(self, side: SideName, condition: str, turns: int) -> "Position":
        """Tailwind, Reflect, a screen. `turns` of 0 removes it."""
        current = dict(self.own.side_conditions if side == US else self.their_side_conditions)
        if turns <= 0:
            current.pop(condition, None)
        else:
            current[condition] = turns
        if side == THEM:
            return self.model_copy(update={"their_side_conditions": current})
        own = self.own.model_copy(update={"side_conditions": current})
        return self.model_copy(update={"own": own})

    def with_mega_used(self, side: SideName) -> "Position":
        """Record that a side has spent its one Mega Evolution.

        Ours also has to stop being *offered*: `available_specials` is what the
        legal-action generator reads, and a Mega left in it after the fact
        would be recommended a second time.
        """
        if side == THEM:
            return self.model_copy(update={"their_mega_used": True})
        team = tuple(
            mon.model_copy(update={"available_specials": frozenset()}) for mon in self.own.team
        )
        return self.model_copy(
            update={"own": self.own.model_copy(update={"team": team, "mega_used": True})}
        )

    def with_turn(self, turn: int) -> "Position":
        if turn < 1:
            raise ValueError(f"turns start at 1, got {turn}")
        return self.model_copy(update={"turn": turn})
