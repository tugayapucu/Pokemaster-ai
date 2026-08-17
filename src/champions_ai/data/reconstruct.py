"""Rebuild what each player could see, at each decision point of a replay.

The feature half of a human-agreement benchmark: `choices.py` recovers *what*
a player did, and this recovers *what they were looking at when they did it*.
Together they make a supervised example.

What may be used is deliberately asymmetric, and the asymmetry is the whole
point:

- **the acting player's own side** may be assembled from the entire replay.
  They knew which four Pokemon they brought and what those Pokemon's moves
  were from the moment the battle started, so reading a move off turn 9 to
  populate their turn 2 moveset recovers knowledge they genuinely had;
- **the opponent's side** is limited to what the log had revealed by that
  turn. Using a later reveal is exactly the future-leak `AGENTS.md` forbids,
  and it flatters results: the agent would "predict" a human's move while
  secretly knowing things the human did not.

Both trackers are fed the same spectator log, each treating the *other* player
as its opponent. So player 0's opponent view comes from its own tracker, and
player 0's own side is assembled from player 1's tracker -- which is watching
player 0 from outside. That is a real limitation rather than a trick: a replay
only ever shows a side from outside, so a reconstructed own side carries
percentage HP, not the exact figures a player actually saw.

Known gaps, all in the direction of an agent that knows *less* than the human:

- **stats are estimated.** Stat Points are never published, so every Pokemon is
  given the regulation's budget spread evenly. Max HP, and every damage figure
  derived from it, is an estimate.
- **movesets are partial.** Only moves actually used are recoverable, so a
  Pokemon that used two of its four moves offers a two-move choice. This
  *inflates* agreement -- the human's real alternatives are missing from the
  action set -- so `known_move_counts` is reported alongside, and any result
  quoting agreement without it is overstating the case.
- **item, ability and PP are unknown** unless something revealed them, and
  move restrictions (Choice lock, Encore, Disable) are not reconstructed, so
  an action set may contain a move the engine would have rejected.
- **Illusion is not untangled.** Moves used by a disguised Zoroark are
  credited to the teammate it impersonated, matching the tracker's own
  documented limitation.
"""

from dataclasses import dataclass, field

from champions_ai.data.choices import ObservedChoice, choices_by_decision, extract_choices
from champions_ai.data.replay import Replay
from champions_ai.dex import Dex
from champions_ai.domain import (
    BattlePokemon,
    Boosts,
    MoveData,
    Observation,
    PokemonSet,
    Regulation,
    Side,
    StatSpread,
)
from champions_ai.mechanics.stats import estimate_stats, hp_stat
from champions_ai.simulator.tracker import (
    BattleTracker,
    level_from_details,
    species_from_details,
    split_ident,
    to_id,
)


@dataclass
class _OwnPokemon:
    """One Pokemon of the acting player's, as recoverable from the whole replay."""

    nickname: str
    species: str
    level: int
    # Ordered by first use, so a move index is stable across turns.
    moves: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReconstructedDecision:
    """One player, one turn: what they saw, and what they did."""

    turn: int
    player: int
    observation: Observation
    choices: tuple[ObservedChoice, ...]
    # Moves recovered per own Pokemon, in team order. The honest measure of how
    # much smaller the reconstructed action set is than the real one.
    known_move_counts: tuple[int, ...]

    @property
    def is_free_choice(self) -> bool:
        """Whether every slot's action was a normal turn decision."""
        return all(choice.is_free_choice for choice in self.choices)


def move_data_from_dex(dex: Dex) -> dict[str, MoveData]:
    """Target types for legal-action generation, from static data.

    In a live battle these come from the engine's request payload (ADR 0003),
    which a replay does not contain. Static targets are correct except where a
    Pokemon is locked mid-move, which is one of this module's known gaps.
    """
    return {
        move_id: MoveData(move_id=move_id, target=info.target)
        for move_id, info in dex.moves.items()
    }


def _recover_own_knowledge(
    log: tuple[str, ...], regulation: Regulation
) -> tuple[dict[str, _OwnPokemon], dict[str, _OwnPokemon]]:
    """Each player's own team and movesets, read from the entire replay.

    Legitimate for the player themselves, and never used for their opponent.
    """
    rosters: tuple[dict[str, _OwnPokemon], dict[str, _OwnPokemon]] = ({}, {})

    for line in log:
        parts = line.split("|")
        if len(parts) < 3:
            continue
        kind, args = parts[1], parts[2:]

        if kind in ("switch", "drag", "replace"):
            side, _, nickname = split_ident(args[0])
            if side not in ("p1", "p2"):
                continue
            roster = rosters[int(side[1]) - 1]
            species = species_from_details(args[1])
            existing = roster.get(nickname)
            if existing is None:
                roster[nickname] = _OwnPokemon(
                    nickname=nickname,
                    species=species,
                    level=level_from_details(args[1], regulation.level),
                    moves=[],
                )
            elif kind == "replace":
                # A broken Illusion: this slot was never the species we filed.
                existing.species = species

        elif kind == "move":
            # A move used `[from]` another effect need not be in the moveset at
            # all -- Copycat and Dancer call the *opponent's*. Sleep Talk's
            # would be legitimate, but it is dropped too: being conservative
            # here only shrinks the recovered set, and the move a player
            # actually chose always appears in a plain `|move|` line anyway.
            if any(part.startswith("[from]") for part in args):
                continue
            side, _, nickname = split_ident(args[0])
            if side not in ("p1", "p2"):
                continue
            entry = rosters[int(side[1]) - 1].get(nickname)
            move_id = to_id(args[1])
            # Struggle is what the engine does when nothing is usable, not a
            # move anybody put on a team sheet.
            if entry is not None and move_id != "struggle" and move_id not in entry.moves:
                entry.moves.append(move_id)

    return rosters


