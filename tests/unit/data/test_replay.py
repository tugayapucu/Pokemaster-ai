"""Replay parsing.

The fixture below is the real shape of a Reg M-B replay, taken from
`gen9championsvgc2026regmb-2666119458` -- including the Elo on the player
lines, which is the field that makes filtering for strong play possible.
"""

import json

import pytest

from champions_ai.data import (
    Replay,
    ReplayMetadata,
    has_human_players,
    looks_like_bot,
    parse_ratings,
    unobservable_turns,
)

LOG = "\n".join(
    [
        "|j|☆audino316",
        "|j|☆sauan2",
        "|t:|1786957837",
        "|gametype|doubles",
        "|player|p1|audino316|byron|1553",
        "|player|p2|sauan2|2|1643",
        "|gen|9",
        "|tier|[Gen 9 Champions] VGC 2026 Reg M-B",
        "|rated|",
        "|clearpoke",
        "|poke|p1|Maushold-Four, L50|",
        "|poke|p2|Charizard, L50, F, shiny|",
        "|teampreview|4",
        "|start",
        "|switch|p1a: Aerodactyl|Aerodactyl, L50, M|100/100",
        "|switch|p2a: Charizard|Charizard, L50, F|100/100",
        "|turn|1",
        "|move|p1a: Aerodactyl|Rock Slide|p2a: Charizard",
        "|-damage|p2a: Charizard|39/100",
        "|turn|2",
        "|move|p2a: Charizard|Heat Wave|p1a: Aerodactyl",
        "|-damage|p1a: Aerodactyl|10/100",
        "|turn|3",
        "|faint|p1a: Aerodactyl",
        "|win|sauan2",
    ]
)

PAYLOAD = {
    "id": "gen9championsvgc2026regmb-2666119458",
    "formatid": "gen9championsvgc2026regmb",
    "players": ["audino316", "sauan2"],
    "uploadtime": 1786958053,
    "rating": 1553,
    "log": LOG,
}


@pytest.fixture
def replay() -> Replay:
    return Replay.from_payload(PAYLOAD)


def test_reads_provenance(replay):
    assert replay.metadata.replay_id == "gen9championsvgc2026regmb-2666119458"
    assert replay.metadata.format_id == "gen9championsvgc2026regmb"
    assert replay.metadata.players == ("audino316", "sauan2")
    assert replay.metadata.upload_time == 1786958053


def test_reads_elo_from_the_player_lines(replay):
    """The search listing omits ratings; the replay itself carries them."""
    assert replay.metadata.ratings == (1553, 1643)


def test_detects_a_rated_game(replay):
    assert replay.metadata.rated


def test_unrated_games_have_no_ratings():
    log = LOG.replace("|player|p1|audino316|byron|1553", "|player|p1|audino316|byron|")
    log = log.replace("|player|p2|sauan2|2|1643", "|player|p2|sauan2|2|")
    unrated = Replay.from_payload({**PAYLOAD, "log": log})
    assert unrated.metadata.ratings == (None, None)
    assert unrated.metadata.minimum_rating is None


def test_high_level_requires_both_players_to_clear_the_bar(replay):
    """A strong player beating a weak one never really tested their choices."""
    assert replay.metadata.minimum_rating == 1553
    assert replay.metadata.is_high_level(1500)
    assert not replay.metadata.is_high_level(1600)


def test_a_game_with_an_unknown_rating_is_not_high_level():
    log = LOG.replace("|player|p2|sauan2|2|1643", "|player|p2|sauan2|2|")
    partial = Replay.from_payload({**PAYLOAD, "log": log})
    assert not partial.metadata.is_high_level(1000)


def test_counts_turns_and_finds_the_winner(replay):
    assert replay.turn_count == 3
    assert replay.winner == "sauan2"


def test_lines_before_a_turn_exclude_everything_after_it(replay):
    """The guard against leaking the future backwards into a decision."""
    early = replay.lines_before_turn(2)
    assert any("Rock Slide" in line for line in early)
    assert not any("Heat Wave" in line for line in early)
    assert not any(line.startswith("|win|") for line in early)


def test_the_first_turn_sees_only_the_setup(replay):
    early = replay.lines_before_turn(1)
    assert any(line.startswith("|switch|") for line in early)
    assert not any(line.startswith("|move|") for line in early)


def test_bot_accounts_are_recognised():
    """Training on bot games while calling it expert play is a silent failure."""
    assert looks_like_bot("pcrlbot12d159c39a")
    assert not looks_like_bot("audino316")


def test_replays_with_a_bot_are_filtered_out(replay):
    assert has_human_players(replay.metadata)
    with_bot = ReplayMetadata(
        replay_id="x", format_id="y", players=("pcrlbot12d159c39a", "audino316"),
        ratings=(1500, 1500), upload_time=0, rated=True,
    )
    assert not has_human_players(with_bot)


def test_round_trips_through_disk(replay, tmp_path):
    path = tmp_path / "replay.json"
    replay.save(path)
    restored = Replay.load(path)
    assert restored.metadata.replay_id == replay.metadata.replay_id
    assert restored.log == replay.log
    assert json.loads(path.read_text(encoding="utf-8"))["log"]


def test_turns_where_a_pokemon_could_not_act_are_flagged_unobservable():
    """`|cant|` records the failure, never the action its player chose."""
    log = "\n".join([
        "|player|p1|a|x|1500",
        "|player|p2|b|y|1500",
        "|turn|1",
        "|move|p1a: X|Tackle|p2a: Y",
        "|turn|2",
        "|cant|p1a: X|par",
        "|move|p2a: Y|Tackle|p1a: X",
        "|turn|3",
        "|move|p1a: X|Tackle|p2a: Y",
    ])
    replay = Replay.from_payload({**PAYLOAD, "log": log})
    assert unobservable_turns(replay.log) == frozenset({2})


def test_a_clean_battle_has_no_unobservable_turns(replay):
    assert unobservable_turns(replay.log) == frozenset()


def test_parse_ratings_directly():
    ratings = parse_ratings(tuple(LOG.split("\n")))
    assert ratings["p1"] == ("audino316", 1553)
    assert ratings["p2"] == ("sauan2", 1643)
