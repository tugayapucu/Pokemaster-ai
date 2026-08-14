"""A battle as a loop agents can drive, rather than a protocol to be handled.

Owns the bridge and both players' trackers, and hides the parts every agent
would otherwise reimplement: which decision the engine is actually asking for
(team preview, a forced switch, or a normal turn), that non-switching slots
must explicitly pass during a forced switch, and that a rejected choice is a
bug rather than something to retry.

Agents see `Observation` and `JointAction` and nothing else.
"""

from dataclasses import dataclass, field
from enum import Enum
from types import TracebackType

from champions_ai.domain import (
    JointAction,
    Observation,
    PassAction,
    Regulation,
    SlotAction,
    SwitchAction,
    Team,
    TeamPreviewAction,
    legal_joint_actions,
    legal_slot_actions,
)
from champions_ai.simulator import (
    BattleTracker,
    BridgeError,
    ShowdownBridge,
    format_joint_action,
    format_team_preview,
)

PLAYER_TAGS = ("p1", "p2")


class Decision(Enum):
    """What the engine is asking a player for right now."""

    NONE = "none"
    TEAM_PREVIEW = "team_preview"
    FORCED_SWITCH = "forced_switch"
    TURN = "turn"


@dataclass(frozen=True)
class StepResult:
    """Outcome of advancing the battle."""

    terminal: bool
    winner: int | None
    turn: int
    protocol: tuple[str, ...] = field(default=(), repr=False)


