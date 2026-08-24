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
from typing import NamedTuple

from champions_ai.agents.base import Agent
from champions_ai.dex import Dex, MoveInfo, SpeciesInfo, to_id
from champions_ai.domain import (
    FIRST_TURN_MOVES,
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
from champions_ai.domain.boosts import BOOST_FIELDS, MAX_STAGE, MIN_STAGE
from champions_ai.mechanics import (
    PARALYSIS,
    TAILWIND,
    TRICK_ROOM,
    apply_boost,
    assumed_attacks,
    assumed_stats,
    attacking_side,
    dynamic_base_power,
    effective_speed,
    estimate_damage,
    estimate_stats,
    is_removable,
    matchup,
    move_priority,
    moves_first,
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
# The fallback for the 56 status moves whose effects live in an `onHit`
# callback the engine cannot dump. Fitted from 12 up to 30: humans reach for
# Belly Drum, Haze, Defog and Baton Pass far more than a token value implied,
# so "unknown" should not mean "probably not worth it".
STATUS_MOVE_VALUE = 30.0

# Protect's three were hand-chosen in experiment 0003 and fitted in 0010: the
# agreement curve has a sharp peak at this combination (44.5% at a tempo cost
# of -60, 45.7% at -160, 44.7% at -260). Together they say something specific
# and legible: protect only against a *large* incoming hit, because the turn it
# costs is expensive. The knockout bonus is flat anywhere between 0 and 40, so
# it keeps a positive value on the grounds that surviving a knockout plainly
# matters even where agreement cannot see it.
#
# Protect is priced as damage *avoided*, in the same currency as damage dealt,
# so the two compete on equal terms instead of Protect carrying a flat value
# that almost any attack outbids. Measured against real humans (experiment
# 0002), the flat value made the heuristic protect almost never: 90 of 643
# disagreements were a human protecting where it attacked.
PROTECT_DAMAGE_WEIGHT = 430.0
# Surviving a knockout is worth less than landing one -- you keep a Pokemon,
# but you have not removed theirs.
PROTECT_SAVES_KO_BONUS = 40.0
# Attacking advances the game and protecting does not, so blocking N% of your
# HP is worth slightly less than dealing N% of theirs.
PROTECT_TEMPO_COST = -160.0
# Drain and recoil are priced in the same currency as damage dealt, because
# that is exactly what they are: HP moved between the two bars. Weighted a
# little below offence, since HP on our own bar is worth slightly less than HP
# removed from theirs -- taking a Pokemon out removes its actions too.
SUSTAIN_WEIGHT = 70.0

# What a status is worth, as a fraction of a health bar. These are judgements,
# not measurements, and they are ordered by how much of a Pokemon's
# contribution the status removes rather than by how much damage it deals:
# sleep takes turns away outright, paralysis halves Speed *and* skips turns,
# burn halves physical attack, poison is chip damage and little else.
STATUS_VALUE = {
    "slp": 0.60,
    "frz": 0.55,
    "par": 0.35,
    "brn": 0.30,
    "tox": 0.25,
    "psn": 0.15,
}
STATUS_WEIGHT = 100.0

# Types that cannot receive a given status at all. Ignoring this made Nuzzle
# look like a fine answer to an Electric-type and Will-O-Wisp to a Fire-type.
STATUS_IMMUNE_TYPES = {
    "par": {"Electric"},
    "brn": {"Fire"},
    "psn": {"Poison", "Steel"},
    "tox": {"Poison", "Steel"},
    "frz": {"Ice"},
}

# One stat stage, as a fraction of a health bar. Flat across stats on purpose:
# weighting them separately is a refinement, and an unjustified table of six
# numbers is harder to argue with than one.
STAT_STAGE_VALUE = 0.12
STAT_STAGE_WEIGHT = 100.0

# Stats whose loss only matters if something actually hits us afterwards. An
# offensive drop reduces our damage whatever happens; a defensive one is a bill
# that only arrives if we are still there to be hit. Charging Close Combat the
# full price for its own -1 Def/-1 SpD made the agent avoid one of the format's
# best attacks.
DEFENSIVE_STATS = frozenset({"def", "spd", "evasion"})

# A flinch denies the target its whole turn. Priced above a single status
# because it is immediate and unconditional once it lands -- but it is worth
# nothing at all unless we move first, which is where most of its subtlety is.
FLINCH_VALUE = 0.40
FLINCH_WEIGHT = 100.0

# --- what a status move that is not Protect is worth -------------------------
#
# Three of these are *not* new judgements. A stat stage is priced with
# STAT_STAGE_VALUE, a status with STATUS_VALUE and healing with SUSTAIN_WEIGHT,
# which are the same numbers the damaging path already uses for the same
# things -- so Swords Dance is worth what a Swords Dance rider is worth, and a
# Recover is worth what a drain of the same size is worth. Nothing about a
# move being "a status move" changes what it buys.
#
# The tables below are judgements in the same sense STATUS_VALUE is, and are
# priced as a fraction of a health bar for the same reason: so they compete
# with damage on equal terms rather than sitting on a separate scale.
#
# They were then *fitted* by coordinate descent against human agreement on the
# training half of the corpus, and reported on the test half, which the sweep
# never saw (experiment 0010). The test gain came out larger than the training
# gain, which is the sign that they generalise rather than memorise.

# Which targets mean "our side". Boosts land on the move's target, so a Swords
# Dance and a Growl carry the same field with opposite meanings.
SELF_TARGETS = frozenset({
    "self", "adjacentAlly", "adjacentAllyOrSelf", "allies", "allySide", "allyTeam",
})

# A screen halves damage for several turns. Priced off the incoming threat the
# way Protect is, rather than flat: a screen with nothing to block is worth
# nothing, and one in front of a knockout is worth a great deal.
SCREEN_CONDITIONS = frozenset({"reflect", "lightscreen", "auroraveil"})
SCREEN_TURNS = 3.0
SCREEN_FRACTION_BLOCKED = 0.5
SCREEN_WEIGHT = 30.0

# Everything else a move can put on a side. Hazards are deliberately cheap:
# this is a four-Pokemon format over about five turns where rated humans
# switch on 11.5% of decisions, so a hazard collects far less than it would in
# singles.
SIDE_CONDITION_VALUE = {
    "tailwind": 45.0,
    "safeguard": 15.0,
    "mist": 8.0,
    "stealthrock": 10.0,
    "spikes": 7.0,
    "toxicspikes": 7.0,
    "stickyweb": 10.0,
    "luckychant": 5.0,
}

# Weather and terrain are worth something to a team built around them and
# little to one that is not, which this cannot see. A modest flat value is the
# honest placeholder rather than a confident number.
WEATHER_VALUE = 26.0
TERRAIN_VALUE = 14.0
# Trick Room is capped deliberately. Agreement keeps rising with it all the way
# to 5,000, because a team that brought Trick Room nearly always uses it -- so
# the fit degenerates from "worth this much" into "always do this". An agent
# that recommends Trick Room regardless of the matchup would be wrong in a way
# human agreement cannot see, so this stays a valuation.
PSEUDO_WEATHER_VALUE = {"trickroom": 55.0, "gravity": 12.0}
PSEUDO_WEATHER_DEFAULT = 10.0

# Volatiles inflicted on an opponent, ordered by how much of a turn they take
# away. Taunt was fitted to 50 (a real peak); Encore and Leech Seed were left
# where they were, because the agreement curve is flat across their whole
# plausible range and moving them would be fitting noise. Taunt and Encore
# remove a choice outright; Leech Seed is chip damage with a heal attached.
VOLATILE_VALUE = {
    "taunt": 50.0,
    "encore": 30.0,
    "yawn": 30.0,
    "leechseed": 26.0,
    "confusion": 25.0,
    "disable": 22.0,
    "attract": 18.0,
    "torment": 14.0,
    "healblock": 14.0,
    "embargo": 8.0,
    "telekinesis": 5.0,
}
# Ours, on ourselves.
SELF_VOLATILE_VALUE = {"substitute": 28.0, "aquaring": 14.0, "ingrain": 10.0, "focusenergy": 12.0}
VOLATILE_DEFAULT = 12.0

# Low enough that anything else legal is preferred, without being so
# extreme that it swamps a whole joint action's score.
UNUSABLE_MOVE_SCORE = -200.0

# How a Team Preview pick is judged. A team is not a collection of good
# Pokemon, it is a set of *answers*: what matters is having something for each
# thing they brought, not maximising an average.
COVERAGE_WEIGHT = 1.0
# A small pull towards picks that are good on average, to break ties between
# two sets with the same worst case.
AVERAGE_WEIGHT = 0.25
# Switching costs a turn and buys a better position. Priced flatly, which is
# crude and known to be crude: rated humans switch on 11.5% of decisions and
# this agent on 1.8%.
#
# A matchup-based replacement was built, measured and **reverted** -- see
# docs/experiments/0004. It tripled switch agreement (6.8% -> 23.2%) and still
# came out worse on every other measure: 3.4 points of overall agreement
# (McNemar chi2 = 172 on 11,133 labels), worse against Random (96.7% against
# 99.0%), and a head-to-head edge that did not survive being re-run at higher
# power. Switching remains an open problem, not a solved one.
SWITCH_COST = -25.0
SWITCH_WHEN_WEAKENED_BONUS = 55.0
LOW_HP_FRACTION = 0.35


@dataclass(frozen=True)
class ScoredAction:
    """One action, its score, and why."""

    action: SlotAction
    score: float
    reasons: tuple[str, ...] = field(default=())


class ResolvedTarget(NamedTuple):
    """What a move is aimed at, with the stats that move will read off it.

    Named rather than a bare tuple because the last field is conditional: it
    holds a value only for a move whose attacking stat comes from this side of
    the field, and `_, _, _, _, x = target` would say nothing about that.
    """

    species: SpeciesInfo
    remaining_hp: int
    defending_stat: int
    is_ally: bool
    # Set only for Foul Play, which swings with the target's Attack rather
    # than the user's. None means "the user's own stat applies", which is
    # every other move.
    attacking_stat: int | None = None
    # Hex and Infernal Parade double against a target carrying any status.
    status: str | None = None
    # A resist berry halves the hit it fires on. None means "none that we know
    # of", which for an opponent is the honest answer until they show it.
    item: str | None = None
    # Sticky Hold refuses to give the item up, so Knock Off gets no boost.
    ability: str | None = None


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
        # 11, not 12: six stats at 12 is 72 points, over Reg M-B's budget of
        # 66, so the old default modelled every opponent with a spread that
        # cannot legally exist. Uniform beats concentrated priors against real
        # damage (0.89x versus 1.14-1.18x), so the shape stays.
        assumed_opponent_points: int = 11,
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
        """A flat cost, plus a bonus for rescuing something nearly dead.

        Deliberately unsophisticated. The matchup-based version this replaced
        is recoverable from git history and documented in experiment 0004; it
        was reverted on evidence, not abandoned for lack of one.
        """
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

        if move.move_id in FIRST_TURN_MOVES and attacker.turns_on_field > 1:
            # The engine refuses these outright after the first turn out, and
            # it does so at runtime rather than reporting them as disabled, so
            # nothing upstream filters them for us.
            return ScoredAction(
                action,
                UNUSABLE_MOVE_SCORE,
                (f"{move.name} only works on its first turn out",),
            )

        if not move.is_damaging:
            return self._score_status_move(observation, slot, action, move, attacker)

        target = self._resolve_target(observation, slot, action)
        if target is None:
            return ScoredAction(action, 0.0, (f"{move.name} has no visible target",))

        defender_species = target.species
        is_ally = target.is_ally
        estimate = estimate_damage(
            self.dex,
            move,
            attacker=attacker_species,
            # `attacking_stat` is set only for Foul Play, which swings with
            # whatever it is aimed at rather than with the user.
            attack_stat=(
                self._attack_stat(attacker, move)
                if target.attacking_stat is None
                else target.attacking_stat
            ),
            defender=defender_species,
            defense_stat=target.defending_stat,
            defender_hp=target.remaining_hp,
            # Twenty-nine moves have their power computed per hit. Most are
            # exact here; Gyro Ball and Electro Ball need the target's Speed,
            # which the target resolution does not carry, and fall back to a
            # middling value rather than to zero.
            base_power=dynamic_base_power(
                move,
                attacker=attacker_species,
                defender=defender_species,
                attacker_hp_fraction=attacker.hp_fraction,
                attacker_speed=(attacker.computed_stats or {}).get("spe"),
                attacker_holds_item=attacker.current_item is not None,
                attacker_positive_boosts=attacker.boosts.positive_total,
                attacker_status=attacker.status,
                defender_status=target.status,
                # Only what they have shown us. An opponent's item is hidden
                # until it fires, so an unrevealed one reads as "none" and
                # Knock Off is priced at its floor rather than its ceiling.
                # Holding one is not enough either: a Mega Stone cannot be
                # taken off the species it evolves, and this dex is full of
                # them.
                defender_item_removable=is_removable(
                    self.dex.items.get(target.item or ""),
                    defender_species,
                    target.ability,
                ),
                fainted_allies=sum(
                    1 for mon in observation.own_side.team if mon.fainted
                ),
                terrain=observation.terrain,
                weather=observation.weather,
            ),
            level=observation.regulation.level,
            doubles=observation.regulation.game_type == "doubles",
            attacker_burned=attacker.status == "brn",
            weather=observation.weather,
            # Ours comes from our own request and is never hidden. Theirs is
            # None until the engine announces it -- `revealed_item` was
            # tracked from the day it was written and read by nothing.
            attacker_item=attacker.current_item,
            defender_item=target.item,
            # Endeavor and Final Gambit are priced off our own remaining HP.
            attacker_hp=attacker.current_hp,
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

        rider, rider_reasons = self._rider_value(move, defender_species, observation, slot)
        score += rider * move.hit_chance
        reasons.extend(rider_reasons)

        return ScoredAction(action, score, tuple(reasons))

    def _rider_value(
        self, move, defender_species, observation: Observation, slot: int
    ) -> tuple[float, list[str]]:
        """What the move does besides damage: status, stat changes, self-cost.

        Priced by expected value -- a 30% burn is worth 30% of a burn -- with
        one exception that is not a rounding detail: a guaranteed rider is
        certain, and Nuzzle's paralysis or Zap Cannon's are the entire reason
        those moves are worth pressing at 20 base power and 50% accuracy.
        """
        value = 0.0
        reasons: list[str] = []
        target = self._observed_target(observation, slot)

        for secondary in move.secondaries:
            chance = secondary.chance / 100

            if secondary.status:
                gain = self._status_value(secondary.status, defender_species, target)
                if gain:
                    value += chance * gain * STATUS_WEIGHT
                    certainty = "always" if secondary.is_guaranteed else f"{secondary.chance}%"
                    reasons.append(f"{certainty} inflicts {secondary.status}")

            if secondary.volatile_status == "flinch":
                first = self._moves_first(move, observation, slot)
                if first > 0 and (target is None or not target.fainted):
                    value += chance * first * FLINCH_VALUE * FLINCH_WEIGHT
                    reasons.append(
                        f"{secondary.chance}% flinch"
                        + ("" if first == 1.0 else " if we move first")
                    )
                else:
                    reasons.append("its flinch is wasted moving second")

            for stat, stages in secondary.boosts.items():
                # Negative stages on the target are good for us.
                value += chance * -stages * STAT_STAGE_VALUE * STAT_STAGE_WEIGHT
                if stages < 0:
                    reasons.append(f"drops their {stat}")

            for stat, stages in secondary.self_boosts.items():
                value += chance * stages * STAT_STAGE_VALUE * STAT_STAGE_WEIGHT
                if stages > 0:
                    reasons.append(f"raises our {stat}")

        # Unconditional, as distinct from a rider: Close Combat always drops
        # its own defences rather than rolling for it.
        attacker = self._own_active(observation, slot)
        threat = 1.0
        if attacker is not None and any(
            stat in DEFENSIVE_STATS and stages < 0
            for stat, stages in move.self_boosts.items()
        ):
            threat, _, _ = self._incoming_threat(observation, slot, attacker)

        for stat, stages in move.self_boosts.items():
            cost = stages * STAT_STAGE_VALUE * STAT_STAGE_WEIGHT
            if stat in DEFENSIVE_STATS and stages < 0:
                # Priced against what is actually coming: dropping our defence
                # in front of something harmless costs nothing.
                cost *= threat
            value += cost
            if stages < 0:
                reasons.append(f"but lowers our own {stat}")

        return value, reasons

    def _status_value(self, status: str, defender_species, target) -> float:
        """Worth of landing `status`, or zero when it cannot land at all."""
        if status not in STATUS_VALUE:
            return 0.0
        # A Pokemon can only carry one status, so a second never lands.
        if target is not None and target.status:
            return 0.0
        immune = STATUS_IMMUNE_TYPES.get(status, set())
        if immune & set(defender_species.types):
            return 0.0
        return STATUS_VALUE[status]

    def _moves_first(self, move: MoveInfo, observation: Observation, slot: int) -> float:
        """Probability we act before everything on the other side.

        The worst case over both opponents, which is what the flinch this
        drives actually needs: a flinch is wasted if *anything* moves before
        us and knocks the flincher out.

        The rule itself lives in `mechanics.turn_order` and is checked against
        the engine directly. What is uncertain here, and only here, is the
        opponent's *move* -- we are choosing before they reveal it.
        """
        attacker = self._own_active(observation, slot)
        if attacker is None:
            return 0.0

        trick_room = TRICK_ROOM in observation.field_conditions
        ours = effective_speed(
            (attacker.computed_stats or {}).get("spe", 0),
            boost_stage=attacker.boosts.speed,
            tailwind=TAILWIND in observation.own_side.side_conditions,
            paralysed=attacker.status == PARALYSIS,
            item=attacker.current_item,
        )
        their_tailwind = TAILWIND in observation.opponent_side.side_conditions

        chance = 1.0
        opponent = observation.opponent_side
        for index in opponent.active_slots:
            if index is None:
                continue
            observed = opponent.revealed[index]
            if observed.fainted:
                continue
            try:
                species = self.dex.get_species(observed.species)
            except KeyError:
                continue
            theirs = effective_speed(
                estimate_stats(species.base_stats, self.assumed_opponent_points)["spe"],
                boost_stage=observed.boosts.speed,
                tailwind=their_tailwind,
                paralysed=observed.status == PARALYSIS,
                item=observed.revealed_item,
            )
            chance = min(
                chance,
                moves_first(
                    move_priority(
                        move,
                        attacker.current_ability,
                        at_full_hp=attacker.hp_fraction >= 1.0,
                    ),
                    ours,
                    self._revealed_priority(observed),
                    theirs,
                    trick_room=trick_room,
                ),
            )
        return chance

    def _revealed_priority(self, observed) -> float:
        """The highest priority we have actually seen this Pokemon use.

        Their ability counts too, once revealed -- a Grimmsnarl whose Prankster
        has shown itself puts every status move it has a bracket above ours.
        `revealed_ability` was tracked by the tracker and read by nothing until
        now, which is the same shape as most of the bugs in this project.

        Unrevealed moves are assumed ordinary. That is optimistic -- they may
        be holding an Aqua Jet we have not seen -- but assuming one would be
        worse: it would make our own priority moves look useless against a
        Pokemon that has shown nothing at all, which is every Pokemon on the
        turn it arrives.
        """
        ability = observed.revealed_ability
        at_full_hp = observed.hp_percent >= 100
        return max(
            (
                move_priority(m, ability, at_full_hp=at_full_hp)
                for m in self._revealed_moves(observed)
            ),
            default=0.0,
        )

    @staticmethod
    def _observed_target(observation: Observation, slot: int):
        """The opponent this slot would most likely be hitting, if visible."""
        opponent = observation.opponent_side
        for index in opponent.active_slots:
            if index is not None and not opponent.revealed[index].fainted:
                return opponent.revealed[index]
        return None

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
        """What this move actually changes, priced like everything else.

        Every status move but Protect used to score a flat 12.0, so Swords
        Dance, Thunder Wave, Recover and Trick Room were indistinguishable --
        and, worse, a *redundant* one scored the same as a fresh one. Recover
        at full HP, Swords Dance at +6 and a second Tailwind were as attractive
        as the first use of any of them.

        Fifty-six of the 175 status moves here keep the flat value, because
        their effects live in an `onHit` callback the engine cannot dump: Belly
        Drum, Haze, Heal Bell, Defog, Baton Pass. Those are unknown rather than
        worthless, and a flat value says so.
        """
        if move.move_id in PROTECT_MOVES:
            return self._score_protect(observation, slot, action, move, attacker)

        observed = self._observed_target(observation, slot)
        on_us = move.target in SELF_TARGETS
        value = 0.0
        reasons: list[str] = []

        value += self._boost_value(move, attacker, observed, on_us, reasons)
        value += self._status_move_status(move, observed, reasons)
        value += self._heal_value(move, attacker, reasons)
        value += self._field_value(move, observation, slot, attacker, reasons)
        value += self._volatile_value(move, observed, on_us, reasons)

        if not reasons:
            return ScoredAction(
                action, STATUS_MOVE_VALUE, (f"{move.name} is a support move",)
            )
        return ScoredAction(action, value * move.hit_chance, tuple(reasons))

    def _boost_value(self, move, attacker, observed, on_us, reasons) -> float:
        """Stat stages the move applies, worth only the headroom that is left.

        A stage is capped at six either way, so a second Swords Dance at +5
        buys one stage and a third buys none. That headroom check is most of
        the value here: without it the agent will boost forever.
        """
        value = 0.0
        for stat, delta in move.boosts.items():
            field = BOOST_FIELDS.get(stat)
            if field is None:
                continue
            if on_us:
                current = getattr(attacker.boosts, field)
                gained = max(0, min(delta, MAX_STAGE - current))
                if gained:
                    value += gained * STAT_STAGE_VALUE * STAT_STAGE_WEIGHT
                    reasons.append(f"raises our {stat} by {gained}")
                elif delta > 0:
                    reasons.append(f"our {stat} is already maxed out")
            else:
                if observed is None:
                    continue
                current = getattr(observed.boosts, field)
                # Only drops are worth anything on an opponent, and only as
                # far as they can still fall.
                dropped = max(0, min(-delta, current - MIN_STAGE))
                if dropped:
                    value += dropped * STAT_STAGE_VALUE * STAT_STAGE_WEIGHT
                    reasons.append(f"drops their {stat} by {dropped}")
                elif delta < 0:
                    reasons.append(f"their {stat} is already at the floor")

        # A move that lowers its user's own stats while doing something else.
        for stat, delta in move.self_boosts.items():
            if delta < 0:
                value += delta * STAT_STAGE_VALUE * STAT_STAGE_WEIGHT
                reasons.append(f"but costs us {-delta} stage(s) of {stat}")
        return value

    def _status_move_status(self, move, observed, reasons) -> float:
        """A status the move inflicts, priced exactly as a rider would be."""
        if not move.status or observed is None:
            return 0.0
        try:
            species = self.dex.get_species(observed.species)
        except KeyError:
            return 0.0
        gain = self._status_value(move.status, species, observed)
        if not gain:
            reasons.append(f"{move.status} cannot land on that target")
            return 0.0
        reasons.append(f"inflicts {move.status}")
        return gain * STATUS_WEIGHT

    def _heal_value(self, move, attacker, reasons) -> float:
        """Healing, in the same currency as a drain of the same size.

        Clamped to the HP actually missing, which is the whole point: a
        Recover at full health restores nothing and used to score the same as
        one at death's door.
        """
        if not move.heal:
            return 0.0
        fraction = move.heal[0] / move.heal[1]
        missing = max(0, attacker.max_hp - attacker.current_hp) / max(1, attacker.max_hp)
        restored = min(fraction, missing)
        if restored <= 0:
            reasons.append("already at full HP, so the healing is wasted")
            return 0.0
        reasons.append(f"restores ~{restored:.0%} of its HP")
        return restored * SUSTAIN_WEIGHT

    def _field_value(self, move, observation, slot, attacker, reasons) -> float:
        """Screens, Tailwind, weather, terrain and Trick Room.

        Anything already up is worth nothing, which is the check that stops
        the agent re-setting its own Tailwind every turn.
        """
        value = 0.0

        if move.side_condition:
            condition = to_id(move.side_condition)
            if condition in observation.own_side.side_conditions:
                reasons.append(f"{move.name} is already up on our side")
            elif condition in SCREEN_CONDITIONS:
                # Priced off what it would actually block, like Protect.
                fraction, _, source = self._incoming_threat(observation, slot, attacker)
                blocked = fraction * SCREEN_FRACTION_BLOCKED * SCREEN_TURNS
                value += blocked * SCREEN_WEIGHT
                reasons.append(
                    f"halves ~{fraction:.0%} incoming for several turns ({source})"
                )
            else:
                value += SIDE_CONDITION_VALUE.get(condition, STATUS_MOVE_VALUE)
                reasons.append(f"sets {move.side_condition} on our side")

        if move.sets_weather:
            if to_id(move.sets_weather) == (observation.weather or ""):
                reasons.append(f"{move.sets_weather} is already up")
            else:
                value += WEATHER_VALUE
                reasons.append(f"sets {move.sets_weather}")

        if move.sets_terrain:
            if to_id(move.sets_terrain) == (observation.terrain or ""):
                reasons.append(f"{move.sets_terrain} is already up")
            else:
                value += TERRAIN_VALUE
                reasons.append(f"sets {move.sets_terrain}")

        if move.pseudo_weather:
            condition = to_id(move.pseudo_weather)
            if condition in observation.field_conditions:
                reasons.append(f"{move.pseudo_weather} is already up")
            else:
                value += PSEUDO_WEATHER_VALUE.get(condition, PSEUDO_WEATHER_DEFAULT)
                reasons.append(f"sets {move.pseudo_weather}")

        return value

    def _volatile_value(self, move, observed, on_us, reasons) -> float:
        """Taunt, Encore, Leech Seed, Substitute and the rest.

        Judgements, ordered by how much of a turn the volatile takes away.
        Worth nothing when the target already has it.
        """
        if not move.volatile_status:
            return 0.0
        volatile = to_id(move.volatile_status)
        if on_us:
            reasons.append(f"puts {move.volatile_status} on us")
            return SELF_VOLATILE_VALUE.get(volatile, VOLATILE_DEFAULT)
        if observed is None:
            return 0.0
        if volatile in observed.volatile_conditions:
            reasons.append(f"they already have {move.volatile_status}")
            return 0.0
        reasons.append(f"inflicts {move.volatile_status}")
        return VOLATILE_VALUE.get(volatile, VOLATILE_DEFAULT)

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

            for move in candidates:
                attacking = move.offensive_stat
                defending = move.defensive_stat
                # Credit investment to the stat the move actually uses: an
                # opponent swinging a physical move is likely built for it.
                stats = assumed_stats(
                    species.base_stats,
                    self.assumed_opponent_points,
                    attacking=attacking,
                )
                # A Foul Play aimed at us swings with *our* Attack, which is
                # exactly why it is dangerous into our own physical attacker.
                swinging_stats, swinging_boosts = attacking_side(
                    move,
                    user=(stats, observed.boosts),
                    target=(defender.computed_stats or {}, defender.boosts),
                )
                estimate = estimate_damage(
                    self.dex,
                    move,
                    attacker=species,
                    attack_stat=apply_boost(
                        swinging_stats.get(attacking, 100),
                        swinging_boosts.stage(attacking),
                    ),
                    defender=defender_species,
                    defense_stat=apply_boost(
                        (defender.computed_stats or {}).get(defending, 100),
                        defender.boosts.stage(defending),
                    ),
                    defender_hp=max(1, defender.current_hp),
                    level=observation.regulation.level,
                    doubles=observation.regulation.game_type == "doubles",
                    weather=observation.weather,
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
    def _attack_stat(attacker, move: MoveInfo) -> int:
        """The attacking stat as it stands *now*, stat stages included.

        Takes the move rather than its category because the two can disagree:
        Body Press is Physical and swings with Defense.

        Boosts were tracked in the domain model and `apply_boost` was written
        for exactly this, and nothing called either: a Pokemon that had just
        used Swords Dance scored identically to one that had not. Measured
        against 5,123 real attacks, applying them lifts predictions within ten
        points of the true damage from 35.8% to 39.2%.
        """
        key = move.offensive_stat
        # Falling back to a mid value keeps a missing stat from reading as a
        # devastating or useless attacker.
        base = (attacker.computed_stats or {}).get(key, 100)
        return apply_boost(base, attacker.boosts.stage(key))

    def _resolve_target(
        self, observation: Observation, slot: int, action: MoveAction
    ) -> "ResolvedTarget | None":
        """What the move is aimed at, with the stats the move will read off it.

        Spread moves carry no explicit target, so the first live opponent
        stands in -- enough to rank the move, though it undercounts a move
        that would hit both.
        """
        move = self.dex.get_move(attacker_move_id(observation, slot, action))
        defending_key = move.defensive_stat
        # Foul Play swings with the target's Attack, so the attacking stat has
        # to be gathered here, where the target is known.
        attacking_key = move.offensive_stat if move.uses_target_offense else None

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
            return ResolvedTarget(
                species=species,
                remaining_hp=max(1, ally.current_hp),
                defending_stat=apply_boost(
                    stats.get(defending_key, 100), ally.boosts.stage(defending_key)
                ),
                is_ally=True,
                status=ally.status,
                item=ally.current_item,
                ability=ally.current_ability,
                attacking_stat=None
                if attacking_key is None
                else apply_boost(
                    stats.get(attacking_key, 100), ally.boosts.stage(attacking_key)
                ),
            )

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
            return ResolvedTarget(
                species=species,
                remaining_hp=remaining,
                defending_stat=apply_boost(
                    estimated[defending_key], observed.boosts.stage(defending_key)
                ),
                is_ally=False,
                status=observed.status,
                item=observed.revealed_item,
                ability=observed.revealed_ability,
                # Uniform rather than credited: the calibrated attacking
                # investment is evidence from *using* a move, and a Foul Play
                # target is not the one using it.
                attacking_stat=None
                if attacking_key is None
                else apply_boost(
                    estimated[attacking_key], observed.boosts.stage(attacking_key)
                ),
            )
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
                            # No weather at Team Preview: the battle has not
                            # started, so none is set yet.
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
