"""Turn bridge events into domain objects.

Two sources, deliberately kept apart:

- **request payloads** describe our own side completely (exact HP, PP, item,
  ability) -- a player genuinely knows all of this about their own team;
- **sideline events** are the player-visible protocol stream, where opponent
  HP is already a percentage. Omniscient `line` events are never consumed here
  (see AGENTS.md).

The tracker accumulates, because knowledge does: an opponent's move stays known
once used, and a Pokemon they never send out stays unknown all battle.
"""

import re

from champions_ai.domain import (
    BattlePokemon,
    Boosts,
    MoveData,
    Observation,
    ObservedPokemon,
    ObservedSide,
    PokemonSet,
    Regulation,
    RevealedPokemon,
    Side,
    StatSpread,
    Team,
    TeamPreview,
)
from champions_ai.domain.health import parse_exact_health, parse_shared_health
from champions_ai.domain.legal_actions import TRAPPED

# Showdown stat keys -> our Boosts fields.
BOOST_FIELDS = {
    "atk": "attack",
    "def": "defense",
    "spa": "special_attack",
    "spd": "special_defense",
    "spe": "speed",
    "accuracy": "accuracy",
    "evasion": "evasion",
}

SLOT_LETTERS = "abcdef"

# Engine request flags -> our SpecialMechanic names (ADR 0003). Reg M-B only
# raises canMegaEvo, but the rest are here so a regulation enabling them needs
# no code change.
ENGINE_SPECIAL_FLAGS = {
    "canMegaEvo": "mega",
    "canTerastallize": "terastallize",
    "canDynamax": "dynamax",
    "canUltraBurst": "ultraburst",
}


