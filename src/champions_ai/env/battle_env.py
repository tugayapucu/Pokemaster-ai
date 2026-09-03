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

from champions_ai.data import BattleTeam, DecisionRecord, Trajectory, git_commit, utc_now
from champions_ai.domain import (
    JointAction,
    Observation,
    PassAction,
    Regulation,
    SlotAction,
    SwitchAction,
    TeamPreview,
    TeamPreviewAction,
    legal_joint_actions,
    legal_switch_actions,
)
from champions_ai.simulator import (
    BattleTracker,
    BridgeError,
    ShowdownBridge,
    format_joint_action,
    format_team_preview,
)

# Showdown distinguishes a choice that was never legal from one that was
# legal until the engine updated its own request. Only the first is a bug
# on our side; the second is answered by choosing again.
UNAVAILABLE_CHOICE = "[Unavailable choice]"

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
        *,
        bridge: ShowdownBridge | None = None,
    ) -> None:
        self.regulation = regulation
        self.teams: tuple[BattleTeam, BattleTeam] | None = None
        self._bridge = bridge or ShowdownBridge()
        self._owns_bridge = bridge is None
        self._trackers: tuple[BattleTracker, ...] = ()
        self._protocol: list[str] = []
        self._winner: int | None = None
        self._started = False
        self._pending: set[int] = set()
        self._decisions: list[DecisionRecord] = []
        self._seed: str | None = None
        self._packed: tuple[str, str] = ("", "")
        self._last_legal_counts: dict[int, int] = {}
        self._stale_requests = 0

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

    def reset(
        self, teams: tuple[BattleTeam, BattleTeam], *, seed: str | None = None
    ) -> StepResult:
        """Start a battle between two prepared teams.

        Teams are given per battle rather than at construction so one
        environment can run a whole pool of matchups.
        """
        self.teams = teams
        packed_teams = (teams[0].packed, teams[1].packed)
        self._trackers = tuple(
            BattleTracker(self.regulation, player=index, own_team=teams[index].team)
            for index in (0, 1)
        )
        self._protocol = []
        self._winner = None
        self._started = True
        self._pending = set()
        self._decisions = []
        self._seed = seed
        self._packed = packed_teams

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

    def team_preview(self, player: int) -> TeamPreview:
        """Both rosters as this player sees them. Only valid before the battle starts."""
        return self.tracker(player).team_preview()

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
            actions = legal_joint_actions(observation, move_data)
        else:
            actions = self._forced_switch_actions(
                observation, tracker.force_switch_slots, move_data
            )
        # Remembered so a recorded decision can say how many options the agent
        # was choosing between, without recomputing them.
        self._last_legal_counts[player] = len(actions)
        return actions

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
                for action in legal_switch_actions(observation, slot)
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

        self._require_started()
        assert self.teams is not None
        size = len(self.teams[player].team)
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

        turn = self.turn
        rendered = []
        for player, action in sorted(actions.items()):
            # Render before submitting: _render reads the current decision,
            # which the engine's response would otherwise have moved on from.
            rendered.append((player, action, self._render(player, action)))
            self._decisions.append(
                DecisionRecord(
                    turn=turn,
                    player=player,
                    action=action,
                    legal_action_count=self._last_legal_counts.get(player),
                )
            )

        events: list[dict] = []
        for player, _, choice in rendered:
            events.extend(self._bridge.choose(PLAYER_TAGS[player], choice))
        self._last_legal_counts = {}
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

    def trajectory(
        self,
        *,
        include_protocol: bool = False,
        metadata: dict[str, str] | None = None,
    ) -> Trajectory:
        """Record this battle as what it takes to reproduce it.

        Observations are deliberately absent: replaying the seed regenerates
        them, and doing so with current code beats preserving whatever the
        recording version happened to produce.
        """
        self._require_started()
        return Trajectory(
            format_id=self.regulation.format_id,
            seed=self._seed,
            packed_teams=self._packed,
            decisions=tuple(self._decisions),
            winner=self._winner,
            turns=self.turn,
            recorded_at=utc_now(),
            git_commit=git_commit(),
            metadata=metadata or {},
            protocol=self.protocol if include_protocol else (),
        )

    def reseed(self, seed: str) -> str:
        """Replace the running battle's random number generator.

        Only meaningful mid-battle. Replaying a seed and a recording reproduces
        a position exactly, which is what makes a fork exact -- and also what
        would make every continuation of it identical. Reseeding here is what
        turns one reproduced position into a sample of what could follow.
        """
        self._require_started()
        return self._bridge.reseed(seed)

    def replay(
        self,
        trajectory: Trajectory,
        teams: tuple[BattleTeam, BattleTeam],
        *,
        stop_after: int | None = None,
    ) -> StepResult:
        """Re-run a recorded battle by resubmitting its decisions.

        Raises if the recording cannot drive the battle -- a decision arriving
        for a player the engine is not asking, or the choices running out
        early, means the record and the current code disagree, which is worth
        failing on rather than papering over.

        `stop_after` replays only that many *steps* and leaves the battle
        running mid-game, which is how a position gets reproduced in order to
        branch from it. A step is one exchange with the engine, so it consumes
        a decision for each player the engine is currently waiting on -- not
        one record. Running out of recorded decisions is an error only when
        replaying the whole thing; stopping early is the point here.
        """
        if not trajectory.replayable:
            raise ValueError("trajectory has no seed and cannot be reproduced")
        recorded = (teams[0].packed, teams[1].packed)
        if recorded != trajectory.packed_teams:
            raise ValueError(
                "teams do not match the recording; replaying different teams under the "
                "recorded seed would silently produce a different battle"
            )

        result = self.reset(teams, seed=trajectory.seed)
        queued = list(trajectory.decisions)
        steps = 0

        while not result.terminal:
            if stop_after is not None and steps >= stop_after:
                break
            waiting = self.awaiting()
            if not waiting:
                break
            actions: dict[int, JointAction | TeamPreviewAction] = {}
            for player in waiting:
                match = next((d for d in queued if d.player == player), None)
                if match is None:
                    raise ValueError(f"trajectory ran out of decisions for player {player}")
                queued.remove(match)
                actions[player] = match.action
            result = self.step(actions)
            steps += 1

        return result

    @property
    def stale_requests(self) -> int:
        """How often the engine corrected a superseded request and re-asked.

        Not an error, but not nothing either: a rise here means our view of
        what is choosable is drifting from the engine's more often.
        """
        return self._stale_requests

    def _absorb(self, events: list[dict]) -> StepResult:
        self._pending = set()
        for event in events:
            if event["type"] == "error":
                message = str(event.get("message") or "")
                if message.startswith(UNAVAILABLE_CHOICE):
                    # Not a rejection. `Side.emitChoiceError` marks an error
                    # "Unavailable" only when `updateRequestForPokemon` changed
                    # the request -- the engine noticed its own request was
                    # stale, corrected it, and re-emitted it:
                    #
                    #     const updated = update ? this.updateRequestForPokemon(...) : null;
                    #     const type = `[${updated ? 'Unavailable' : 'Invalid'} choice]`;
                    #     if (updated) this.emitRequest(this.activeRequest!, true);
                    #
                    # Showdown's own reference agent ignores these for exactly
                    # that reason. The corrected request arrives in this same
                    # batch and puts the player back in `_pending`, so the
                    # caller simply chooses again against the fixed view.
                    #
                    # Every instance seen here was a move the engine had newly
                    # disabled -- `updateDisabledRequest` is one of the two
                    # callers -- which is why it read as a legality bug and
                    # survived two fixes aimed at legality.
                    self._stale_requests += 1
                    continue
                # An *invalid* choice is the real thing: our legality model
                # disagrees with the engine. Failing loudly keeps that visible
                # instead of letting an agent quietly play a different game.
                raise BridgeError(f"engine rejected a choice: {message}")
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
