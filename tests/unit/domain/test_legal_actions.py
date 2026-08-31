import pytest

from champions_ai.domain import (
    REGULATION_M_B,
    BattlePokemon,
    BattleState,
    MoveAction,
    MoveData,
    Observation,
    PassAction,
    PokemonSet,
    Side,
    SwitchAction,
    legal_joint_actions,
    legal_slot_actions,
    legal_switch_actions,
)

MOVES = {
    "tackle": MoveData(move_id="tackle", target="normal"),
    "earthquake": MoveData(move_id="earthquake", target="allAdjacent"),
    "protect": MoveData(move_id="protect", target="self"),
    "helpinghand": MoveData(move_id="helpinghand", target="adjacentAlly"),
    "heatwave": MoveData(move_id="heatwave", target="allAdjacentFoes"),
}


def _mon(species: str, moves: tuple[str, ...] = ("tackle", "protect"), **overrides):
    defaults = dict(
        pokemon_set=PokemonSet(species=species, level=50, ability="a", moves=moves),
        current_hp=100,
        max_hp=100,
        has_been_active=True,
    )
    return BattlePokemon(**{**defaults, **overrides})


def _observation(own: Side, opponent: Side | None = None, player: int = 0) -> Observation:
    opponent = opponent or Side(team=tuple(_mon(f"foe{i}") for i in range(4)), active_slots=(0, 1))
    sides = (own, opponent) if player == 0 else (opponent, own)
    state = BattleState(regulation=REGULATION_M_B, turn=1, sides=sides)
    return Observation.from_battle_state(state, player=player)


def _own_side(**overrides) -> Side:
    defaults = dict(
        team=tuple(_mon(f"own{i}") for i in range(4)),
        active_slots=(0, 1),
    )
    return Side(**{**defaults, **overrides})


def test_normal_move_offers_every_live_target_including_the_ally():
    obs = _observation(_own_side())
    actions = legal_slot_actions(obs, 0, MOVES)
    tackle_targets = {
        (a.target.side, a.target.slot)
        for a in actions
        if isinstance(a, MoveAction) and a.move_index == 0
    }
    assert tackle_targets == {("foe", 0), ("foe", 1), ("ally", 1)}


def test_self_targeting_move_yields_exactly_one_action_with_no_target():
    obs = _observation(_own_side())
    protects = [a for a in legal_slot_actions(obs, 0, MOVES) if getattr(a, "move_index", None) == 1]
    assert len(protects) == 1
    assert protects[0].target is None


def test_spread_move_is_not_offered_per_target():
    own = _own_side(team=(_mon("a", moves=("heatwave",)), *_own_side().team[1:]))
    obs = _observation(own)
    moves = [a for a in legal_slot_actions(obs, 0, MOVES) if isinstance(a, MoveAction)]
    assert len(moves) == 1
    assert moves[0].target is None


def test_fainted_foe_is_not_a_valid_target():
    opponent = Side(
        team=(_mon("foe0", current_hp=0), *[_mon(f"foe{i}") for i in range(1, 4)]),
        active_slots=(0, 1),
    )
    obs = _observation(_own_side(), opponent)
    targets = {
        (a.target.side, a.target.slot)
        for a in legal_slot_actions(obs, 0, MOVES)
        if isinstance(a, MoveAction) and a.target is not None
    }
    assert ("foe", 0) not in targets
    assert ("foe", 1) in targets


def test_ally_targeting_move_disappears_when_partner_is_gone():
    own = _own_side(
        team=(_mon("a", moves=("helpinghand",)), *_own_side().team[1:]),
        active_slots=(0, None),
    )
    obs = _observation(own)
    assert not [a for a in legal_slot_actions(obs, 0, MOVES) if isinstance(a, MoveAction)]


def test_switches_offered_for_healthy_benched_pokemon_only():
    own = _own_side(
        team=(_mon("a"), _mon("b"), _mon("c", current_hp=0), _mon("d")),
        active_slots=(0, 1),
    )
    obs = _observation(own)
    actions = legal_slot_actions(obs, 0, MOVES)
    assert {a.team_index for a in actions if isinstance(a, SwitchAction)} == {3}


