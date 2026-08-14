"""Play agents against each other and report whether a difference is real.

The point of this module is not to run battles -- `BattleEnv` does that -- but
to make a claim like "agent A beats agent B" defensible: enough battles, both
sides played from both positions, a stated interval, and a reproducible seed
(AGENTS.md, "Evaluation before claims").
"""

import math
from dataclasses import dataclass, field

from champions_ai.agents import Agent
from champions_ai.data import Trajectory, utc_now
from champions_ai.env import BattleEnv, Decision, StepResult

Z_95 = 1.959963984540054


def wilson_interval(successes: int, trials: int, z: float = Z_95) -> tuple[float, float]:
    """Wilson score interval for a proportion.

    Preferred over the normal approximation because it stays inside [0, 1] and
    remains sensible for small samples and extreme rates -- exactly the cases
    an early evaluation run produces, where the naive interval would suggest
    impossible win rates or a zero-width interval at 0% and 100%.
    """
    if trials < 0 or successes < 0:
        raise ValueError(f"counts must be non-negative, got {successes}/{trials}")
    if successes > trials:
        # Otherwise this fails deep inside a sqrt as a math domain error, which
        # says nothing about the miscounted result that caused it.
        raise ValueError(f"{successes} successes out of {trials} trials is impossible")
    if trials == 0:
        return (0.0, 1.0)
    proportion = successes / trials
    denominator = 1 + z**2 / trials
    centre = proportion + z**2 / (2 * trials)
    spread = z * math.sqrt(proportion * (1 - proportion) / trials + z**2 / (4 * trials**2))
    return (
        max(0.0, (centre - spread) / denominator),
        min(1.0, (centre + spread) / denominator),
    )


@dataclass(frozen=True)
class BattleOutcome:
    """One battle, from the perspective of the first agent."""

    index: int
    seed: str
    first_agent_played_as: int
    winner: int | None
    turns: int

    @property
    def first_agent_won(self) -> bool:
        return self.winner == self.first_agent_played_as


@dataclass(frozen=True)
class MatchResult:
    """Aggregate of a head-to-head, with enough provenance to be reproduced."""

    agent_a: str
    agent_b: str
    battles: int
    wins_a: int
    wins_b: int
    draws: int
    total_turns: int
    seed: int
    recorded_at: str
    outcomes: tuple[BattleOutcome, ...] = field(default=(), repr=False)
    trajectories: tuple[Trajectory, ...] = field(default=(), repr=False)

    @property
    def win_rate_a(self) -> float:
        """Draws count as neither side's win, so this is wins over all battles."""
        return self.wins_a / self.battles if self.battles else 0.0

    @property
    def confidence_interval_a(self) -> tuple[float, float]:
        return wilson_interval(self.wins_a, self.battles)

    @property
    def average_turns(self) -> float:
        return self.total_turns / self.battles if self.battles else 0.0

    @property
    def is_significant(self) -> bool:
        """Whether the interval excludes a coin flip.

        Deliberately conservative: overlapping 0.5 means the run does not
        support a claim either way, not that the agents are equal.
        """
        low, high = self.confidence_interval_a
        return low > 0.5 or high < 0.5

    def summary(self) -> str:
        low, high = self.confidence_interval_a
        verdict = "significant" if self.is_significant else "not significant"
        return (
            f"{self.agent_a} vs {self.agent_b}: "
            f"{self.wins_a}-{self.wins_b}"
            + (f"-{self.draws}" if self.draws else "")
            + f" over {self.battles} battles | "
            f"win rate {self.win_rate_a:.1%} "
            f"(95% CI {low:.1%}-{high:.1%}, {verdict}) | "
            f"avg {self.average_turns:.1f} turns"
        )


def play_battle(
    env: BattleEnv,
    agents: tuple[Agent, Agent],
    packed_teams: tuple[str, str],
    *,
    seed: str | None = None,
) -> StepResult:
    """Run one battle to completion, with `agents[i]` playing as player i."""
    for agent in agents:
        agent.on_battle_start()

    result = env.reset(packed_teams, seed=seed)
    while not result.terminal:
        waiting = env.awaiting()
        if not waiting:
            break
        choices = {}
        for player in waiting:
            agent = agents[player]
            if env.decision(player) is Decision.TEAM_PREVIEW:
                choices[player] = agent.select_team_preview(
                    env.team_preview(player), env.regulation.picked_team_size
                )
            else:
                choices[player] = agent.select_action(
                    env.observation(player), env.legal_actions(player)
                )
        result = env.step(choices)
    return result


def evaluate(
    env: BattleEnv,
    agent_a: Agent,
    agent_b: Agent,
    packed_teams: tuple[str, str],
    *,
    battles: int = 100,
    seed: int = 0,
    keep_trajectories: bool = False,
) -> MatchResult:
    """Play a head-to-head and summarise it.

    Sides are swapped every other battle so a first-player or team-order
    advantage cancels out instead of being attributed to an agent. Battle seeds
    are derived from `seed`, so a whole run reproduces from one number.
    """
    if battles < 1:
        raise ValueError(f"battles must be positive, got {battles}")

    outcomes: list[BattleOutcome] = []
    trajectories: list[Trajectory] = []
    wins_a = wins_b = draws = total_turns = 0

    for index in range(battles):
        a_is_player_one = index % 2 == 0
        ordered = (agent_a, agent_b) if a_is_player_one else (agent_b, agent_a)
        a_player = 0 if a_is_player_one else 1
        battle_seed = f"sodium,{(seed * 1_000_003 + index) % (2**256):064x}"

        result = play_battle(env, ordered, packed_teams, seed=battle_seed)
        total_turns += result.turn

        if result.winner is None:
            draws += 1
        elif result.winner == a_player:
            wins_a += 1
        else:
            wins_b += 1

        outcomes.append(
            BattleOutcome(
                index=index,
                seed=battle_seed,
                first_agent_played_as=a_player,
                winner=result.winner,
                turns=result.turn,
            )
        )
        if keep_trajectories:
            trajectories.append(
                env.trajectory(metadata={"agent_p1": ordered[0].name, "agent_p2": ordered[1].name})
            )

    return MatchResult(
        agent_a=agent_a.name,
        agent_b=agent_b.name,
        battles=battles,
        wins_a=wins_a,
        wins_b=wins_b,
        draws=draws,
        total_turns=total_turns,
        seed=seed,
        recorded_at=utc_now(),
        outcomes=tuple(outcomes),
        trajectories=tuple(trajectories),
    )
