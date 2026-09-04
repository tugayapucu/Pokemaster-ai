"""Walk a real game and put the engine's advice next to what a human did.

`play` answers "what should I do here" on a position the agent made up.
Everything it shows comes from self-play, and 0026 established that self-play
cannot surface a mechanic the agent under-uses -- the opponent *is* our agent,
so anything it neglects is invisible. A replay contains decisions our agent
would never make.

**A disagreement is not a verdict.** The corpus is 1500-1850 Elo, and this
project has twice been misled by treating human agreement as truth: Trick
Room's fitted value climbed without bound because a team that brings it nearly
always uses it (0010), and target selection looked like the largest gap in the
project when humans themselves are near-random on it (0013). So this shows both
sides and the reasoning, and scores nobody.

Reconstruction is lossy in one direction worth stating plainly: a replay only
reveals the moves a Pokemon actually used, so the legal action set rebuilt here
is a subset of the real one. Where the human's own move was never otherwise
seen, the comparison is skipped rather than counted as a disagreement.
"""

import random
from pathlib import Path

from champions_ai.agents import HeuristicAgent
from champions_ai.cli.board import render_board
from champions_ai.data import load_all
from champions_ai.data.reconstruct import move_data_from_dex, reconstruct_decisions
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_B, legal_joint_actions
from champions_ai.evaluation.agreement import action_signature, human_signature
from champions_ai.recommendation import Recommender
from champions_ai.simulator import ShowdownBridge

DEFAULT_CORPUS = Path("data/replays")
DEFAULT_DEX = Path("data/dex.json")


def _actor(choice, observation) -> str:
    """Name the acting Pokemon by species, keeping its nickname alongside.

    The log only ever calls it by nickname, and "Try me" tells a reader
    nothing about which of four Pokemon acted. The slot resolves it, and the
    nickname is kept because that is what the replay shows.
    """
    slot = choice.slot
    if slot < len(observation.own_side.active_slots):
        index = observation.own_side.active_slots[slot]
        if index is not None:
            species = observation.own_side.team[index].pokemon_set.species
            return species if species.lower() == choice.actor.lower() else (
                f"{species} ({choice.actor})"
            )
    return choice.actor


def _target(raw: str | None) -> str:
    """`p2b: Staraptor` is protocol. A reader wants the name."""
    if not raw:
        return ""
    return raw.split(": ", 1)[1] if ": " in raw else raw


def _describe_human(choice, dex) -> str:
    """What the player actually pressed, in the same words the adviser uses."""
    if choice.kind == "switch" and choice.switched_to:
        return f"switch to {_target(choice.switched_to)}"
    if choice.kind == "move" and choice.move:
        name = choice.move
        try:
            name = dex.get_move(choice.move.replace(" ", "").replace("-", "").lower()).name
        except KeyError:
            pass
        target = _target(choice.target)
        # A move aimed at its own user reads as "Tailwind -> After Me", which
        # is the log being literal rather than anything a reader needs.
        if target and target.lower() == choice.actor.lower():
            target = ""
        return f"{name}{' -> ' + target if target else ''}"
    return choice.kind


def _rank_of(signature, advice, observation, move_data) -> int | None:
    """Where the human's action sits in our ranking, if it appears at all.

    Answering "did the agent agree" with yes or no throws away the interesting
    middle: an action ranked second is a different kind of disagreement from
    one the adviser never considered.
    """
    for entry in advice.recommendations:
        for slot, slot_action in enumerate(entry.action.slot_actions):
            if action_signature(slot_action, observation, slot, move_data) == signature:
                return entry.rank
    return None


