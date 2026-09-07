"""A battle position typed in by a person, rather than produced by the engine.

The project can play a battle and review a replay, and neither helps during a
real game of Pokemon Champions: the game has no replay export, no battle
history and no share link, so there is nothing to feed the replay pipeline.
What a player does have is the screen in front of them.

So this is the other direction -- a position described by hand, turned into the
same `Observation` every other part of the project consumes, and handed to the
same `Recommender`. Nothing here reads, drives or inspects the game client
(`AGENTS.md` section 3); a person reads their own screen and types.
"""

from champions_ai.position.state import THEM, US, Position, Target

__all__ = ["Position", "Target", "THEM", "US"]
