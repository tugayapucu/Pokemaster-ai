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
from collections import Counter, defaultdict
from pathlib import Path

from champions_ai.agents import HeuristicAgent
from champions_ai.cli.board import render_board
from champions_ai.data import load_all
from champions_ai.data.reconstruct import move_data_from_dex, reconstruct_decisions
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_B, legal_joint_actions
from champions_ai.evaluation.agreement import (
    action_signature,
    human_signature,
    target_unobservable,
)
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


def _rank_of(signature, advice, observation, move_data, *, move_only: bool = False) -> int | None:
    """Where the human's action sits in our ranking, if it appears at all.

    Answering "did the agent agree" with yes or no throws away the interesting
    middle: an action ranked second is a different kind of disagreement from
    one the adviser never considered.

    `move_only` compares the move and ignores the target, for the case the log
    genuinely cannot answer -- a move that failed or is mid-charge prints no
    target at all, and the player certainly picked one.
    """
    trim = (lambda s: None if s is None else s[:2]) if move_only else (lambda s: s)
    wanted = trim(signature)
    for entry in advice.recommendations:
        for slot, slot_action in enumerate(entry.action.slot_actions):
            if trim(action_signature(slot_action, observation, slot, move_data)) == wanted:
                return entry.rank
    return None


def _signature_name(signature, dex) -> str:
    """A comparable action, spelled for a human."""
    if signature[0] == "switch":
        return f"switch to {_species(dex, signature[1])}"
    try:
        return dex.get_move(signature[1]).name
    except KeyError:
        return signature[1]


def _species(dex, species: str) -> str:
    try:
        return dex.get_species(species).name
    except KeyError:
        return species