class BattleEnv:
    """Two-player Champions battle driven with domain objects."""

    def __init__(
        self,
        regulation: Regulation,
        teams: tuple[Team, Team],
        *,
        bridge: ShowdownBridge | None = None,
    ) -> None:
        self.regulation = regulation
        self.teams = teams
        self._bridge = bridge or ShowdownBridge()
        self._owns_bridge = bridge is None
        self._trackers: tuple[BattleTracker, ...] = ()
        self._protocol: list[str] = []
        self._winner: int | None = None
        self._started = False
        self._pending: set[int] = set()

    # ------------------------------------------------------------- lifecycle

    def __enter__(self) -> "BattleEnv":
        if self._owns_bridge:
            self._bridge.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_bridge:
            self._bridge.close()

    def reset(self, packed_teams: tuple[str, str], *, seed: str | None = None) -> StepResult:
        """Start a battle. Packed teams come from `ShowdownBridge.validate_team`."""
        self._trackers = tuple(
            BattleTracker(self.regulation, player=index, own_team=self.teams[index])
            for index in (0, 1)
        )
        self._protocol = []
        self._winner = None
        self._started = True
        self._pending = set()

        events = self._bridge.start_battle(
            self.regulation.format_id, packed_teams[0], packed_teams[1], seed=seed
        )
        return self._absorb(events)

    # ---------------------------------------------------------------- state

    def _require_started(self) -> None:
        if not self._started:
            raise RuntimeError("call reset() before using the environment")

    def tracker(self, player: int) -> BattleTracker:
        self._require_started()
        return self._trackers[player]

    def observation(self, player: int) -> Observation:
        return self.tracker(player).observation()

    def decision(self, player: int) -> Decision:
        """What this player must choose right now, if anything.

        Driven by which players actually received a request in the last batch,
        not by stored tracker state: a player who has already chosen still
        holds their old request, and asking them again would desync the battle.
        """
        tracker = self.tracker(player)
        if self.terminal or player not in self._pending or tracker.waiting:
            return Decision.NONE
        if tracker.awaiting_team_preview:
            return Decision.TEAM_PREVIEW
        if tracker.force_switch_slots:
            return Decision.FORCED_SWITCH
        return Decision.TURN if tracker.has_request else Decision.NONE

    def awaiting(self) -> tuple[int, ...]:
        """Players the engine is currently waiting on."""
        return tuple(p for p in (0, 1) if self.decision(p) is not Decision.NONE)

    @property
    def terminal(self) -> bool:
        return self._winner is not None

    @property
    def winner(self) -> int | None:
        return self._winner

    @property
    def turn(self) -> int:
        self._require_started()
        return self._trackers[0].observation().turn

    @property
    def protocol(self) -> tuple[str, ...]:
        return tuple(self._protocol)

    # -------------------------------------------------------- legal actions

    def legal_actions(self, player: int) -> list[JointAction]:
        """Every joint action this player may submit for the current decision.

        Team preview is excluded on purpose: picking N of 6 is a different
        shape of choice, and `legal_team_previews` covers it.
        """
        tracker = self.tracker(player)
        decision = self.decision(player)
        if decision is Decision.NONE:
            return []
        if decision is Decision.TEAM_PREVIEW:
            raise ValueError("team preview is a different decision; use legal_team_previews()")

        observation = tracker.observation()
        move_data = tracker.move_data
        if decision is Decision.TURN:
            return legal_joint_actions(observation, move_data)

        return self._forced_switch_actions(observation, tracker.force_switch_slots, move_data)

    def _forced_switch_actions(
        self, observation: Observation, forced: tuple[bool, ...], move_data: dict
    ) -> list[JointAction]:
        """Only flagged slots act; the rest must pass, which the engine requires explicitly.

        Slots are resolved in sequence rather than independently, because they
        compete for the same bench: if one slot takes the last living
        replacement, the other has nothing to send and must pass. Enumerating
        slots independently and filtering conflicts afterwards loses that case
        entirely and yields no legal action at all.
        """

        def expand(slot: int, used: frozenset[int]) -> list[tuple[SlotAction, ...]]:
            if slot >= len(forced):
                return [()]
            if not forced[slot]:
                return [(PassAction(), *rest) for rest in expand(slot + 1, used)]

            switches = [
                action
                for action in legal_slot_actions(observation, slot, move_data)
                if isinstance(action, SwitchAction) and action.team_index not in used
            ]
            if not switches:
                return [(PassAction(), *rest) for rest in expand(slot + 1, used)]

            return [
                (switch, *rest)
                for switch in switches
                for rest in expand(slot + 1, used | {switch.team_index})
            ]

        return [JointAction(slot_actions=combo) for combo in expand(0, frozenset())]

    def legal_team_previews(self, player: int) -> list[TeamPreviewAction]:
        """Every ordered pick of N from the declared team.

        Order matters -- the first picks lead -- so this is permutations, not
        combinations, and grows fast; agents that only need one pick should
        construct a `TeamPreviewAction` directly.
        """
        from itertools import permutations

        size = len(self.teams[player])
        return [
            TeamPreviewAction(picks=picks)
            for picks in permutations(range(size), self.regulation.picked_team_size)
        ]

    # ------------------------------------------------------------------ step

    def step(self, actions: dict[int, JointAction | TeamPreviewAction]) -> StepResult:
        """Submit each waiting player's choice and advance the battle."""
        self._require_started()
        if self.terminal:
            raise RuntimeError("battle is over; call reset() to start another")

        expected = set(self.awaiting())
        if set(actions) != expected:
            raise ValueError(
                f"expected actions for players {sorted(expected)}, got {sorted(actions)}"
            )

        events: list[dict] = []
        for player, action in sorted(actions.items()):
            events.extend(self._bridge.choose(PLAYER_TAGS[player], self._render(player, action)))
        return self._absorb(events)

    def _render(self, player: int, action: JointAction | TeamPreviewAction) -> str:
        decision = self.decision(player)
        if decision is Decision.TEAM_PREVIEW:
            if not isinstance(action, TeamPreviewAction):
                raise TypeError(
                    f"player {player} owes a TeamPreviewAction, got {type(action).__name__}"
                )
            return format_team_preview(action)
        if not isinstance(action, JointAction):
            raise TypeError(f"player {player} owes a JointAction, got {type(action).__name__}")
        return format_joint_action(action)

    def _absorb(self, events: list[dict]) -> StepResult:
        self._pending = set()
        for event in events:
            if event["type"] == "error":
                # A rejected choice means our legality model disagrees with the
                # engine. Failing loudly keeps that visible instead of letting an
                # agent quietly play a different game.
                raise BridgeError(f"engine rejected a choice: {event.get('message')}")
            if event["type"] == "line":
                self._protocol.append(event["line"])
            if event["type"] == "request":
                self._pending.add(PLAYER_TAGS.index(event["player"]))
            for tracker in self._trackers:
                tracker.handle(event)

        for index, tracker in enumerate(self._trackers):
            if tracker.finished:
                names = {f"P{i + 1}": i for i in (0, 1)}
                self._winner = names.get(tracker.winner or "")
                break

        return StepResult(
            terminal=self.terminal,
            winner=self._winner,
            turn=self._trackers[0].observation().turn if self._started else 0,
            protocol=tuple(self._protocol),
        )
