"""One-turn lookahead that accounts for the opponent hitting back.

The heuristic treats opponents purely as damage targets: it never asks whether
it is about to be knocked out, or whether it even moves first. This does, which
is most of what "search" buys at this depth.

**Not true multi-ply search.** A real one would fork the battle and ask the
simulator what actually happens. That turns out to be possible -- Showdown
supports `Battle.toJSON()`/`fromJSON()`, and a fork advances in complete
isolation from the original at roughly 460 forks/sec (measured; see
`PROJECT_PLAN.md` section 15). It is simply not what is limiting play right
now: `docs/experiments/0001` found search depth is not the bottleneck,
opponent knowledge is.

So this estimates a single exchange with the same approximate damage model the
heuristic uses. Reimplementing battle resolution to get a faster forward model
remains ruled out by ADR 0001 -- forking the real engine is exact by
construction, where a reimplementation would diverge silently.

Opponent replies are drawn from what has actually been *revealed*, so the
search cannot cheat by reacting to moves a player could not know about.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from champions_ai.agents.base import Agent
from champions_ai.agents.heuristic import HeuristicAgent
from champions_ai.dex import Dex, MoveInfo, SpeciesInfo
from champions_ai.domain import JointAction, MoveAction, Observation
from champions_ai.mechanics import attacking_side, estimate_damage, estimate_stats
from champions_ai.mechanics.evaluation import HP_WEIGHT, POKEMON_WEIGHT

# How much to trust the opponent to play well. 1.0 assumes their best reply,
# 0.0 ignores them; between the two, a weighted blend of best and average.
DEFAULT_PESSIMISM = 0.7

# A knockout we suffer costs the Pokemon outright, not just its remaining HP.
INCOMING_KO_COST = POKEMON_WEIGHT + HP_WEIGHT
MOVING_FIRST_BONUS = 0.5


@dataclass(frozen=True)
class Threat:
    """What one active opponent can do to us, and whether we act first."""

    cost: float
    outsped: bool


class SearchAgent(Agent):
    """Scores actions by what they achieve *and* what they invite in return."""

    def __init__(
        self,
        dex: Dex,
        *,
        name: str = "search",
        pessimism: float = DEFAULT_PESSIMISM,
        assumed_opponent_points: int = 12,
    ) -> None:
        self.dex = dex
        self.name = name
        self.pessimism = pessimism
        self.assumed_opponent_points = assumed_opponent_points
        # The immediate-value term is the heuristic's judgement, so improving
        # the heuristic improves search rather than the two drifting apart.
        self._heuristic = HeuristicAgent(
            dex, assumed_opponent_points=assumed_opponent_points
        )

    def select_action(
        self, observation: Observation, legal_actions: Sequence[JointAction]
    ) -> JointAction:
        # Each active opponent's threat, and whether we outspeed it. Computed
        # once per position; only which of them survive depends on our action.
        threats = self._threats(observation)

        best, best_score = None, float("-inf")
        slot_cache: dict[tuple[int, object], float] = {}
        threat_cache: dict[frozenset[int], float] = {}

        for joint in legal_actions:
            immediate = sum(
                self._slot_value(observation, slot, action, slot_cache)
                for slot, action in enumerate(joint.slot_actions)
            )
            # The point of looking ahead: a move that knocks out the attacker
            # first removes its threat entirely. Without this the retaliation
            # term is the same for every action and changes nothing.
            silenced = self._slots_we_would_silence(observation, joint, threats)
            key = frozenset(silenced)
            if key not in threat_cache:
                threat_cache[key] = sum(
                    threat.cost for slot, threat in threats.items() if slot not in silenced
                )
            score = immediate - threat_cache[key] * self._exposure(observation, joint)
            if score > best_score:
                best, best_score = joint, score

        assert best is not None, "legal_actions must not be empty"
        return best

    def _slots_we_would_silence(
        self, observation: Observation, action: JointAction, threats: dict[int, "Threat"]
    ) -> set[int]:
        """Opponent slots this action would knock out *before* they act.

        Requires a guaranteed knockout, not a likely one, and requires winning
        the speed check -- a knockout that lands second still lets the attack
        through, which is exactly the mistake this is meant to avoid.
        """
        silenced: set[int] = set()
        for slot, slot_action in enumerate(action.slot_actions):
            if not isinstance(slot_action, MoveAction) or slot_action.target is None:
                continue
            if slot_action.target.side != "foe":
                continue
            target_slot = slot_action.target.slot
            threat = threats.get(target_slot)
            if threat is None or not threat.outsped:
                continue
            if self._is_guaranteed_ko(observation, slot, slot_action, target_slot):
                silenced.add(target_slot)
        return silenced

    def _is_guaranteed_ko(
        self, observation: Observation, slot: int, action: MoveAction, target_slot: int
    ) -> bool:
        scored = self._heuristic.score_slot_action(observation, slot, action)
        return any("guaranteed knockout" in reason for reason in scored.reasons)

    def _slot_value(self, observation, slot, action, cache) -> float:
        key = (slot, action)
        if key not in cache:
            cache[key] = self._heuristic.score_slot_action(observation, slot, action).score
        return cache[key]

    # ------------------------------------------------------------ opponent

    def _threats(self, observation: Observation) -> dict[int, "Threat"]:
        """Per opponent slot: what it can do to us, and whether we move first.

        Only revealed moves count. An opponent whose moves are still unknown
        looks harmless, which is optimistic -- a prior over unseen moves
        belongs to opponent modelling (Milestone 10).
        """
        our_speed = max(
            (
                (mon.computed_stats or {}).get("spe", 0)
                for mon in self._own_active(observation)
            ),
            default=0,
        )

        threats: dict[int, Threat] = {}
        for slot, index in enumerate(observation.opponent_side.active_slots):
            if index is None:
                continue
            observed = observation.opponent_side.revealed[index]
            if observed.fainted:
                continue
            try:
                species = self.dex.get_species(observed.species)
            except KeyError:
                continue

            costs = [
                self._damage_cost(species, move, defender, observation)
                for move in self._known_damaging_moves(observed)
                for defender in self._own_active(observation)
            ]
            cost = 0.0
            if costs:
                cost = self.pessimism * max(costs) + (1 - self.pessimism) * (
                    sum(costs) / len(costs)
                )

            their_speed = estimate_stats(species.base_stats, self.assumed_opponent_points)["spe"]
            threats[slot] = Threat(cost=cost, outsped=our_speed > their_speed)
        return threats

    def _expected_retaliation(self, observation: Observation) -> float:
        """Total incoming threat, ignoring anything our action might prevent."""
        return sum(threat.cost for threat in self._threats(observation).values())

    @staticmethod
    def _own_active(observation: Observation) -> list:
        return [
            observation.own_side.team[index]
            for index in observation.own_side.active_slots
            if index is not None and not observation.own_side.team[index].fainted
        ]

    def _known_damaging_moves(self, observed) -> list[MoveInfo]:
        moves = []
        for move_id in observed.revealed_moves:
            try:
                move = self.dex.get_move(move_id)
            except KeyError:
                continue
            if move.is_damaging:
                moves.append(move)
        return moves

    def _damage_cost(self, attacker, move: MoveInfo, defender, observation) -> float:
        try:
            defender_species = self.dex.get_species(defender.pokemon_set.species)
        except KeyError:
            return 0.0

        attack_stats = estimate_stats(attacker.base_stats, self.assumed_opponent_points)
        # The move names the stats it uses; the category only usually agrees.
        # `defender` here is ours, so a Foul Play aimed at us swings with our
        # own Attack -- which is what makes it dangerous into a sweeper.
        defending = (defender.computed_stats or {}).get(move.defensive_stat, 100)
        swinging = attacking_side(
            move, user=attack_stats, target=defender.computed_stats or {}
        )
        estimate = estimate_damage(
            self.dex,
            move,
            attacker=attacker,
            attack_stat=swinging.get(move.offensive_stat, 100),
            defender=defender_species,
            defense_stat=defending,
            defender_hp=max(1, defender.current_hp),
            level=observation.regulation.level,
            doubles=observation.regulation.game_type == "doubles",
        )
        if estimate.guaranteed_ko:
            return INCOMING_KO_COST
        cost = estimate.average_fraction * HP_WEIGHT
        if estimate.possible_ko:
            cost += INCOMING_KO_COST * 0.4
        return cost * move.hit_chance

    def _active_opponents(self, observation: Observation) -> list[tuple[SpeciesInfo, object]]:
        found = []
        for index in observation.opponent_side.active_slots:
            if index is None:
                continue
            observed = observation.opponent_side.revealed[index]
            if observed.fainted:
                continue
            try:
                found.append((self.dex.get_species(observed.species), observed))
            except KeyError:
                continue
        return found

    def _exposure(self, observation: Observation, action: JointAction) -> float:
        """The share of our slots that will actually be standing there to be hit.

        Protecting removes a slot from the exchange entirely, and switching
        brings in something that has not been damaged yet, so both reduce what
        retaliation costs us.
        """
        slots = action.slot_actions
        if not slots:
            return 1.0
        exposed = 0
        for slot_action in slots:
            if not isinstance(slot_action, MoveAction):
                continue  # switching or passing: not the Pokemon being aimed at
            if self._is_protect(observation, slot_action):
                continue
            exposed += 1
        return exposed / len(slots)

    def _is_protect(self, observation: Observation, action: MoveAction) -> bool:
        for index in observation.own_side.active_slots:
            if index is None:
                continue
            moves = observation.own_side.team[index].selectable_moves
            if action.move_index < len(moves) and moves[action.move_index] == "protect":
                return True
        return False
