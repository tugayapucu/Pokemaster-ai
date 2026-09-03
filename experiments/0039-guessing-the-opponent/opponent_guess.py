"""Guess the opponent's move from only what is publicly visible about them.

0038's search was hooked up with a cheat: `opponent = probe[1].select_action(
env.observation(1), env.legal_actions(1))` computes player 1's *true*
simultaneous choice, because `observation(1)` and `legal_actions(1)` are
legitimately full-information from player 1's own side of the table. That is
not a leak of anything player 1 should keep secret -- but a real search, run
by player 0 before both choices are submitted, cannot see player 1's choice at
all. It has to guess.

This builds that guess using only `observation(0).opponent_side` -- species,
HP%, boosts, status, and *revealed* moves -- which is exactly the information
`HeuristicAgent._threat_from` already reasons from when the agent judges
incoming danger to itself. The guess never sees player 1's true selectable
moves, true stats, PP, or held item unless revealed.

**One deliberate leak, stated rather than hidden.** Submitting a guess to the
engine requires a *real, legal* choice string, and only player 1's true
request lists real move indices and PP. So player 1's true legal actions are
consulted, but only to translate a guess already made from public data into a
submittable action -- by checking whether the guessed move's name matches a
move the true request actually offers, never by using the true request's
damage numbers to *choose* the guess. When a slot has no revealed damaging
move at all, no public information distinguishes one true option from
another, and the fallback is a fixed rule (their first offered attack) rather
than a peek at which option is strongest.

Switches are not modelled: the guess only ever predicts an attack, which is
the same simplification the retired `SearchAgent._threats` made.

**And a slot with nothing revealed gets no opinion at all.** An earlier draft
intended to fall back on `assumed_attacks` -- a standard STAB attack off their
public typing -- and never did; the slot is simply skipped and the fixed
default takes it. That is what 0039 measured, so it is left alone here rather
than quietly improved after the fact. It is also the largest known weakness:
63% of decision points have at least one active slot the guesser says nothing
about.
"""

from champions_ai.domain import JointAction, MoveAction
from champions_ai.mechanics import attacking_side, estimate_damage, estimate_stats

ASSUMED_OPPONENT_POINTS = 12


def _our_targets(observation):
    """Our own active Pokemon, fully known to us -- legitimate to use."""
    out = []
    for slot, index in enumerate(observation.own_side.active_slots):
        if index is None:
            continue
        mon = observation.own_side.team[index]
        if not mon.fainted:
            out.append((slot, mon))
    return out


def _public_guess(dex, observation):
    """Per opponent active slot: (guessed move id, our target slot), or None.

    None means nothing revealed distinguishes their options -- there is
    genuinely no public basis for a guess at that slot.
    """
    guess = {}
    targets = _our_targets(observation)
    for slot, index in enumerate(observation.opponent_side.active_slots):
        if index is None:
            continue
        observed = observation.opponent_side.revealed[index]
        if observed.fainted or not targets:
            continue
        try:
            species = dex.get_species(observed.species)
        except KeyError:
            continue

        revealed = []
        for move_id in observed.revealed_moves:
            try:
                move = dex.get_move(move_id)
            except KeyError:
                continue
            if move.is_damaging:
                revealed.append(move)
        if not revealed:
            continue

        attack_stats = estimate_stats(species.base_stats, ASSUMED_OPPONENT_POINTS)
        best = None
        for move in revealed:
            for target_slot, mon in targets:
                swinging = attacking_side(
                    move, user=attack_stats, target=mon.computed_stats or {}
                )
                try:
                    defender_species = dex.get_species(mon.pokemon_set.species)
                except KeyError:
                    continue
                estimate = estimate_damage(
                    dex,
                    move,
                    attacker=species,
                    attack_stat=swinging.get(move.offensive_stat, 100),
                    defender=defender_species,
                    defense_stat=(mon.computed_stats or {}).get(move.defensive_stat, 100),
                    defender_hp=max(1, mon.current_hp),
                    level=observation.regulation.level,
                    doubles=observation.regulation.game_type == "doubles",
                    weather=observation.weather,
                )
                expected = estimate.average_fraction * move.hit_chance
                if best is None or expected > best[0]:
                    best = (expected, move.move_id, target_slot)
        if best is not None:
            guess[slot] = (best[1], best[2])
    return guess


def guess_opponent_action(dex, env, observation0) -> JointAction:
    """A submittable action for player 1, guessed from player 0's public view.

    `env` is used only as plumbing to reach player 1's true legal actions and
    move names -- required to produce something the engine will accept, never
    to inform *which* action is guessed.
    """
    guess = _public_guess(dex, observation0)
    legal = env.legal_actions(1)
    if not legal:
        raise ValueError("player 1 has no legal actions to guess among")

    true_observation = env.observation(1)
    active_team_index = true_observation.own_side.active_slots
    move_names_by_slot: dict[int, list[str]] = {}
    for slot, team_index in enumerate(active_team_index):
        if team_index is not None:
            move_names_by_slot[slot] = list(
                true_observation.own_side.team[team_index].selectable_moves
            )

    def resolved_name(slot: int, action) -> str | None:
        if not isinstance(action, MoveAction):
            return None
        names = move_names_by_slot.get(slot)
        if names is None or action.move_index >= len(names):
            return None
        return names[action.move_index]

    def matches(slot: int, action, wanted_name: str, wanted_target: int) -> bool:
        if resolved_name(slot, action) != wanted_name:
            return False
        if action.target is None:
            return True  # a move with no target concept cannot disagree
        return action.target.side == "foe" and action.target.slot == wanted_target

    best_joint, best_score = None, -1
    for joint in legal:
        score = sum(
            1
            for slot, (name, target) in guess.items()
            if slot < len(joint.slot_actions)
            and matches(slot, joint.slot_actions[slot], name, target)
        )
        if score > best_score:
            best_joint, best_score = joint, score

    if best_score > 0:
        return best_joint

    # Nothing revealed matched anything currently offered. Fixed default:
    # the first legal joint action that attacks with at least one slot,
    # rather than passing or switching -- not chosen by its own strength.
    for joint in legal:
        if any(isinstance(a, MoveAction) for a in joint.slot_actions):
            return joint
    return legal[0]