def test_trapped_pokemon_cannot_switch_but_can_still_move():
    own = _own_side(
        team=(_mon("a", volatile_conditions=frozenset({"trapped"})), *_own_side().team[1:]),
    )
    obs = _observation(own)
    actions = legal_slot_actions(obs, 0, MOVES)
    assert not [a for a in actions if isinstance(a, SwitchAction)]
    assert [a for a in actions if isinstance(a, MoveAction)]


def test_zero_pp_move_is_excluded():
    own = _own_side(
        team=(_mon("a", moves=("tackle", "protect"), move_pp=(0, 5)), *_own_side().team[1:]),
    )
    obs = _observation(own)
    used = {a.move_index for a in legal_slot_actions(obs, 0, MOVES) if isinstance(a, MoveAction)}
    assert used == {1}


def test_empty_slot_may_only_switch_someone_in():
    own = _own_side(active_slots=(0, None))
    actions = legal_slot_actions(_observation(own), 1, MOVES)
    assert actions
    assert all(isinstance(a, SwitchAction) for a in actions)


def test_empty_slot_with_no_bench_left_passes():
    own = _own_side(
        team=(_mon("a"), _mon("b", current_hp=0), _mon("c", current_hp=0), _mon("d", current_hp=0)),
        active_slots=(0, None),
    )
    actions = legal_slot_actions(_observation(own), 1, MOVES)
    assert actions == [PassAction()]


def test_unknown_move_data_raises_rather_than_silently_dropping_the_move():
    own = _own_side(team=(_mon("a", moves=("mysterymove",)), *_own_side().team[1:]))
    with pytest.raises(KeyError):
        legal_slot_actions(_observation(own), 0, MOVES)


def test_joint_actions_cover_both_slots_and_stay_legal():
    obs = _observation(_own_side())
    joint = legal_joint_actions(obs, MOVES)
    assert joint
    assert all(len(j) == 2 for j in joint)


def test_joint_actions_exclude_both_slots_switching_to_the_same_pokemon():
    own = _own_side(
        team=(_mon("a"), _mon("b"), _mon("c", current_hp=0), _mon("d")),
        active_slots=(0, 1),
    )
    joint = legal_joint_actions(_observation(own), MOVES)
    for action in joint:
        switch_targets = [a.team_index for a in action.slot_actions if isinstance(a, SwitchAction)]
        assert len(set(switch_targets)) == len(switch_targets)


def test_generator_never_offers_a_special_mechanic_while_engine_flags_are_unavailable():
    obs = _observation(_own_side())
    for action in legal_joint_actions(obs, MOVES):
        assert not any(isinstance(a, MoveAction) and a.special for a in action.slot_actions)


# --------------------------------------------------------------- out of PP


def test_a_pokemon_with_no_usable_moves_is_offered_one_anyway():
    """Struggle, and the engine supplies it.

    When every move is disabled or out of PP the engine does not accept a pass
    -- `Side.chooseMove` says "Override action and use Struggle if there are no
    enabled moves with PP" and substitutes it for whatever move is chosen. So
    the generator must still offer a move.

    Found by a harness crash rather than by reading the code: 800 battles of
    random attacking exhaust PP often enough to hit it in the first run, and it
    would have crashed the agent in any sufficiently long real game.
    """
    spent = _mon("Solo", moves=("tackle", "protect"), move_pp=(0, 0))
    # Every bench Pokemon fainted, so there is nowhere to switch either --
    # which is the only way the move list can come out empty.
    own = Side(
        team=(spent, *(_mon(f"Down{i}", current_hp=0) for i in range(3))),
        active_slots=(0, None),
    )
    actions = legal_slot_actions(_observation(own), 0, MOVES)
    assert actions
    assert not any(isinstance(a, PassAction) for a in actions)
    assert all(isinstance(a, MoveAction) for a in actions)


def test_an_empty_slot_still_passes():
    """The other branch, and it is genuinely a pass: nothing is there to act."""
    own = Side(
        team=(_mon("Solo"), *(_mon(f"Down{i}", current_hp=0) for i in range(3))),
        active_slots=(0, None),
    )
    actions = legal_slot_actions(_observation(own), 1, MOVES)
    assert actions == [PassAction()]