def survey(
    *,
    corpus_path: Path = DEFAULT_CORPUS,
    replay_limit: int = 0,
    minimum: int = 40,
) -> int:
    """Where do we and rated players systematically differ, across the corpus?

    One game tells you whether the adviser is sane. The corpus tells you what
    it is *habitually* wrong about, or -- since agreement is not truth here --
    what it habitually does differently. Those are the two lists at the end:
    actions humans keep taking that we rank low, and actions we keep
    recommending that humans do not play.
    """
    if not corpus_path.exists():
        print(f"No replay corpus at {corpus_path}. Collect one with data/collect.py.")
        return 2

    corpus = load_all(corpus_path)
    replays = list(corpus.replays)
    if replay_limit:
        replays = replays[:replay_limit]
    if not replays:
        print(f"No replays found under {corpus_path}.")
        return 2

    ranks: Counter = Counter()
    by_kind: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    theirs: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
    ours: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
    switch_by_known: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    failed = unscorable = target_only = hidden_target = 0

    with ShowdownBridge() as bridge:
        dex = Dex.cached(bridge, DEFAULT_DEX)
        move_data = move_data_from_dex(dex)
        recommender = Recommender(dex, agent=HeuristicAgent(dex, name="adviser"))

        print(f"  Walking {len(replays)} replays...", flush=True)
        for number, replay in enumerate(replays, 1):
            if number % 400 == 0:
                print(f"    {number}...", flush=True)
            try:
                decisions = reconstruct_decisions(replay, REGULATION_M_B, dex)
            except Exception:
                failed += 1
                continue

            for decision in decisions:
                if not decision.is_free_choice:
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
                best = advice.best.action
                for choice in decision.choices:
                    signature = human_signature(choice, move_data)
                    if signature is None:
                        unscorable += 1
                        continue
                    # A move that failed or is mid-charge prints no target,
                    # so `('move', 'electroshot', None)` could never match our
                    # `('move', 'electroshot', ('foe', 0))`. Comparing those on
                    # the full signature reported every charge move in the
                    # format as a total disagreement, in both directions.
                    move_only = target_unobservable(choice, move_data)
                    if move_only:
                        hidden_target += 1
                    rank = _rank_of(
                        signature, advice, observation, move_data, move_only=move_only
                    )
                    agreed = rank == 1
                    ranks[rank] += 1
                    by_kind[signature[0]][1] += 1
                    by_kind[signature[0]][0] += int(agreed)
                    # Grouped by move rather than by move-and-target, because
                    # the same move aimed two ways is one thing to a reader and
                    # the target is tracked separately below.
                    theirs[signature[:2]][1] += 1
                    theirs[signature[:2]][0] += int(agreed)

                    if choice.slot < len(best.slot_actions):
                        mine = action_signature(
                            best.slot_actions[choice.slot], observation, choice.slot, move_data
                        )
                        index = observation.own_side.active_slots[choice.slot]
                        if index is not None and index < len(decision.known_move_counts):
                            known = min(decision.known_move_counts[index], 4)
                            switch_by_known[known][1] += 1
                            switch_by_known[known][0] += int(mine is not None
                                                             and mine[0] == "switch")
                        if mine is not None and mine[0] != "pass":
                            ours[mine[:2]][1] += 1
                            ours[mine[:2]][0] += int(
                                mine[:2] == signature[:2] if move_only else mine == signature
                            )
                            # 0013 measured humans as near-random on target
                            # selection, so a disagreement that is only about
                            # where the same move points is a different and
                            # much weaker finding than a different move.
                            if not agreed and mine[:2] == signature[:2]:
                                target_only += 1

        total = sum(ranks.values())
        if not total:
            print("  Nothing comparable was found.")
            return 1

        print(f"\n  {len(replays)} replays, {total} slot decisions compared\n")
        print("  Where the human's action sat in our shortlist")
        for rank in (1, 2, 3, 4):
            count = ranks.get(rank, 0)
            label = "our #1 (we agree)" if rank == 1 else f"our #{rank}"
            print(f"    {label:<22} {count / total:>6.1%}   n={count}")
        outside = ranks.get(None, 0)
        print(f"    {'outside the top 4':<22} {outside / total:>6.1%}   n={outside}")

        print("\n  By what they did")
        for kind in sorted(by_kind):
            agreed, count = by_kind[kind]
            print(f"    {kind:<22} {agreed / count:>6.1%} agreed   n={count}")

        if hidden_target:
            print(
                f"\n  {hidden_target} were compared on the move alone: a move that failed"
            )
            print(
                "  or is mid-charge prints no target, so the player certainly chose one\n"
                "  and the log does not say which."
            )

        disagreed = total - ranks.get(1, 0)
        if disagreed:
            print(
                f"\n  Of the {disagreed} we did not match, {target_only} "
                f"({target_only / disagreed:.0%}) were the same move aimed elsewhere."
            )
            print(
                "  0013 measured humans as near-random on target choice, so those are\n"
                "  the weakest disagreements on this page."
            )

        print(f"\n  What they keep playing that we rank low  (>= {minimum} times)")
        print(f"    {'action':<28} {'played':>7} {'we agreed':>10}")
        ranked = [
            (agreed / count, count, signature)
            for signature, (agreed, count) in theirs.items()
            if count >= minimum
        ]
        for rate, count, signature in sorted(ranked)[:12]:
            print(f"    {_signature_name(signature, dex):<28} {count:>7} {rate:>9.0%}")

        print(f"\n  What we keep recommending that they do not play  (>= {minimum} times)")
        print(f"    {'action':<28} {'we said':>7} {'they did':>10}")
        mine_ranked = [
            (matched / count, count, signature)
            for signature, (matched, count) in ours.items()
            if count >= minimum
        ]
        for rate, count, signature in sorted(mine_ranked)[:12]:
            print(f"    {_signature_name(signature, dex):<28} {count:>7} {rate:>9.0%}")

        if switch_by_known:
            print("\n  Read the switch rows above with this in mind:")
            print(f"    {'moves we know':<16} {'decisions':>10} {'we switch':>11}")
            for known in sorted(switch_by_known):
                switched, count = switch_by_known[known]
                print(f"    {known:<16} {count:>10} {switched / count:>10.1%}")
            print(
                "\n  A replay only reveals the moves a Pokemon was seen using, so the\n"
                "  adviser judges most positions from a partial moveset -- and a Pokemon\n"
                "  whose moves are unknown looks like it can do nothing, which makes\n"
                "  switching away from it look good. That is the instrument, not a\n"
                "  finding: with all four moves known we switch less often than the\n"
                "  11.8% rate 0027 measured for humans."
            )

        if failed or unscorable:
            print(
                f"\n  {failed} replays could not be reconstructed and {unscorable} slot\n"
                "  decisions could not be compared. A replay only reveals moves that\n"
                "  were used, so some actions the human had are not reconstructable."
            )
        print(
            "\n  Agreement is not truth. The corpus is 1500-1850 Elo, and matching it\n"
            "  has twice been the wrong target (0010, 0013). This is a map of where we\n"
            "  differ, not a scoreboard."
        )
        return 0


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
                # The cost, not the confidence: the confidence is a softmax
                # share with an unswept temperature, the cost is measured.
                note = (
                    "top choice"
                    if entry.rank == 1
                    else (str(entry.cost) if entry.cost is not None else "not measured")
                )
                print(f"    {entry.rank}. {entry.description}")
                print(f"         {note}")
                for reason in entry.reasons[:2]:
                    print(f"         - {reason}")

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
