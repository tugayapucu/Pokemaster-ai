"""An agent that reasons about damage instead of guessing.

Scores every legal action and takes the best. The scoring is deliberately
readable rather than tuned: each component says something a player would say
out loud, and `explain()` returns those reasons, which is what the
recommendation system (Milestone 4) will need to show a human.

What it knows is limited to what a player knows. Opponent defensive stats are
never revealed (ADR 0002), so they are estimated from base stats under an
assumed investment -- a modelling choice to be replaced by inference in
Milestone 10, not a fact.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import combinations

from champions_ai.agents.base import Agent
from champions_ai.dex import Dex, MoveInfo, SpeciesInfo
from champions_ai.domain import (
    PROTECT_MOVES,
    JointAction,
    MoveAction,
    Observation,
    PassAction,
    SlotAction,
    SwitchAction,
    TeamPreview,
    TeamPreviewAction,
)
from champions_ai.mechanics import (
    assumed_attacks,
    estimate_damage,
    estimate_stats,
    matchup,
)

# Scoring weights. Chosen to be legible rather than optimal: damage is the
# baseline currency, and everything else is priced relative to it.
DAMAGE_WEIGHT = 100.0
GUARANTEED_KO_BONUS = 120.0
POSSIBLE_KO_BONUS = 30.0
# Hitting your own partner is almost never intended, and a spread move that
# happens to catch them is priced separately by the damage term anyway.
ALLY_DAMAGE_PENALTY = -250.0
IMMUNE_PENALTY = -60.0
RESISTED_PENALTY = -15.0
STATUS_MOVE_VALUE = 12.0

# Protect is priced as damage *avoided*, in the same currency as damage dealt,
# so the two compete on equal terms instead of Protect carrying a flat value
# that almost any attack outbids. Measured against real humans (experiment
# 0002), the flat value made the heuristic protect almost never: 90 of 643
# disagreements were a human protecting where it attacked.
PROTECT_DAMAGE_WEIGHT = 100.0
# Surviving a knockout is worth less than landing one -- you keep a Pokemon,
# but you have not removed theirs.
PROTECT_SAVES_KO_BONUS = 90.0
# Attacking advances the game and protecting does not, so blocking N% of your
# HP is worth slightly less than dealing N% of theirs.
PROTECT_TEMPO_COST = -20.0
# Drain and recoil are priced in the same currency as damage dealt, because
# that is exactly what they are: HP moved between the two bars. Weighted a
# little below offence, since HP on our own bar is worth slightly less than HP
# removed from theirs -- taking a Pokemon out removes its actions too.
SUSTAIN_WEIGHT = 70.0

# How a Team Preview pick is judged. A team is not a collection of good
# Pokemon, it is a set of *answers*: what matters is having something for each
# thing they brought, not maximising an average.
COVERAGE_WEIGHT = 1.0
# A small pull towards picks that are good on average, to break ties between
# two sets with the same worst case.
AVERAGE_WEIGHT = 0.25
SWITCH_COST = -25.0
SWITCH_WHEN_WEAKENED_BONUS = 55.0
LOW_HP_FRACTION = 0.35


@dataclass(frozen=True)
class ScoredAction:
    """One action, its score, and why."""

    action: SlotAction
    score: float
    reasons: tuple[str, ...] = field(default=())


class HeuristicAgent(Agent):
    """Picks the highest-scoring legal action.

    Needs a `Dex` because a player who could not read type matchups or move
    power would not be playing a heuristic at all.
    """

    def __init__(
        self,
        dex: Dex,
        *,
        name: str = "heuristic",
        assumed_opponent_points: int = 12,
    ) -> None:
        self.dex = dex
        self.name = name
        self.assumed_opponent_points = assumed_opponent_points

    # ------------------------------------------------------------- selection

    def select_action(
        self, observation: Observation, legal_actions: Sequence[JointAction]
    ) -> JointAction:
        best, best_score = None, float("-inf")
        # Joint actions are products of per-slot choices, so the same slot
        # action recurs many times; scoring it once keeps this linear in the
        # number of distinct choices rather than their product.
        cache: dict[tuple[int, SlotAction], ScoredAction] = {}

        for joint in legal_actions:
            total = sum(
                self._cached(observation, slot, action, cache).score
                for slot, action in enumerate(joint.slot_actions)
            )
            if total > best_score:
                best, best_score = joint, total

        assert best is not None, "legal_actions must not be empty"
        return best

    def explain(
        self, observation: Observation, action: JointAction
    ) -> tuple[ScoredAction, ...]:
        """Per-slot scores and reasons for a chosen action."""
        return tuple(
            self.score_slot_action(observation, slot, slot_action)
            for slot, slot_action in enumerate(action.slot_actions)
        )

    def _cached(
        self,
        observation: Observation,
        slot: int,
        action: SlotAction,
        cache: dict[tuple[int, SlotAction], ScoredAction],
    ) -> ScoredAction:
        key = (slot, action)
        if key not in cache:
            cache[key] = self.score_slot_action(observation, slot, action)
        return cache[key]

    # --------------------------------------------------------------- scoring

    def score_slot_action(
        self, observation: Observation, slot: int, action: SlotAction
    ) -> ScoredAction:
        if isinstance(action, PassAction):
            return ScoredAction(action, 0.0, ("nothing to do",))
        if isinstance(action, SwitchAction):
            return self._score_switch(observation, slot, action)
        return self._score_move(observation, slot, action)

    def _score_switch(
        self, observation: Observation, slot: int, action: SwitchAction
    ) -> ScoredAction:
        attacker = self._own_active(observation, slot)
        if attacker is None:
            # The slot is empty, so this is a forced replacement rather than a
            # choice to give up momentum.
            return ScoredAction(action, 0.0, ("filling an empty slot",))

        score = SWITCH_COST
        reasons = ["switching costs a turn"]
        if attacker.hp_fraction <= LOW_HP_FRACTION:
            score += SWITCH_WHEN_WEAKENED_BONUS
            reasons.append(f"{attacker.pokemon_set.species} is weakened")
        return ScoredAction(action, score, tuple(reasons))

    def _score_move(
        self, observation: Observation, slot: int, action: MoveAction
    ) -> ScoredAction:
        attacker = self._own_active(observation, slot)
        if attacker is None:
            return ScoredAction(action, 0.0, ("no active Pokemon",))

        move_id = attacker.selectable_moves[action.move_index]
        try:
            move = self.dex.get_move(move_id)
            attacker_species = self.dex.get_species(attacker.pokemon_set.species)
        except KeyError as error:
            # Unknown data is a gap to fix, not a reason to prefer or avoid the
            # move, so it scores neutrally rather than silently ranking last.
            return ScoredAction(action, 0.0, (f"no data: {error}",))

        if not move.is_damaging:
            return self._score_status_move(observation, slot, action, move, attacker)

        target = self._resolve_target(observation, slot, action)
        if target is None:
            return ScoredAction(action, 0.0, (f"{move.name} has no visible target",))

        defender_species, defender_hp, defender_defense, is_ally = target
        estimate = estimate_damage(
            self.dex,
            move,
            attacker=attacker_species,
            attack_stat=self._attack_stat(attacker, move.category),
            defender=defender_species,
            defense_stat=defender_defense,
            defender_hp=defender_hp,
            level=observation.regulation.level,
            doubles=observation.regulation.game_type == "doubles",
            attacker_burned=attacker.status == "brn",
        )

        reasons: list[str] = []
        if is_ally:
            return ScoredAction(
                action,
                ALLY_DAMAGE_PENALTY,
                (f"{move.name} would hit our own {defender_species.name}",),
            )

        if estimate.is_immune:
            return ScoredAction(
                action, IMMUNE_PENALTY, (f"{defender_species.name} is immune to {move.name}",)
            )

        score = estimate.average_fraction * DAMAGE_WEIGHT
        reasons.append(
            f"{move.name} deals ~{estimate.average_fraction:.0%} of "
            f"{defender_species.name}'s remaining HP"
        )

        if estimate.guaranteed_ko:
            score += GUARANTEED_KO_BONUS
            reasons.append("guaranteed knockout")
        elif estimate.possible_ko:
            score += POSSIBLE_KO_BONUS
            reasons.append("knockout on a high roll")

        if estimate.effectiveness > 1:
            reasons.append(f"super effective ({estimate.effectiveness:g}x)")
        elif estimate.effectiveness < 1:
            score += RESISTED_PENALTY
            reasons.append(f"resisted ({estimate.effectiveness:g}x)")

        # An accurate move is worth more than a strong one that misses. Applied
        # last so it discounts the whole package, KO bonus included.
        if not move.always_hits:
            score *= move.hit_chance
            if move.hit_chance < 1:
                reasons.append(f"{move.accuracy}% accurate")

        sustain, sustain_reasons = self._sustain(move, estimate, attacker)
        score += sustain * move.hit_chance
        reasons.extend(sustain_reasons)

        return ScoredAction(action, score, tuple(reasons))

    def _sustain(self, move, estimate, attacker) -> tuple[float, list[str]]:
        """HP the move moves onto or off our own bar.

        Drain and recoil are damage too, just pointed at us, so they belong in
        the same currency rather than as a separate adjustment. Both are
        clamped to what is actually available: healing above full is wasted,
        and recoil cannot take more HP than the Pokemon has.
        """
        if not move.drain and not move.recoil:
            return 0.0, []

        dealt = estimate.average
        value = 0.0
        reasons: list[str] = []

        if move.drain:
            missing = max(0, attacker.max_hp - attacker.current_hp)
            healed = min(move.drain_fraction * dealt, missing)
            gain = healed / attacker.max_hp
            value += gain * SUSTAIN_WEIGHT
            if gain > 0:
                reasons.append(f"heals back ~{gain:.0%} of its own HP")
            else:
                reasons.append("already at full HP, so the drain is wasted")

        if move.recoil:
            taken = min(move.recoil_fraction * dealt, attacker.current_hp)
            loss = taken / attacker.max_hp
            value -= loss * SUSTAIN_WEIGHT
            reasons.append(f"but costs ~{loss:.0%} of its own HP in recoil")
            if taken >= attacker.current_hp:
                reasons.append("which would knock it out")

        return value, reasons

    def _score_status_move(
        self,
        observation: Observation,
        slot: int,
        action: MoveAction,
        move: MoveInfo,
        attacker,
    ) -> ScoredAction:
        if move.move_id in PROTECT_MOVES:
            return self._score_protect(observation, slot, action, move, attacker)
        return ScoredAction(action, STATUS_MOVE_VALUE, (f"{move.name} is a support move",))

    def _score_protect(
        self,
        observation: Observation,
        slot: int,
        action: MoveAction,
        move: MoveInfo,
        attacker,
    ) -> ScoredAction:
        """Worth what it stops, discounted by how likely it is to fail.

        Priced against the incoming attack rather than against our own HP bar.
        A healthy Pokemon facing a knockout should protect and a weakened one
        facing nothing should not, and a flat value cannot express either.
        """
        fraction, would_ko, source = self._incoming_threat(observation, slot, attacker)

        # The engine's stall counter: each consecutive use succeeds a third as
        # often as the last. This is the game's own rule rather than a tuned
        # constant, and it is what stops a threat-aware Protect being spammed.
        success = 1.0 / (3.0**attacker.protect_streak)

        score = fraction * PROTECT_DAMAGE_WEIGHT
        reasons = [f"{move.name} would block ~{fraction:.0%} of this Pokemon's HP ({source})"]
        if would_ko:
            score += PROTECT_SAVES_KO_BONUS
            reasons.append("which would otherwise be a knockout")

        score = score * success + PROTECT_TEMPO_COST
        if attacker.protect_streak:
            reasons.append(
                f"but it protected {attacker.protect_streak} turn(s) running, "
                f"so this succeeds ~{success:.0%} of the time"
            )
        return ScoredAction(action, score, tuple(reasons))

    def _incoming_threat(
        self, observation: Observation, slot: int, defender
    ) -> tuple[float, bool, str]:
        """Worst expected hit on this Pokemon: (fraction of its HP, would KO, why).

        Revealed moves are used when there are any. When there are none the
        opponent is *not* treated as harmless -- experiment 0001 found that
        assumption is exactly why one-turn search was inert. A standard STAB
        attack is assumed instead, from their typing, which is information we
        genuinely have the moment they are on the field.
        """
        try:
            defender_species = self.dex.get_species(defender.pokemon_set.species)
        except KeyError:
            return 0.0, False, "unknown defender"

        worst, worst_ko, source = 0.0, False, "nothing visible"
        for index in observation.opponent_side.active_slots:
            if index is None:
                continue
            observed = observation.opponent_side.revealed[index]
            if observed.fainted:
                continue
            try:
                species = self.dex.get_species(observed.species)
            except KeyError:
                continue

            known = [m for m in self._revealed_moves(observed) if m.is_damaging]
            candidates = known or assumed_attacks(species)
            label = "seen" if known else "assumed"

            stats = estimate_stats(species.base_stats, self.assumed_opponent_points)
            for move in candidates:
                estimate = estimate_damage(
                    self.dex,
                    move,
                    attacker=species,
                    attack_stat=stats["atk" if move.category == "Physical" else "spa"],
                    defender=defender_species,
                    defense_stat=(defender.computed_stats or {}).get(
                        "def" if move.category == "Physical" else "spd", 100
                    ),
                    defender_hp=max(1, defender.current_hp),
                    level=observation.regulation.level,
                    doubles=observation.regulation.game_type == "doubles",
                )
                expected = estimate.average_fraction * move.hit_chance
                if expected > worst:
                    worst = expected
                    worst_ko = estimate.guaranteed_ko
                    source = f"{species.name}, {label}"
        return min(worst, 1.0), worst_ko, source

    def _revealed_moves(self, observed) -> list[MoveInfo]:
        found = []
        for move_id in observed.revealed_moves:
            try:
                found.append(self.dex.get_move(move_id))
            except KeyError:
                continue
        return found



    # ------------------------------------------------------------- resolution

    @staticmethod
    def _own_active(observation: Observation, slot: int):
        index = observation.own_side.active_slots[slot]
        return None if index is None else observation.own_side.team[index]

    @staticmethod
    def _attack_stat(attacker, category: str) -> int:
        stats = attacker.computed_stats or {}
        key = "atk" if category == "Physical" else "spa"
        # Falling back to a mid value keeps a missing stat from reading as a
        # devastating or useless attacker.
        return stats.get(key, 100)

    def _resolve_target(
        self, observation: Observation, slot: int, action: MoveAction
    ) -> tuple[SpeciesInfo, int, int, bool] | None:
        """(species, remaining HP, defending stat, is_ally) for the move's target.

        Spread moves carry no explicit target, so the first live opponent
        stands in -- enough to rank the move, though it undercounts a move
        that would hit both.
        """
        move = self.dex.get_move(attacker_move_id(observation, slot, action))
        defending_key = "def" if move.category == "Physical" else "spd"

        if action.target is not None and action.target.side == "ally":
            index = observation.own_side.active_slots[action.target.slot]
            if index is None:
                return None
            ally = observation.own_side.team[index]
            try:
                species = self.dex.get_species(ally.pokemon_set.species)
            except KeyError:
                return None
            stats = ally.computed_stats or {}
            return species, max(1, ally.current_hp), stats.get(defending_key, 100), True

        foe_slot = action.target.slot if action.target is not None else None
        opponent = observation.opponent_side
        candidates = (
            [foe_slot]
            if foe_slot is not None
            else list(range(len(opponent.active_slots)))
        )
        for candidate in candidates:
            if candidate >= len(opponent.active_slots):
                continue
            index = opponent.active_slots[candidate]
            if index is None:
                continue
            observed = opponent.revealed[index]
            if observed.fainted:
                continue
            try:
                species = self.dex.get_species(observed.species)
            except KeyError:
                continue
            estimated = estimate_stats(species.base_stats, self.assumed_opponent_points)
            remaining = max(1, estimated["hp"] * observed.hp_percent // 100)
            return species, remaining, estimated[defending_key], False
        return None



    # --------------------------------------------------------- team preview

    def select_team_preview(
        self, preview: TeamPreview, picked_team_size: int
    ) -> TeamPreviewAction:
        """Pick which Pokemon to bring, and in what order, from the matchup.

        The first decision of every battle, and the one a player most wants
        help with -- they can see six species and nothing else.

        Scored as **coverage** rather than as a sum of individually good
        Pokemon. A team wins Team Preview by having an answer to each thing the
        opponent brought, so for every one of their six we take our *best*
        answer among the four we are considering, and add those up. Picking
        four Pokemon that all beat the same threat and lose to the rest scores
        badly, which is the point.
        """
        picks = self._rank_team_preview(preview, picked_team_size)
        return TeamPreviewAction(picks=picks)

    def _rank_team_preview(
        self, preview: TeamPreview, picked_team_size: int
    ) -> tuple[int, ...]:
        scores = self._matchup_table(preview)
        if not scores:
            return tuple(range(picked_team_size))

        best_set, best_score = None, float("-inf")
        # Six choose four is fifteen combinations, so the exhaustive answer is
        # cheaper than any clever approximation would be.
        for candidate in combinations(range(len(preview.own_team)), picked_team_size):
            score = self._score_selection(candidate, scores, len(preview.opponent_team))
            if score > best_score:
                best_set, best_score = candidate, score

        assert best_set is not None
        # Lead with the two that fare best against their roster as a whole,
        # since which of their six leads is still unknown.
        return tuple(
            sorted(
                best_set,
                key=lambda index: sum(scores[index]) / max(1, len(scores[index])),
                reverse=True,
            )
        )

    def _matchup_table(self, preview: TeamPreview) -> list[list[float]]:
        """`table[ours][theirs]` -- our net matchup against each of their six."""
        table: list[list[float]] = []
        for ours in preview.own_team.pokemon:
            row: list[float] = []
            for theirs in preview.opponent_team:
                try:
                    species = self.dex.get_species(theirs.species)
                    row.append(
                        matchup(
                            self.dex,
                            ours,
                            species,
                            level=preview.regulation.level,
                            doubles=preview.regulation.game_type == "doubles",
                            assumed_points=self.assumed_opponent_points,
                        ).net
                    )
                except KeyError:
                    # Missing data must not read as a good or bad matchup.
                    row.append(0.0)
            table.append(row)
        return table

    @staticmethod
    def _score_selection(
        selection: tuple[int, ...], scores: list[list[float]], opponents: int
    ) -> float:
        coverage = sum(
            max(scores[index][foe] for index in selection) for foe in range(opponents)
        )
        average = sum(
            scores[index][foe] for index in selection for foe in range(opponents)
        ) / max(1, len(selection) * opponents)
        return COVERAGE_WEIGHT * coverage + AVERAGE_WEIGHT * average

    def explain_team_preview(
        self, preview: TeamPreview, picked_team_size: int
    ) -> tuple[tuple[str, float], ...]:
        """Per-pick reasons, for the recommendation system."""
        scores = self._matchup_table(preview)
        picks = self._rank_team_preview(preview, picked_team_size)
        reasons = []
        for index in picks:
            row = scores[index]
            worst = min(range(len(row)), key=lambda foe: row[foe])
            best = max(range(len(row)), key=lambda foe: row[foe])
            reasons.append(
                (
                    f"{preview.own_team.pokemon[index].species}: "
                    f"best into {preview.opponent_team[best].species}, "
                    f"worst into {preview.opponent_team[worst].species}",
                    sum(row) / max(1, len(row)),
                )
            )
        return tuple(reasons)



def attacker_move_id(observation: Observation, slot: int, action: MoveAction) -> str:
    index = observation.own_side.active_slots[slot]
    assert index is not None
    return observation.own_side.team[index].selectable_moves[action.move_index]
