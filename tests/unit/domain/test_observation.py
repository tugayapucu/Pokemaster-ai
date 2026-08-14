import pytest

from champions_ai.domain import (
    REGULATION_M_B,
    BattlePokemon,
    BattleState,
    Boosts,
    Observation,
    ObservedPokemon,
    PokemonSet,
    Side,
    StatSpread,
)

SECRET_MOVE = "dracometeor"
SECRET_ITEM = "lifeorb"
SECRET_ABILITY = "roughskin"


def _mon(
    species: str,
    *,
    hp: int = 100,
    max_hp: int = 100,
    seen: bool = True,
    **overrides,
) -> BattlePokemon:
    defaults = dict(
        pokemon_set=PokemonSet(
            species=species,
            level=50,
            ability=SECRET_ABILITY,
            moves=("tackle", SECRET_MOVE),
            item=SECRET_ITEM,
            stats=StatSpread(hp=31, speed=29),
        ),
        current_hp=hp,
        max_hp=max_hp,
        current_ability=SECRET_ABILITY,
        current_item=SECRET_ITEM,
        has_been_active=seen,
    )
    return BattlePokemon(**{**defaults, **overrides})


def _side(prefix: str, seen_flags: tuple[bool, ...] = (True, True, False, False)) -> Side:
    return Side(
        team=tuple(_mon(f"{prefix}{i}", seen=seen) for i, seen in enumerate(seen_flags)),
        active_slots=(0, 1),
    )


def _state(**overrides) -> BattleState:
    defaults = dict(
        regulation=REGULATION_M_B,
        turn=3,
        sides=(_side("p1"), _side("p2")),
    )
    return BattleState(**{**defaults, **overrides})


def test_observation_keeps_full_truth_for_own_side():
    obs = Observation.from_battle_state(_state(), player=0)
    own_mon = obs.own_side.team[0]
    assert own_mon.current_hp == 100
    assert own_mon.pokemon_set.moves == ("tackle", SECRET_MOVE)
    assert own_mon.pokemon_set.item == SECRET_ITEM


def test_opponent_secrets_do_not_appear_anywhere_in_serialized_observation():
    """The strongest guarantee: dump the whole observation and grep it for secrets."""
    obs = Observation.from_battle_state(_state(), player=0)
    dumped = obs.opponent_side.model_dump_json()
    assert SECRET_MOVE not in dumped
    assert SECRET_ITEM not in dumped
    assert SECRET_ABILITY not in dumped


def test_observed_pokemon_has_no_field_that_could_hold_secrets():
    forbidden = {"pokemon_set", "current_hp", "max_hp", "stats", "nature"}
    assert forbidden.isdisjoint(ObservedPokemon.model_fields)


def test_opponent_hp_is_a_percentage_not_exact_values():
    side = Side(team=(_mon("a", hp=87, max_hp=174), *_side("p2").team[1:]), active_slots=(0, 1))
    obs = Observation.from_battle_state(_state(sides=(_side("p1"), side)), player=0)
    assert obs.opponent_side.revealed[0].hp_percent == 50


def test_barely_alive_opponent_never_reports_zero_percent():
    side = Side(team=(_mon("a", hp=1, max_hp=400), *_side("p2").team[1:]), active_slots=(0, 1))
    obs = Observation.from_battle_state(_state(sides=(_side("p1"), side)), player=0)
    observed = obs.opponent_side.revealed[0]
    assert observed.hp_percent == 1
    assert not observed.fainted


def test_unseen_opponent_pokemon_are_only_a_count():
    obs = Observation.from_battle_state(_state(), player=0)
    assert len(obs.opponent_side.revealed) == 2
    assert obs.opponent_side.unrevealed_count == 2


def test_revealed_move_becomes_visible_but_unused_moves_do_not():
    revealed_mon = _mon("a").with_revealed_move("tackle")
    side = Side(team=(revealed_mon, *_side("p2").team[1:]), active_slots=(0, 1))
    obs = Observation.from_battle_state(_state(sides=(_side("p1"), side)), player=0)
    observed = obs.opponent_side.revealed[0]
    assert observed.revealed_moves == frozenset({"tackle"})
    assert SECRET_MOVE not in observed.revealed_moves


def test_item_and_ability_hidden_until_flagged_revealed():
    obs = Observation.from_battle_state(_state(), player=0)
    observed = obs.opponent_side.revealed[0]
    assert observed.revealed_item is None
    assert observed.revealed_ability is None


def test_item_and_ability_appear_once_revealed():
    mon = _mon("a", item_revealed=True, ability_revealed=True)
    side = Side(team=(mon, *_side("p2").team[1:]), active_slots=(0, 1))
    obs = Observation.from_battle_state(_state(sides=(_side("p1"), side)), player=0)
    observed = obs.opponent_side.revealed[0]
    assert observed.revealed_item == SECRET_ITEM
    assert observed.revealed_ability == SECRET_ABILITY


def test_status_and_boosts_are_public():
    mon = _mon("a", status="brn", boosts=Boosts(attack=2))
    side = Side(team=(mon, *_side("p2").team[1:]), active_slots=(0, 1))
    obs = Observation.from_battle_state(_state(sides=(_side("p1"), side)), player=0)
    observed = obs.opponent_side.revealed[0]
    assert observed.status == "brn"
    assert observed.boosts.attack == 2


def test_active_slots_are_remapped_to_the_revealed_list():
    seen = (False, True, True, False)
    side = Side(
        team=tuple(_mon(f"p2{i}", seen=s) for i, s in enumerate(seen)),
        active_slots=(1, 2),
    )
    obs = Observation.from_battle_state(_state(sides=(_side("p1"), side)), player=0)
    assert obs.opponent_side.active_slots == (0, 1)
    assert obs.opponent_side.revealed[0].species == "p21"


def test_each_player_sees_their_own_side_as_own():
    state = _state()
    obs_p1 = Observation.from_battle_state(state, player=1)
    assert obs_p1.player == 1
    assert obs_p1.own_side.team[0].pokemon_set.species == "p20"


def test_rejects_invalid_player_index():
    with pytest.raises(ValueError):
        Observation.from_battle_state(_state(), player=2)