def review(
    *,
    corpus_path: Path = DEFAULT_CORPUS,
    replay_id: str | None = None,
    player: int = 0,
    disagreements_only: bool = False,
    limit: int = 0,
    seed: int | None = None,
) -> int:
    """Walk one replay's decisions for one player. Returns a process exit code."""
    if not corpus_path.exists():
        print(
            f"No replay corpus at {corpus_path}.\n"
            "  Collect one locally with data/collect.py. The logs carry no licence,\n"
            "  so the corpus is never committed and never redistributed."
        )
        return 2

    corpus = load_all(corpus_path)
    replays = list(corpus.replays)
    if not replays:
        print(f"No replays found under {corpus_path}.")
        return 2

    if replay_id is not None:
        chosen = next((r for r in replays if replay_id in r.metadata.replay_id), None)
        if chosen is None:
            print(f"No replay matching {replay_id!r} among {len(replays)}.")
            return 2
    else:
        chosen = random.Random(seed).choice(replays)

    with ShowdownBridge() as bridge:
        dex = Dex.cached(bridge, DEFAULT_DEX)
        move_data = move_data_from_dex(dex)
        recommender = Recommender(dex, agent=HeuristicAgent(dex, name="adviser"))

        try:
            decisions = reconstruct_decisions(chosen, REGULATION_M_B, dex)
        except Exception as error:
            print(f"Could not reconstruct {chosen.metadata.replay_id}: {error}")
            return 1

        players = list(chosen.metadata.players)
        name = players[player] if player < len(players) else f"player {player}"
        print(f"\n  Replay {chosen.metadata.replay_id}")
        print(f"  {' vs '.join(players)}")
        print(f"  Following {name}, and the winner was {chosen.winner or 'not recorded'}.")

        shown = agreed = disagreed = unscorable = skipped = 0
        for decision in decisions:
            if decision.player != player:
                continue
            if not decision.is_free_choice:
                # Leads and forced replacements are decisions, but different
                # ones, and lumping them in would measure a mixture of three
                # policies (see `data/choices.py`). Counted so the reader knows
                # the walk is not showing every turn.
                skipped += 1
                continue
            observation = decision.observation
            try:
                legal = legal_joint_actions(observation, move_data)
            except KeyError:
                unscorable += len(decision.choices)
                continue
            if not legal:
                continue

            advice = recommender.recommend(observation, legal)
            lines = []
            turn_agreed = True
            for choice in decision.choices:
                signature = human_signature(choice, move_data)
                if signature is None:
                    unscorable += 1
                    continue
                rank = _rank_of(signature, advice, observation, move_data)
                if rank == 1:
                    verdict = "agrees"
                elif rank is not None:
                    verdict = f"our #{rank}"
                    turn_agreed = False
                else:
                    verdict = "not in our shortlist"
                    turn_agreed = False
                lines.append(
                    f"    {_actor(choice, observation)}: "
                    f"{_describe_human(choice, dex)}   [{verdict}]"
                )

            if not lines:
                continue
            if turn_agreed:
                agreed += 1
                if disagreements_only:
                    continue
            else:
                disagreed += 1

            print()
            print(render_board(observation))
            print(f"\n  They played, turn {decision.turn}:")
            for line in lines:
                print(line)
            print("\n  We would advise:")
            for entry in advice.recommendations[:3]:
                print(f"    {entry.rank}. {entry.description}   {entry.confidence:.0%}")
                for reason in entry.reasons[:2]:
                    print(f"         - {reason}")
            if not advice.is_clear:
                print("    (close call: the top two are hard to separate)")

            shown += 1
            if limit and shown >= limit:
                print(f"\n  ... stopping at {limit} positions (--limit).")
                break

        print()
        total = agreed + disagreed
        turns = "turn" if total == 1 else "turns"
        print(
            f"  {total} {turns} compared: our top pick matched on {agreed}, "
            f"differed on {disagreed}."
        )
        if skipped:
            print(
                f"  {skipped} not compared: a Team Preview lead or a forced replacement\n"
                "  after a faint is a real decision, but a different one."
            )
        if unscorable:
            print(
                f"  {unscorable} slot decisions could not be compared -- a replay only\n"
                "  reveals moves that were used, so some the human had are not "
                "reconstructable."
            )
        print(
            "\n  A disagreement is not a verdict. The corpus is 1500-1850 Elo, and\n"
            "  agreement has twice been the wrong target here (0010, 0013)."
        )
        return 0
