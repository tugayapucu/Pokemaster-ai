"""End-to-end checks against a real Showdown process.

Marked `integration` because they spawn Node; skipped automatically when it
isn't installed.
"""

import random

import pytest

from champions_ai.simulator import ShowdownBridge

pytestmark = pytest.mark.integration

SEED = "sodium," + "0123456789abcdef" * 4


def _choose(request: dict, rng: random.Random) -> str | None:
    """A crude legal choice -- enough to drive a battle, not to play well."""
    if request.get("wait"):
        return None
    if request.get("teamPreview"):
        return "default"

    if request.get("forceSwitch"):
        side = request["side"]["pokemon"]
        chosen: set[int] = set()
        picks = []
        for must_switch in request["forceSwitch"]:
            options = [
                i + 1
                for i, mon in enumerate(side)
                if not mon["active"]
                and not mon["condition"].endswith(" fnt")
                and i + 1 not in chosen
            ]
            if not must_switch or not options:
                picks.append("pass")
                continue
            target = rng.choice(options)
            chosen.add(target)
            picks.append(f"switch {target}")
        return ", ".join(picks)

    if request.get("active"):
        picks = []
        for slot, active in enumerate(request["active"]):
            if request["side"]["pokemon"][slot]["condition"].endswith(" fnt"):
                picks.append("pass")
                continue
            usable = [i + 1 for i, m in enumerate(active["moves"]) if not m.get("disabled")]
            move = rng.choice(usable) if usable else 1
            if active["moves"][move - 1].get("target") in ("normal", "any", "adjacentFoe"):
                picks.append(f"move {move} {rng.choice([1, 2])}")
            else:
                picks.append(f"move {move}")
        return ", ".join(picks)
    return None


def _play(battle_format: str, teams: tuple[str, str], seed: str | None) -> dict:
    """Run one battle to completion, returning the log and what the requests exposed."""
    with ShowdownBridge() as bridge:
        events = bridge.start_battle(battle_format, teams[0], teams[1], seed=seed)
        rng = random.Random(20260811)
        log: list[str] = []
        p1_view: list[str] = []
        saw_mega_flag = False
        saw_disabled_flag = False
        winner = None

        for _ in range(500):
            requests: dict[str, dict] = {}
            for event in events:
                assert event["type"] != "error", event
                if event["type"] == "line":
                    log.append(event["line"])
                    if event["line"].startswith("|win|"):
                        winner = event["line"].split("|")[2]
                elif event["type"] == "sideline":
                    if event["player"] == "p1":
                        p1_view.append(event["line"])
                elif event["type"] == "request":
                    requests[event["player"]] = event["request"]

            if winner is not None:
                break

            for request in requests.values():
                for active in request.get("active") or []:
                    saw_mega_flag |= bool(active.get("canMegaEvo"))
                    saw_disabled_flag |= any(m.get("disabled") for m in active["moves"])

            if not requests:
                break

            events = []
            for player, request in requests.items():
                choice = _choose(request, rng)
                if choice:
                    events.extend(bridge.choose(player, choice))

        return {
            "log": log,
            "p1_view": p1_view,
            "winner": winner,
            "saw_mega_flag": saw_mega_flag,
            "saw_disabled_flag": saw_disabled_flag,
        }


def _hp_denominators(lines: list[str], ident_prefix: str) -> set[str]:
    """Denominators of HP readings for one side, e.g. {'153'} exact or {'100'} masked."""
    found = set()
    for line in lines:
        parts = line.split("|")
        if len(parts) < 4 or parts[1] not in ("switch", "drag", "-damage", "-heal"):
            continue
        if not parts[2].startswith(ident_prefix):
            continue
        condition = parts[4] if parts[1] in ("switch", "drag") else parts[3]
        health = condition.split()[0]
        if "/" in health:
            denominator = health.split("/")[1]
            # Champions appends an HP-bar colour letter at exactly 20% and 50%.
            found.add(denominator.rstrip("gyr"))
    return found


def _without_timestamps(log: list[str]) -> list[str]:
    """Drop `|t:|` lines: they carry wall-clock time and differ between identical battles."""
    return [line for line in log if not line.startswith("|t:|")]


def test_random_team_is_valid_for_the_format(bridge, battle_format, team_generator):
    packed = bridge.random_team(battle_format, team_generator)
    assert packed
    assert len(packed.split("]")) == 6


def test_battle_runs_to_completion(battle_format, teams):
    result = _play(battle_format, teams, seed=SEED)
    assert result["winner"] in ("P1", "P2")
    assert len(result["log"]) > 20


def test_same_seed_reproduces_the_battle_exactly(battle_format, teams):
    first = _play(battle_format, teams, seed=SEED)
    second = _play(battle_format, teams, seed=SEED)
    assert _without_timestamps(first["log"]) == _without_timestamps(second["log"])
    assert first["winner"] == second["winner"]


def test_only_timestamps_differ_between_seeded_runs(battle_format, teams):
    """Guards the replay comparison: if anything else becomes nondeterministic, fail loudly."""
    first = _play(battle_format, teams, seed=SEED)
    second = _play(battle_format, teams, seed=SEED)
    differing = {
        a.split("|")[1] for a, b in zip(first["log"], second["log"], strict=False) if a != b
    }
    assert differing <= {"t:"}


def test_requests_expose_mega_availability_per_adr_0003(battle_format, mega_team):
    """Both sides hold a Mega stone, so this asserts the mechanism, not luck."""
    result = _play(battle_format, (mega_team.packed, mega_team.packed), seed=SEED)
    assert result["saw_mega_flag"], (
        "no canMegaEvo seen; ADR 0003 depends on the engine reporting Mega availability"
    )


def test_player_stream_masks_opponent_hp_but_not_their_own(battle_format, mega_team):
    """The engine masks for us -- but only on the per-player stream, not the omniscient one.

    Observations must be built from `sideline` events for this reason; building
    them from `line` events would leak exact opponent HP while looking correct.
    """
    result = _play(battle_format, (mega_team.packed, mega_team.packed), seed=SEED)

    opponent_seen_by_p1 = _hp_denominators(result["p1_view"], "p2")
    assert opponent_seen_by_p1, "expected some opponent HP readings"
    assert opponent_seen_by_p1 == {"100"}, (
        f"opponent HP should be a percentage, saw denominators {opponent_seen_by_p1}"
    )

    own_seen_by_p1 = _hp_denominators(result["p1_view"], "p1")
    assert own_seen_by_p1 and own_seen_by_p1 != {"100"}, (
        f"own HP should be exact, saw denominators {own_seen_by_p1}"
    )


def test_omniscient_stream_really_does_expose_what_the_player_stream_hides(
    battle_format, mega_team
):
    """Guards against 'the masking test passes because nothing was masked'."""
    result = _play(battle_format, (mega_team.packed, mega_team.packed), seed=SEED)
    omniscient_opponent = _hp_denominators(result["log"], "p2")
    assert omniscient_opponent - {"100"}, (
        "omniscient stream should show exact opponent HP; if it doesn't, the "
        "masking test above proves nothing"
    )


def test_illegal_team_is_rejected_with_reasons(bridge, battle_format):
    with pytest.raises(Exception) as excinfo:
        bridge.validate_team(battle_format, "Pikachu\nAbility: Static\n- Thunderbolt")
    assert "illegal team" in str(excinfo.value)


def test_bridge_reports_errors_instead_of_hanging(bridge):
    events = bridge.request(cmd="nonsense")
    assert any(event["type"] == "error" for event in events)