def to_id(name: str) -> str:
    """Showdown's toID: lowercase, strip everything non-alphanumeric."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _split_ident(ident: str) -> tuple[str, int | None, str]:
    """`p2a: Chomper` -> ("p2", 0, "Chomper"). Slot is None for sideless idents."""
    position, _, name = ident.partition(": ")
    side = position[:2]
    slot = SLOT_LETTERS.index(position[2]) if len(position) > 2 else None
    return side, slot, name


def _species_from_details(details: str) -> str:
    """`Charizard-Mega-Y, L50, F` -> `Charizard-Mega-Y`."""
    return details.split(",")[0].strip()


class _OpponentPokemon:
    """Mutable accumulator; converted to the immutable ObservedPokemon on demand."""

    def __init__(self, species: str, level: int) -> None:
        self.species = species
        self.level = level
        self.hp_percent = 100
        self.fainted = False
        self.status: str | None = None
        self.boosts = Boosts()
        self.volatiles: set[str] = set()
        self.revealed_moves: set[str] = set()
        self.revealed_item: str | None = None
        self.revealed_ability: str | None = None

    def snapshot(self) -> ObservedPokemon:
        return ObservedPokemon(
            species=self.species,
            level=self.level,
            hp_percent=self.hp_percent,
            fainted=self.fainted,
            status=self.status,
            boosts=self.boosts,
            volatile_conditions=frozenset(self.volatiles),
            revealed_moves=frozenset(self.revealed_moves),
            revealed_ability=self.revealed_ability,
            revealed_item=self.revealed_item,
        )


class BattleTracker:
    """Accumulates one player's view of a battle and renders it as an Observation."""

    def __init__(self, regulation: Regulation, player: int, own_team: Team) -> None:
        if player not in (0, 1):
            raise ValueError(f"player must be 0 or 1, got {player}")
        self.regulation = regulation
        self.player = player
        self.own_tag = f"p{player + 1}"
        self.opponent_tag = f"p{2 - player}"

        self._sets_by_species = {to_id(mon.species): mon for mon in own_team.pokemon}
        self._request: dict | None = None
        # A fainted Pokemon reports "0 fnt" with no maximum, so remember it.
        self._own_max_hp: dict[str, int] = {}
        self._move_data: dict[str, MoveData] = {}
        self._turn = 0
        self._winner: str | None = None

        self._opponents: dict[str, _OpponentPokemon] = {}
        self._opponent_order: list[str] = []
        self._opponent_slots: list[str | None] = [None] * regulation.active_slots_per_side
        self._opponent_team_size = regulation.picked_team_size
        self._opponent_side_conditions: dict[str, int] = {}
        self._nickname_to_species: dict[str, str] = {}
        self._opponent_mega_used = False
        self._opponent_roster: list[RevealedPokemon] = []
        self._own_team = own_team

        self.weather: str | None = None
        self.terrain: str | None = None
        self.field_conditions: dict[str, int] = {}

    # ---------------------------------------------------------------- events

    def handle(self, event: dict) -> None:
        kind = event.get("type")
        if kind == "request" and event.get("player") == self.own_tag:
            self._request = event["request"]
            self._learn_move_data(event["request"])
            self._learn_max_hp(event["request"])
        elif kind == "sideline" and event.get("player") == self.own_tag:
            self._handle_line(event["line"])

    def _learn_move_data(self, request: dict) -> None:
        """Move target types come from the engine, not a data file.

        Requests carry `target` per move for whatever is active, so the move
        metadata legal-action generation needs arrives for free. Accumulated
        because switch requests carry no `active` block at all.
        """
        for active in request.get("active") or []:
            for entry in active.get("moves") or []:
                if "id" in entry and "target" in entry:
                    self._move_data[entry["id"]] = MoveData(
                        move_id=entry["id"], target=entry["target"]
                    )

    def _learn_max_hp(self, request: dict) -> None:
        """Record maximum HP while it is still visible.

        A fainted Pokemon's condition is `0 fnt` with no maximum, so this has
        to be captured as requests arrive rather than when a side is rendered.
        """
        for entry in request.get("side", {}).get("pokemon", []):
            health = parse_exact_health(entry["condition"])
            if not health.fainted:
                self._own_max_hp[entry["ident"]] = health.maximum

    def handle_all(self, events: list[dict]) -> None:
        for event in events:
            self.handle(event)

    def _handle_line(self, line: str) -> None:
        parts = line.split("|")
        if len(parts) < 2:
            return
        handler = getattr(self, f"_on_{parts[1].lstrip('-').replace(':', '')}", None)
        if handler is not None:
            handler(parts[2:])

    # --------------------------------------------------------- line handlers

    def _on_turn(self, args: list[str]) -> None:
        self._turn = int(args[0])

    def _on_win(self, args: list[str]) -> None:
        self._winner = args[0]

    def _on_teamsize(self, args: list[str]) -> None:
        if args[0] == self.opponent_tag:
            self._opponent_team_size = int(args[1])

    def _on_poke(self, args: list[str]) -> None:
        """Team Preview roster line: `|poke|p2|Charizard, L50, M|`.

        Only species and level are listed unless Open Team Sheets was accepted
        (see ADR 0002), which is what `RevealedPokemon` is shaped for.
        """
        if args[0] != self.opponent_tag:
            return
        details = args[1]
        self._opponent_roster.append(
            RevealedPokemon(
                species=_species_from_details(details),
                level=int(details.split("L")[1].split(",")[0]) if ", L" in details else 50,
            )
        )

    def _on_clearpoke(self, args: list[str]) -> None:
        self._opponent_roster.clear()

    def _opponent_at(self, ident: str) -> _OpponentPokemon | None:
        side, _, name = _split_ident(ident)
        if side != self.opponent_tag:
            return None
        species = self._nickname_to_species.get(name)
        return self._opponents.get(species) if species else None

    def _on_switch(self, args: list[str]) -> None:
        ident, details, condition = args[0], args[1], args[2]
        side, slot, name = _split_ident(ident)
        if side != self.opponent_tag:
            return

        species = _species_from_details(details)
        # Nicknames make ident unreliable on its own, so learn the mapping from
        # the details field the first time a Pokemon appears.
        known = self._nickname_to_species.get(name)
        if known is None:
            self._nickname_to_species[name] = species
            known = species
        if known not in self._opponents:
            level = int(details.split("L")[1].split(",")[0]) if ", L" in details else 50
            self._opponents[known] = _OpponentPokemon(known, level)
            self._opponent_order.append(known)

        mon = self._opponents[known]
        # A Pokemon switching in loses its boosts and volatiles.
        mon.boosts = Boosts()
        mon.volatiles.clear()
        self._apply_condition(mon, condition)
        if slot is not None:
            self._clear_slot(known)
            self._opponent_slots[slot] = known

    _on_drag = _on_switch
    _on_replace = _on_switch

    def _clear_slot(self, species: str) -> None:
        for index, occupant in enumerate(self._opponent_slots):
            if occupant == species:
                self._opponent_slots[index] = None

    def _apply_condition(self, mon: _OpponentPokemon, condition: str) -> None:
        health = parse_shared_health(condition)
        mon.hp_percent = health.percent
        mon.fainted = health.fainted
        mon.status = health.status if health.status != "fnt" else None

    def _on_damage(self, args: list[str]) -> None:
        mon = self._opponent_at(args[0])
        if mon:
            self._apply_condition(mon, args[1])

    _on_heal = _on_damage
    _on_sethp = _on_damage

    def _on_faint(self, args: list[str]) -> None:
        mon = self._opponent_at(args[0])
        if mon:
            mon.fainted = True
            mon.hp_percent = 0
            self._clear_slot(mon.species)

    def _on_mega(self, args: list[str]) -> None:
        _, _, name = _split_ident(args[0])
        if self._nickname_to_species.get(name) in self._opponents:
            self._opponent_mega_used = True

    def _on_status(self, args: list[str]) -> None:
        mon = self._opponent_at(args[0])
        if mon:
            mon.status = args[1]

    def _on_curestatus(self, args: list[str]) -> None:
        mon = self._opponent_at(args[0])
        if mon:
            mon.status = None

    def _on_boost(self, args: list[str]) -> None:
        self._change_boost(args, sign=1)

    def _on_unboost(self, args: list[str]) -> None:
        self._change_boost(args, sign=-1)

    def _change_boost(self, args: list[str], sign: int) -> None:
        mon = self._opponent_at(args[0])
        field = BOOST_FIELDS.get(args[1])
        if mon and field:
            mon.boosts = mon.boosts.clamped_add(field, sign * int(args[2]))

    def _on_move(self, args: list[str]) -> None:
        mon = self._opponent_at(args[0])
        if mon:
            mon.revealed_moves.add(to_id(args[1]))

    def _on_item(self, args: list[str]) -> None:
        mon = self._opponent_at(args[0])
        if mon:
            mon.revealed_item = to_id(args[1])

    def _on_enditem(self, args: list[str]) -> None:
        mon = self._opponent_at(args[0])
        if mon:
            # Consumed or knocked off: now known to be holding nothing.
            mon.revealed_item = None

    def _on_ability(self, args: list[str]) -> None:
        mon = self._opponent_at(args[0])
        if mon:
            mon.revealed_ability = to_id(args[1])

    def _on_weather(self, args: list[str]) -> None:
        self.weather = None if args[0] == "none" else to_id(args[0])

    def _on_fieldstart(self, args: list[str]) -> None:
        self.field_conditions[to_id(args[0].split(": ")[-1])] = 0

    def _on_fieldend(self, args: list[str]) -> None:
        self.field_conditions.pop(to_id(args[0].split(": ")[-1]), None)

    def _on_sidestart(self, args: list[str]) -> None:
        if args[0].split(":")[0] == self.opponent_tag:
            self._opponent_side_conditions[to_id(args[1].split(": ")[-1])] = 0

    def _on_sideend(self, args: list[str]) -> None:
        if args[0].split(":")[0] == self.opponent_tag:
            self._opponent_side_conditions.pop(to_id(args[1].split(": ")[-1]), None)

    # ---------------------------------------------------------------- output

    @property
    def has_request(self) -> bool:
        """Whether the engine has asked this player for anything at all yet."""
        return self._request is not None

    @property
    def awaiting_team_preview(self) -> bool:
        return bool(self._request and self._request.get("teamPreview"))

    @property
    def force_switch_slots(self) -> tuple[bool, ...]:
        """Per-slot: must this slot switch right now? Empty when it's a normal turn.

        Comes from the engine's request rather than being inferred from fainted
        Pokemon (ADR 0003) -- moves like Roar and Eject Button force switches
        without a faint.
        """
        if not self._request:
            return ()
        return tuple(self._request.get("forceSwitch") or ())

    @property
    def waiting(self) -> bool:
        """True when the engine wants nothing from us this step."""
        return bool(self._request and self._request.get("wait"))

    @property
    def move_data(self) -> dict[str, MoveData]:
        """Target types for every move seen active so far, for legal-action generation."""
        return dict(self._move_data)

    @property
    def winner(self) -> str | None:
        return self._winner

    @property
    def finished(self) -> bool:
        return self._winner is not None

    def own_side(self) -> Side:
        """Our own team, from the latest request payload."""
        if self._request is None:
            raise RuntimeError("no request seen yet; cannot describe our own side")

        entries = self._request["side"]["pokemon"]
        active_entries = self._request.get("active") or []

        team: list[BattlePokemon] = []
        active_slots: list[int | None] = []
        for index, entry in enumerate(entries):
            species = _species_from_details(entry["details"])
            # The request is authoritative for live identity: its move list is
            # already in Showdown id form, matching the move_data keys. The
            # supplied team only contributes what the request omits -- the Stat
            # Points allocation, which is never sent back to the player.
            declared = self._sets_by_species.get(to_id(species))
            pokemon_set = PokemonSet(
                species=species,
                level=int(entry["details"].split("L")[1].split(",")[0]),
                ability=to_id(entry.get("baseAbility") or ""),
                moves=tuple(entry["moves"]),
                item=to_id(entry["item"]) if entry.get("item") else None,
                stats=declared.stats if declared else StatSpread(),
                nature=declared.nature if declared else None,
                tera_type=declared.tera_type if declared else None,
            )

            health = parse_exact_health(entry["condition"])
            max_hp = self._own_max_hp.get(entry["ident"], health.maximum)

            slot = len(active_slots) if entry.get("active") else None
            pp = None
            choosable: tuple[str, ...] | None = None
            choosable_targets: tuple[str | None, ...] | None = None
            disabled: frozenset[str] = frozenset()
            specials: frozenset[str] = frozenset()
            volatiles: frozenset[str] = frozenset()
            if slot is not None and slot < len(active_entries):
                active = active_entries[slot]
                moves = active.get("moves") or []
                # The engine's list, not the declared moveset: a Pokemon locked
                # mid-charge or by Encore gets a trimmed one, and submitted move
                # indices are relative to it.
                choosable = tuple(move["id"] for move in moves if "id" in move)
                # `target` is absent for a locked move; None means "submit no target".
                choosable_targets = tuple(move.get("target") for move in moves if "id" in move)
                # Only record PP when the engine actually reports it. A Pokemon
                # locked into a charging move gets an entry with no `pp` field,
                # and defaulting that to 0 reads as "no PP left", filtering out
                # the one move it is allowed to use.
                if moves and all("pp" in move for move in moves):
                    pp = tuple(move["pp"] for move in moves)
                disabled = frozenset(
                    move["id"] for move in moves if move.get("disabled") and "id" in move
                )
                specials = frozenset(
                    mechanic
                    for flag, mechanic in ENGINE_SPECIAL_FLAGS.items()
                    if active.get(flag)
                )
                if active.get("trapped") or active.get("maybeTrapped"):
                    volatiles = volatiles | {TRAPPED}

            team.append(
                BattlePokemon(
                    pokemon_set=pokemon_set,
                    current_hp=health.current,
                    max_hp=max_hp,
                    status=health.status,
                    current_ability=to_id(entry.get("ability") or entry.get("baseAbility", "")),
                    current_item=to_id(entry["item"]) if entry.get("item") else None,
                    choosable_moves=choosable,
                    choosable_move_targets=choosable_targets,
                    move_pp=pp,
                    volatile_conditions=volatiles,
                    disabled_moves=disabled,
                    available_specials=specials,
                    has_been_active=bool(entry.get("active")),
                )
            )
            if entry.get("active"):
                active_slots.append(index)

        while len(active_slots) < self.regulation.active_slots_per_side:
            active_slots.append(None)

        return Side(
            team=tuple(team),
            active_slots=tuple(active_slots[: self.regulation.active_slots_per_side]),
        )

    def opponent_side(self) -> ObservedSide:
        revealed = [self._opponents[species].snapshot() for species in self._opponent_order]
        position = {species: i for i, species in enumerate(self._opponent_order)}
        return ObservedSide(
            revealed=tuple(revealed),
            active_slots=tuple(
                None if occupant is None else position[occupant]
                for occupant in self._opponent_slots
            ),
            unrevealed_count=max(0, self._opponent_team_size - len(self._opponent_order)),
            side_conditions=dict(self._opponent_side_conditions),
            mega_used=self._opponent_mega_used,
        )

    def team_preview(self) -> TeamPreview:
        """The pick-N-of-6 decision point. Not an Observation -- no battle exists yet."""
        if len(self._opponent_roster) != self.regulation.min_team_size:
            raise RuntimeError(
                f"opponent roster has {len(self._opponent_roster)} Pokemon, "
                f"expected {self.regulation.min_team_size}; team preview not reached yet"
            )
        return TeamPreview(
            regulation=self.regulation,
            own_team=self._own_team,
            opponent_team=tuple(self._opponent_roster),
        )

    def observation(self) -> Observation:
        return Observation(
            regulation=self.regulation,
            turn=self._turn,
            player=self.player,
            own_side=self.own_side(),
            opponent_side=self.opponent_side(),
            weather=self.weather,
            terrain=self.terrain,
            field_conditions=dict(self.field_conditions),
        )
