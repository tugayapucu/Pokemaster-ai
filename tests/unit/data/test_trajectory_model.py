"""Trajectory serialisation, tested without needing a simulator."""

from champions_ai.data import SCHEMA_VERSION, DecisionRecord, Trajectory, git_commit, utc_now
from champions_ai.domain import JointAction, MoveAction, TargetSlot, TeamPreviewAction


def _trajectory(**overrides) -> Trajectory:
    defaults = dict(
        format_id="gen9championsvgc2026regmb",
        seed="sodium,abc",
        packed_teams=("packed1", "packed2"),
        decisions=(
            DecisionRecord(
                turn=0,
                player=0,
                action=TeamPreviewAction(picks=(0, 1, 2, 3)),
                legal_action_count=360,
            ),
            DecisionRecord(
                turn=1,
                player=1,
                action=JointAction(
                    slot_actions=(
                        MoveAction(move_index=0, target=TargetSlot(side="foe", slot=1)),
                        MoveAction(move_index=2, special="mega"),
                    )
                ),
                legal_action_count=94,
            ),
        ),
        winner=1,
        turns=12,
        recorded_at=utc_now(),
    )
    return Trajectory(**{**defaults, **overrides})


def test_defaults_to_the_current_schema_version():
    assert _trajectory().schema_version == SCHEMA_VERSION


def test_round_trips_through_json_preserving_action_types():
    """Both action kinds must survive; an untagged union would collapse them."""
    original = _trajectory()
    restored = Trajectory.model_validate_json(original.model_dump_json())

    assert restored == original
    assert isinstance(restored.decisions[0].action, TeamPreviewAction)
    assert isinstance(restored.decisions[1].action, JointAction)


def test_nested_slot_actions_survive_the_round_trip():
    restored = Trajectory.model_validate_json(_trajectory().model_dump_json())
    joint = restored.decisions[1].action
    assert joint.slot_actions[0].target == TargetSlot(side="foe", slot=1)
    assert joint.slot_actions[1].special == "mega"


def test_replayable_requires_a_seed():
    assert _trajectory().replayable
    assert not _trajectory(seed=None).replayable


def test_without_protocol_shrinks_the_record_but_keeps_it_replayable():
    full = _trajectory(protocol=("|turn|1", "|move|p1a: X|Tackle", "|win|P2"))
    lean = full.without_protocol()

    assert lean.protocol == ()
    assert lean.replayable
    assert lean.decisions == full.decisions


def test_save_and_load(tmp_path):
    path = tmp_path / "nested" / "battle.json"
    original = _trajectory()
    original.save(path)

    assert path.exists()
    assert Trajectory.load(path) == original


def test_git_commit_is_a_hash_or_none_but_never_raises():
    commit = git_commit()
    assert commit is None or len(commit) == 40


def test_metadata_carries_experiment_provenance():
    """AGENTS.md asks runs to record what produced them."""
    trajectory = _trajectory(metadata={"p1_agent": "random", "p2_agent": "heuristic-v1"})
    restored = Trajectory.model_validate_json(trajectory.model_dump_json())
    assert restored.metadata["p2_agent"] == "heuristic-v1"
