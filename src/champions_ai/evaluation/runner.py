"""Play agents against each other and report whether a difference is real.

The point of this module is not to run battles -- `BattleEnv` does that -- but
to make a claim like "agent A beats agent B" defensible: enough battles, both
sides played from both positions, a stated interval, and a reproducible seed
(AGENTS.md, "Evaluation before claims").
"""

import math
from dataclasses import dataclass, field

from champions_ai.agents import Agent
from champions_ai.data import BattleTeam, TeamPool, Trajectory, utc_now
from champions_ai.env import BattleEnv, Decision, StepResult
from champions_ai.evaluation.margin import (
    BattleMargin,
    margin_from_sides,
    summarise,
)

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
    matchup: str = ""
    # How decisively it ended, from the first agent's point of view. None when
    # the battle stopped without a readable final state.
    margin: BattleMargin | None = None

    @property
    def first_agent_won(self) -> bool:
        return self.winner == self.first_agent_played_as

    @property
    def pokemon_margin(self) -> int:
        return self.margin.pokemon_margin if self.margin else 0

    @property
    def hp_margin(self) -> float:
        return self.margin.hp_margin if self.margin else 0.0


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
    # Per matchup, +1/-1/0 from agent A's perspective. Kept so a win rate can
    # be checked for resting on a handful of favourable team pairings.
    matchup_scores: dict[str, tuple[int, ...]] = field(default_factory=dict, repr=False)

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

    @property
    def pokemon_margin(self):
        """Mean surviving-Pokemon difference, with a confidence interval.

        Far more sensitive than the win rate on the same battles: a 4-0 and a
        4-3 are the same bit of win/loss evidence and very different results.
        """
        return summarise(
            f"{self.agent_a} vs {self.agent_b} pokemon margin",
            [o.pokemon_margin for o in self.outcomes if o.margin],
        )

    @property
    def hp_margin(self):
        """Mean surviving-HP difference, as a fraction of a full team."""
        return summarise(
            f"{self.agent_a} vs {self.agent_b} hp margin",
            [o.hp_margin for o in self.outcomes if o.margin],
        )

    @property
    def matchups_played(self) -> int:
        return len(self.matchup_scores)

    @property
    def matchups_won(self) -> int:
        """Matchups where agent A came out ahead across both team assignments."""
        return sum(1 for scores in self.matchup_scores.values() if sum(scores) > 0)

    @property
    def matchups_lost(self) -> int:
        return sum(1 for scores in self.matchup_scores.values() if sum(scores) < 0)

    @property
    def matchups_tied(self) -> int:
        """Matchups the two agents split, one team assignment each.

        With `common_seed` a tie is not a coincidence: the pair is identical but
        for which agent sits where, so a tie means the two policies produced the
        same result and the matchup carries no information about them.
        """
        return sum(1 for scores in self.matchup_scores.values() if sum(scores) == 0)

    @property
    def decided_matchups(self) -> int:
        """Matchups where the agents actually differed. **The sample size.**

        The pooled win rate counts every battle, but tied matchups contribute
        one win and one loss by construction and say nothing about either
        policy. This is what a comparison is really resting on, and it is
        routinely a small fraction of `battles` -- 21 of 798 in experiment 0033.
        """
        return self.matchups_won + self.matchups_lost

    @property
    def paired_win_rate(self) -> float:
        """Share of the decided matchups agent A took.

        The statistic to quote when `common_seed` is on. Ties are deterministic
        there, so the pooled rate is just `0.5 + (won - lost) / 2N` and a
        binomial interval on it is too wide.
        """
        decided = self.decided_matchups
        return self.matchups_won / decided if decided else 0.5

    @property
    def changed_nothing(self) -> bool:
        """Whether the two agents produced identical results everywhere.

        **Not a null.** Two agents that never once decided a matchup differently
        are, as far as this run can tell, the same agent -- which usually means
        the thing meant to differ between them did not. Experiment 0033 lost a
        sweep to a weight held in a module global that both sides read; every
        setting tied every matchup and it read exactly like a null result.
        """
        return self.matchups_played > 0 and self.decided_matchups == 0

    def summary(self) -> str:
        low, high = self.confidence_interval_a
        verdict = "significant" if self.is_significant else "not significant"
        margin = self.pokemon_margin
        margin_text = (
            f" | margin {margin.mean:+.2f} pokemon"
            f" ({'significant' if margin.is_significant else 'not significant'})"
            if margin.values
            else ""
        )
        return (
            f"{self.agent_a} vs {self.agent_b}: "
            f"{self.wins_a}-{self.wins_b}"
            + (f"-{self.draws}" if self.draws else "")
            + f" over {self.battles} battles | "
            f"win rate {self.win_rate_a:.1%} "
            f"(95% CI {low:.1%}-{high:.1%}, {verdict}) | "
            f"avg {self.average_turns:.1f} turns"
            + margin_text
            + (
                f" | ahead in {self.matchups_won}/{self.decided_matchups}"
                f" decided matchups ({self.matchups_tied} tied)"
                if self.matchup_scores
                else ""
            )
        )