class TestLastResortAvoidsDisabledMoves:
    """The blind fallback sent the engine a disabled move once.

    When every move has been filtered, `legal_slot_actions` falls back to a
    single `MoveAction` so the slot has *something* -- passing is refused for a
    slot the engine expects to act. It used to name move index 0 whatever that
    was, on the grounds that Showdown substitutes Struggle. It only does that
    when the request itself carries no usable move, and in that case the
    request already offers Struggle and the normal path returns it. So naming a
    disabled move here gets the whole choice rejected:

        [Unavailable choice] Can't move: Whimsicott's Protect is disabled

    Observed once against a scripted opponent and not reproduced since, so this
    is a narrowing rather than a claimed root cause: of the two filters, PP is
    the one that can be stale, while `disabled` arrives on the engine's own
    request.
    """

    def _cornered(self, disabled: frozenset[str], pp: tuple[int, ...]):
        """A Pokemon whose every move our filters reject."""
        moves = ("protect", "tackle")
        mon = _mon(
            "own0",
            moves=moves,
            choosable_moves=moves,
            choosable_move_targets=("self", "normal"),
            move_pp=pp,
            disabled_moves=disabled,
            # Trapped, so switching cannot rescue the slot and the fallback is
            # actually reached. Without this the bench supplies legal actions
            # and the branch under test never runs.
            volatile_conditions=frozenset({"trapped"}),
        )
        side = _own_side(team=(mon, _mon("own1"), _mon("own2"), _mon("own3")))
        return legal_slot_actions(_observation(side), 0, MOVES)

    def test_a_disabled_move_is_not_named_when_another_is_only_out_of_pp(self):
        """Protect is disabled by the engine; Tackle merely looks spent to us.

        Tackle is the safer thing to offer: the engine never said it was
        unusable, and our PP count is the belief more likely to be wrong. The
        last resort re-runs the normal rules with the PP filter dropped, so
        what comes back is properly targeted rather than a bare move index.
        """
        actions = self._cornered(disabled=frozenset({"protect"}), pp=(10, 0))
        assert actions, "the slot must be given something to do"
        moves = [a for a in actions if isinstance(a, MoveAction)]
        assert moves
        assert all(a.move_index == 1 for a in moves), (
            "should offer Tackle only, never the disabled Protect"
        )

    def test_everything_disabled_still_names_a_move_for_struggle(self):
        """The case the fallback was written for is unchanged."""
        actions = self._cornered(disabled=frozenset({"protect", "tackle"}), pp=(10, 10))
        assert len(actions) == 1
        assert isinstance(actions[0], MoveAction)
        assert actions[0].move_index == 0


class TestTargetRelaxationStaysLegal:
    """Relaxing a target must not invent one the move cannot use.

    When a slot has no usable action, `legal_slot_actions` relaxes *targeting*
    and aims at the first foe, because the engine rejects a targetless attack
    with "Ice Beam needs a target" and our view of who is standing can lag the
    engine's mid-turn.

    Applied to every target type, that sent Helping Hand -- `adjacentAlly` --
    at an opponent, and the engine refused the whole choice:

        [Invalid choice] Can't move: Invalid target for Helping Hand

    An ally-only move with no living ally has no legal target at all.
    """

    def _alone(self, moves: tuple[str, ...], targets: tuple[str, ...]):
        """One Pokemon with usable moves, no partner, and no foe we can see.

        PP must remain, or every move is filtered before targeting is even
        considered and the final Struggle fallback runs instead of the branch
        under test. What makes targets empty here is that our view has no
        living opponent -- exactly the mid-turn lag the relaxation exists for.
        """
        mon = _mon(
            "own0",
            moves=moves,
            choosable_moves=moves,
            choosable_move_targets=targets,
            move_pp=(10,) * len(moves),
            volatile_conditions=frozenset({"trapped"}),
        )
        side = _own_side(
            team=(mon, _mon("own1"), _mon("own2"), _mon("own3")),
            active_slots=(0, None),
        )
        downed = Side(
            team=tuple(_mon(f"foe{i}", current_hp=0) for i in range(4)),
            active_slots=(0, 1),
        )
        return legal_slot_actions(_observation(side, downed), 0, MOVES)

    def test_an_ally_only_move_is_not_aimed_at_an_opponent(self):
        actions = self._alone(("helpinghand",), ("adjacentAlly",))
        for action in actions:
            if isinstance(action, MoveAction) and action.target is not None:
                assert action.target.side != "foe", "Helping Hand cannot be aimed at a foe"

    def test_an_attacking_move_still_gets_the_relaxed_foe_target(self):
        """The behaviour the relaxation exists for is unchanged."""
        actions = self._alone(("tackle",), ("normal",))
        aimed = [a for a in actions if isinstance(a, MoveAction) and a.target is not None]
        assert aimed, "an attacking move should still be offered a foe target"
        assert all(a.target.side == "foe" for a in aimed)