def _own_side(
    roster: dict[str, _OwnPokemon],
    tracker: BattleTracker,
    regulation: Regulation,
    dex: Dex,
    points_per_stat: int,
) -> tuple[Side, tuple[int, ...]]:
    """Assemble the acting player's side from the tracker watching them.

    Returns the side and, alongside it, how many moves were recovered for each
    Pokemon -- the caller needs that to report agreement honestly.
    """
    observed = tracker.observed_by_nickname()
    active = tracker.active_nicknames()

    team: list[BattlePokemon] = []
    move_counts: list[int] = []
    index_by_nickname: dict[str, int] = {}

    for nickname, entry in roster.items():
        seen = observed.get(nickname)
        # The tracker's species is the live one: a Pokemon that Mega Evolved is
        # no longer the forme its team sheet named, and its base stats changed
        # with it.
        species = seen.species if seen is not None else entry.species
        base_stats = dex.get_species(species).base_stats

        max_hp = hp_stat(base_stats.hp, points_per_stat)
        stats = estimate_stats(base_stats, points_per_stat)
        stats.pop("hp")

        if seen is None:
            # Never sent out yet. Its own player still knows it is there, and
            # it is necessarily untouched.
            current_hp, status, boosts, volatiles = max_hp, None, Boosts(), frozenset()
        elif seen.fainted:
            current_hp, status, boosts, volatiles = 0, None, Boosts(), frozenset()
        else:
            current_hp = min(max_hp, max(1, round(max_hp * seen.hp_percent / 100)))
            status, boosts = seen.status, seen.boosts
            volatiles = seen.volatile_conditions

        pokemon_set = PokemonSet(
            species=species,
            level=seen.level if seen is not None else entry.level,
            # Unknown, not absent: a replay names an ability or item only when
            # one visibly fires.
            ability=seen.revealed_ability if seen and seen.revealed_ability else "",
            moves=tuple(entry.moves),
            # Stat Points are never published (ADR 0002), so no allocation is
            # claimed here; `computed_stats` carries the estimate instead.
            stats=StatSpread(),
            item=seen.revealed_item if seen is not None else None,
        )

        is_active = nickname in active
        index_by_nickname[nickname] = len(team)
        move_counts.append(len(entry.moves))
        team.append(
            BattlePokemon(
                pokemon_set=pokemon_set,
                current_hp=current_hp,
                max_hp=max_hp,
                status=status,
                volatile_conditions=volatiles,
                boosts=boosts,
                current_ability=pokemon_set.ability or None,
                current_item=pokemon_set.item,
                computed_stats=stats,
                # Move indices in a submitted choice refer to this list, and
                # here it is all we know of the moveset.
                choosable_moves=tuple(entry.moves) if is_active else None,
                # No engine request to read targets from; the Dex supplies them.
                choosable_move_targets=None,
                # PP is not published, and claiming a number would be invented.
                move_pp=None,
                revealed_moves=frozenset(entry.moves),
                has_been_active=seen is not None,
            )
        )

    slots = tuple(
        None if nickname is None else index_by_nickname.get(nickname) for nickname in active
    )
    while len(slots) < regulation.active_slots_per_side:
        slots = (*slots, None)

    return (
        Side(team=tuple(team), active_slots=slots[: regulation.active_slots_per_side]),
        tuple(move_counts),
    )


def reconstruct_decisions(
    replay: Replay,
    regulation: Regulation,
    dex: Dex,
    *,
    points_per_stat: int | None = None,
) -> list[ReconstructedDecision]:
    """Every decision point in a replay, paired with the view it was made from.

    `points_per_stat` defaults to the regulation's whole budget spread evenly
    (66 points over 6 stats is 11 each under Reg M-B). Real spreads concentrate
    instead, so this is a neutral placeholder for something opponent modelling
    should later infer -- not a claim about how anybody built their team.
    """
    if points_per_stat is None:
        points_per_stat = regulation.max_total_stat_points // 6

    rosters = _recover_own_knowledge(replay.log, regulation)
    grouped = choices_by_decision(extract_choices(replay.log))
    trackers = [BattleTracker(regulation, player) for player in (0, 1)]

    decisions: list[ReconstructedDecision] = []
    for line in replay.log:
        for player, tracker in enumerate(trackers):
            tracker.handle({"type": "sideline", "player": f"p{player + 1}", "line": line})

        if not line.startswith("|turn|"):
            continue
        turn = int(line.split("|")[2])

        for player in (0, 1):
            choices = grouped.get((turn, player))
            if not choices or not rosters[player]:
                continue
            # The *other* tracker is the one watching this player.
            own_side, move_counts = _own_side(
                rosters[player], trackers[1 - player], regulation, dex, points_per_stat
            )
            decisions.append(
                ReconstructedDecision(
                    turn=turn,
                    player=player,
                    observation=Observation(
                        regulation=regulation,
                        turn=turn,
                        player=player,
                        own_side=own_side,
                        opponent_side=trackers[player].opponent_side(),
                        weather=trackers[player].weather,
                        terrain=trackers[player].terrain,
                        field_conditions=dict(trackers[player].field_conditions),
                    ),
                    choices=tuple(choices),
                    known_move_counts=move_counts,
                )
            )

    return decisions