def play_battle(
    env: BattleEnv,
    agents: tuple[Agent, Agent],
    teams: tuple[BattleTeam, BattleTeam],
    *,
    seed: str | None = None,
) -> StepResult:
    """Run one battle to completion, with `agents[i]` playing as player i."""
    for agent in agents:
        agent.on_battle_start()

    result = env.reset(teams, seed=seed)
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


class HarnessUnsound(AssertionError):
    """The measuring apparatus disagrees with itself."""


def check_mirror(env, make_agent, pool, *, battles: int = 60, seed: int = 0):
    """Play an agent against a copy of itself. Every matchup must tie.

    With `common_seed` the two passes of a matchup share their luck and differ
    only in which agent sits where, so two identical policies produce two
    identical battles and each wins exactly one pass. A tie is therefore not a
    tendency but an identity, and any decided matchup means the harness is
    measuring something other than the agents.

    This is the check that would have caught the bug 0031 found: `evaluate`
    swapped agents *and* teams, which cancels, so each agent kept its team and
    240 of 299 mirror matchups came out decided. It sat there for the life of
    the project because every test used a pool of two identical teams.

    Raises `HarnessUnsound` rather than returning a flag, because a caller who
    ignores this is measuring noise and should not get the chance.
    """
    result = evaluate(
        env, make_agent(), make_agent(), pool, battles=battles, seed=seed
    )
    if result.decided_matchups:
        raise HarnessUnsound(
            f"an agent played against a copy of itself and "
            f"{result.decided_matchups} of {result.matchups_played} matchups "
            f"came out decided ({result.matchups_won} ahead, "
            f"{result.matchups_lost} behind). With identical policies and a "
            f"shared seed every matchup must tie, so something other than the "
            f"agents is differing between the two passes."
        )
    return result