class TestAllyMoveWithAFaintedPartner:
    """The engine keeps an ally-targeting move enabled after the ally faints.

    Real state, from a run that crashed: Tinkaton held Fake Out, Helping Hand,
    Encore and Gigaton Hammer with three of them disabled by the engine and
    Politoed fainted beside it. Helping Hand was the only move the engine had
    *not* disabled, so under ADR 0003 it is the choice the engine expects --
    but its partner was gone, so our own liveness check found no target.

    Both earlier answers were refused. Aiming at a foe:

        Can't move: Invalid target for Helping Hand

    and falling through to a bare move index with no target:

        Can't move: Helping Hand needs a target

    So the partner's slot is named even though nobody is standing in it.
    """

    def _with_fainted_partner(self):
        actor = _mon(
            "own0",
            moves=("helpinghand",),
            choosable_moves=("helpinghand",),
            choosable_move_targets=("adjacentAlly",),
            move_pp=(16,),
            volatile_conditions=frozenset({"trapped"}),
        )
        downed = _mon("own1", current_hp=0)
        side = _own_side(
            team=(actor, downed, _mon("own2"), _mon("own3")),
            active_slots=(0, 1),
        )
        return legal_slot_actions(_observation(side), 0, MOVES)

    def test_the_move_is_still_offered(self):
        actions = self._with_fainted_partner()
        moves = [a for a in actions if isinstance(a, MoveAction)]
        assert moves, "the engine expects this move, so it must be offered"

    def test_it_names_the_partner_slot_and_not_a_foe(self):
        for action in self._with_fainted_partner():
            if isinstance(action, MoveAction):
                assert action.target is not None, "the engine refuses no target"
                assert action.target.side == "ally"


class TestSwitchOnlyEnumeration:
    """Replacing a fainted Pokemon must not depend on move data.

    Move target types are learned from requests that carry an `active` block,
    and a forced-switch request carries none -- so a Pokemon that has not yet
    had a move request has no entry. That is routine. The forced-switch path
    made it fatal by asking `legal_slot_actions` for every action and then
    keeping only the switches:

        KeyError: no MoveData for move 'dazzlinggleam' on 'Hatterene'

    It built every move action, discarded them all, and crashed on data it did
    not need. Surfaced by matchup switching, which reaches replacement turns far
    more often.
    """

    def _side(self, fainted_first: bool):
        active = _mon("own0", current_hp=0 if fainted_first else 100)
        return _own_side(
            team=(active, _mon("own1"), _mon("own2"), _mon("own3")),
            active_slots=(0, 1),
        )

    def test_no_move_data_is_needed_at_all(self):
        """The empty mapping is the point: it is what the tracker has here."""
        actions = legal_switch_actions(_observation(self._side(True)), 0)
        assert actions
        assert all(isinstance(a, SwitchAction) for a in actions)

    def test_it_matches_what_the_old_filter_produced(self):
        """Same answer as before for a healthy slot, without the moves."""
        side = self._side(False)
        observation = _observation(side)
        expected = [
            a for a in legal_slot_actions(observation, 0, MOVES) if isinstance(a, SwitchAction)
        ]
        assert legal_switch_actions(observation, 0) == expected

    def test_a_trapped_pokemon_still_cannot_switch(self):
        trapped = _mon("own0", volatile_conditions=frozenset({"trapped"}))
        side = _own_side(
            team=(trapped, _mon("own1"), _mon("own2"), _mon("own3")),
            active_slots=(0, 1),
        )
        assert legal_switch_actions(_observation(side), 0) == []

    def test_a_fainted_pokemon_is_replaceable_even_while_trapped(self):
        """Trapping does not hold a Pokemon that is already gone."""
        gone = _mon("own0", current_hp=0, volatile_conditions=frozenset({"trapped"}))
        side = _own_side(
            team=(gone, _mon("own1"), _mon("own2"), _mon("own3")),
            active_slots=(0, 1),
        )
        assert legal_switch_actions(_observation(side), 0)
