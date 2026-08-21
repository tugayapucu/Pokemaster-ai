"""Turn one candidate action into numbers a model can weigh.

Experiment 0005 measured the ceiling on opponent knowledge and found it flat:
handing the heuristic the opponent's entire moveset moved agreement by less than
a tenth of a point. The binding constraint is the *rule*, not the inputs. So
these features deliberately describe the same things the heuristic already sees,
and the question being asked is whether a learned mapping beats a hand-written
one over identical information.

`heuristic_score` is included as a feature on purpose. A linear model can
reproduce the heuristic exactly by putting all its weight there, so the learned
policy starts from a floor rather than from nothing, and any gain is a gain
*over* the hand-tuned rule rather than a rediscovery of it.
"""

from collections.abc import Mapping

from champions_ai.agents.heuristic import HeuristicAgent
from champions_ai.dex import Dex
from champions_ai.domain import (
    PROTECT_MOVES,
    MoveAction,
    Observation,
    PassAction,
    SlotAction,
    SwitchAction,
)
from champions_ai.domain.move_data import MoveData

# Order is the model's input order, so it is fixed here rather than derived from
# a dict at call time -- a reordering would silently invalidate saved weights.
FEATURE_NAMES: tuple[str, ...] = (
    "bias",
    "heuristic_score",
    # what kind of action this is
    "is_move",
    "is_switch",
    "is_pass",
    "is_status_move",
    "is_protect",
    "is_spread",
    # what the move does
    "damage_fraction",
    "guaranteed_ko",
    "possible_ko",
    "super_effective",
    "resisted",
    "hit_chance",
    "has_priority",
    "drain_fraction",
    "recoil_fraction",
    "flinch_expected",
    "status_expected",
    "target_stat_drop",
    "self_stat_drop",
    # our own situation
    "own_hp_fraction",
    "incoming_threat",
    "would_be_knocked_out",
    "protect_success_chance",
    "early_turn",
)

# The heuristic's raw scores run to a few hundred; a linear model trains far
# more stably when every input sits in roughly the same range.
HEURISTIC_SCALE = 100.0


class FeatureExtractor:
    """Builds one fixed-length vector per candidate action.

    Holds the heuristic because `heuristic_score` and the incoming-threat
    estimate both come from it, and recomputing either here would be a second
    implementation to keep in step.
    """

    def __init__(self, dex: Dex, move_data: Mapping[str, MoveData]) -> None:
        self.dex = dex
        self.move_data = move_data
        self.heuristic = HeuristicAgent(dex, name="features")

    def __call__(
        self, observation: Observation, slot: int, action: SlotAction
    ) -> list[float]:
        values = dict.fromkeys(FEATURE_NAMES, 0.0)
        values["bias"] = 1.0

        scored = self.heuristic.score_slot_action(observation, slot, action)
        values["heuristic_score"] = scored.score / HEURISTIC_SCALE
        values["early_turn"] = min(observation.turn, 10) / 10.0

        own = observation.own_side
        index = own.active_slots[slot] if slot < len(own.active_slots) else None
        active = own.team[index] if index is not None else None

        if active is not None:
            values["own_hp_fraction"] = active.hp_fraction
            threat, would_ko, _ = self.heuristic._incoming_threat(observation, slot, active)
            values["incoming_threat"] = threat
            values["would_be_knocked_out"] = 1.0 if would_ko else 0.0
            values["protect_success_chance"] = 1.0 / (3.0**active.protect_streak)

        if isinstance(action, PassAction):
            values["is_pass"] = 1.0
        elif isinstance(action, SwitchAction):
            values["is_switch"] = 1.0
        elif isinstance(action, MoveAction) and active is not None:
            self._move_features(values, observation, slot, action, active)

        return [values[name] for name in FEATURE_NAMES]

    def _move_features(self, values, observation, slot, action, active) -> None:
        values["is_move"] = 1.0
        moves = active.selectable_moves
        if not 0 <= action.move_index < len(moves):
            return
        try:
            move = self.dex.get_move(moves[action.move_index])
        except KeyError:
            return

        values["hit_chance"] = move.hit_chance
        values["has_priority"] = 1.0 if move.priority > 0 else 0.0
        values["drain_fraction"] = move.drain_fraction
        values["recoil_fraction"] = move.recoil_fraction
        values["is_spread"] = 1.0 if move.target.startswith("allAdjacent") else 0.0

        if not move.is_damaging:
            values["is_status_move"] = 1.0
            values["is_protect"] = 1.0 if move.move_id in PROTECT_MOVES else 0.0

        first = self.heuristic._moves_first(move, observation, slot)
        for secondary in move.secondaries:
            chance = secondary.chance / 100.0
            if secondary.volatile_status == "flinch":
                values["flinch_expected"] += chance * first
            if secondary.status:
                values["status_expected"] += chance
            values["target_stat_drop"] += chance * -sum(
                v for v in secondary.boosts.values() if v < 0
            )
        values["self_stat_drop"] += -sum(v for v in move.self_boosts.values() if v < 0)

        # Damage against whatever this action is aimed at, via the same
        # resolution the heuristic uses so the two cannot disagree.
        target = self.heuristic._resolve_target(observation, slot, action)
        if target is None or not move.is_damaging:
            return
        species = target.species
        if target.is_ally:
            return
        from champions_ai.mechanics import dynamic_base_power, estimate_damage

        estimate = estimate_damage(
            self.dex, move,
            attacker=self.dex.get_species(active.pokemon_set.species),
            attack_stat=(
                self.heuristic._attack_stat(active, move)
                if target.attacking_stat is None
                else target.attacking_stat
            ),
            defender=species,
            defense_stat=target.defending_stat,
            defender_hp=target.remaining_hp,
            level=observation.regulation.level,
            doubles=observation.regulation.game_type == "doubles",
            attacker_burned=active.status == "brn",
            weather=observation.weather,
            base_power=dynamic_base_power(
                move,
                attacker=self.dex.get_species(active.pokemon_set.species),
                defender=species,
                attacker_hp_fraction=active.hp_fraction,
                attacker_speed=(active.computed_stats or {}).get("spe"),
                attacker_holds_item=active.current_item is not None,
                attacker_positive_boosts=active.boosts.positive_total,
                defender_status=target.status,
                fainted_allies=sum(
                    1 for mon in observation.own_side.team if mon.fainted
                ),
                terrain=observation.terrain,
            ),
        )
        values["damage_fraction"] = estimate.average_fraction
        values["guaranteed_ko"] = 1.0 if estimate.guaranteed_ko else 0.0
        values["possible_ko"] = 1.0 if estimate.possible_ko else 0.0
        values["super_effective"] = 1.0 if estimate.effectiveness > 1 else 0.0
        values["resisted"] = 1.0 if 0 < estimate.effectiveness < 1 else 0.0