def evaluate(
    env: BattleEnv,
    agent_a: Agent,
    agent_b: Agent,
    pool: TeamPool,
    *,
    battles: int = 100,
    seed: int = 0,
    keep_trajectories: bool = False,
    common_seed: bool = True,
) -> MatchResult:
    """Play a head-to-head over a pool of matchups and summarise it.

    Every matchup is played **twice**, and the two passes exchange the agents
    while leaving the teams in place. That gives each agent both teams and both
    seats across the pair, so neither confound can be credited to it. `battles`
    is rounded up to an even number for that reason.

    Swapping the agents *and* the teams together, which this used to do, is not
    the same thing: the two swaps cancel and each agent keeps the team it
    started with. Only the seat was ever controlled. That is not biased -- over
    many matchups the team draw evens out -- but it is enormously noisy, and it
    is why this harness could not resolve small effects. Measured on the frozen
    pool, **85% of matchups are one-sided** with identical agents on both sides
    (one team wins 17 or more of 20), and **93% of the variance in outcomes is
    the matchup**. Leaving that uncontrolled put it all in the error bars.

    The invariant worth remembering: with the *same* agent on both sides, every
    matchup must tie. Before this fix, 240 of 299 did not.

    `common_seed` gives both passes of a matchup the same battle seed. Since the
    teams and seats are now identical between the two passes and only the agents
    swap, sharing the seed makes the pair differ in *nothing but the policies* --
    the same damage rolls, the same speed ties, the same everything. That is
    plain common random numbers, unbiased and much tighter, and it sharpens the
    invariant from "should tie" to "must tie": identical agents produce two
    identical battles, so one wins each pass by construction.

    Without it the two passes draw different luck, which is why identical agents
    still failed to tie 19% of matchups after the pairing was fixed.

    Battle seeds and matchup selection both derive from `seed`, so a whole run
    reproduces from one number.
    """
    if battles < 1:
        raise ValueError(f"battles must be positive, got {battles}")

    matchup_count = (battles + 1) // 2
    matchups = pool.matchups(matchup_count, seed=seed)

    outcomes: list[BattleOutcome] = []
    trajectories: list[Trajectory] = []
    wins_a = wins_b = draws = total_turns = 0
    per_matchup: dict[str, list[int]] = {}

    index = 0
    for pair, matchup in enumerate(matchups):
        for swapped in (False, True):
            # Pass 1: A is player 0 with the first team. Pass 2: the agents
            # swap and the teams stay put, so A now holds the second team from
            # the other seat. Across the pair each agent has played both teams
            # and sat in both seats.
            ordered = (agent_b, agent_a) if swapped else (agent_a, agent_b)
            teams = matchup.teams
            a_player = 1 if swapped else 0
            # With `common_seed` the pair shares its luck, so the two passes
            # differ only in which agent sits where. `pair` counts matchups
            # rather than battles for exactly that reason.
            stream = pair if common_seed else index
            battle_seed = f"sodium,{(seed * 1_000_003 + stream) % (2**256):064x}"

            result = play_battle(env, ordered, teams, seed=battle_seed)
            total_turns += result.turn

            # Read from each player's *own* side. An ObservedSide shows only
            # what was revealed, so counting an opponent's survivors from one
            # would silently miss anything they never sent out.
            try:
                margin = margin_from_sides(
                    env.tracker(a_player).own_side(),
                    env.tracker(1 - a_player).own_side(),
                )
            except RuntimeError:
                # No request seen -- the battle ended before a side was
                # readable. Recorded as absent rather than as a zero margin.
                margin = None

            if result.winner is None:
                draws += 1
                scored = 0
            elif result.winner == a_player:
                wins_a += 1
                scored = 1
            else:
                wins_b += 1
                scored = -1

            per_matchup.setdefault(matchup.label, []).append(scored)
            outcomes.append(
                BattleOutcome(
                    index=index,
                    seed=battle_seed,
                    first_agent_played_as=a_player,
                    winner=result.winner,
                    turns=result.turn,
                    matchup=matchup.label,
                    margin=margin,
                )
            )
            if keep_trajectories:
                trajectories.append(
                    env.trajectory(
                        metadata={
                            "agent_p1": ordered[0].name,
                            "agent_p2": ordered[1].name,
                            "matchup": matchup.label,
                        }
                    )
                )
            index += 1

    return MatchResult(
        agent_a=agent_a.name,
        agent_b=agent_b.name,
        battles=index,
        wins_a=wins_a,
        wins_b=wins_b,
        draws=draws,
        total_turns=total_turns,
        seed=seed,
        recorded_at=utc_now(),
        outcomes=tuple(outcomes),
        trajectories=tuple(trajectories),
        matchup_scores={label: tuple(scores) for label, scores in per_matchup.items()},
    )
