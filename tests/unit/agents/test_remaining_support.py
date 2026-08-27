"""The support moves the backlog called unpriceable, and mostly were not.

Six were blocked on plumbing rather than on knowledge. Swallow is the clearest
case: the item said it "needs a Stockpile counter that nothing tracks", and the
engine announces every layer as `|-start|...|stockpile1`, so the counter had
been a tracked volatile all along.

Two of these come out **negative**, and are left that way. Swallow hands back
six defensive stages to heal one health bar, and Healing Wish faints its user.
Both are honest readings of the currency rather than bugs, the same call this
project already made for Rest.
"""


from champions_ai.agents.support import _stockpile_layers, score_support_move
from champions_ai.dex import MoveInfo
from champions_ai.domain import BattlePokemon, PokemonSet
from champions_ai.domain.boosts import Boosts


def _move(move_id, **kwargs):
    fields = dict(
        move_id=move_id, name=move_id.title(), type="Normal", category="Status",
        base_power=0, accuracy=None, priority=0, target="self",
    )
    fields.update(kwargs)
    return MoveInfo(**fields)


def _mon(hp=80, volatiles=(), boosts=None, stats=None):
    return BattlePokemon(
        pokemon_set=PokemonSet(
            species="Machamp", level=50, ability="", moves=("swallow",)
        ),
        current_hp=hp, max_hp=200,
        volatile_conditions=frozenset(volatiles),
        boosts=boosts or Boosts(),
        computed_stats=stats or {
            "hp": 200, "atk": 100, "def": 80, "spa": 90, "spd": 80, "spe": 100
        },
    )


# --- Swallow -------------------------------------------------------------


def test_the_stockpile_counter_was_already_tracked():
    """`|-start|...|stockpile3` -- the layers are in the volatiles."""
    assert _stockpile_layers(_mon(volatiles=("stockpile3",))) == 3
    assert _stockpile_layers(_mon(volatiles=("stockpile1", "substitute"))) == 1
    assert _stockpile_layers(_mon()) == 0


def test_swallow_without_a_stockpile_simply_fails():
    value, why = score_support_move(_move("swallow"), attacker=_mon())
    assert value == 0.0
    assert "needs a Stockpile" in why[0]


def test_swallow_heals_more_with_more_layers():
    one = score_support_move(
        _move("swallow"), attacker=_mon(hp=20, volatiles=("stockpile1",))
    )
    three = score_support_move(
        _move("swallow"), attacker=_mon(hp=20, volatiles=("stockpile3",))
    )
    # More layers heal more, and also cost more stages back.
    assert "25%" in one[1][0]
    assert "90%" in three[1][0] or "100%" in three[1][0]


def test_swallow_prices_negative_and_is_left_that_way():
    """Six defensive stages are worth more than one health bar in this
    currency. Deliberate, and documented where it is computed."""
    value, _ = score_support_move(
        _move("swallow"), attacker=_mon(hp=20, volatiles=("stockpile3",))
    )
    assert value < 0


# --- Wish ----------------------------------------------------------------


def test_wish_is_worth_half_a_bar_when_there_is_room_for_it():
    value, why = score_support_move(_move("wish"), attacker=_mon(hp=80))
    assert value > 0
    assert "next turn" in why[0]


def test_wish_at_full_health_is_wasted():
    value, _ = score_support_move(_move("wish"), attacker=_mon(hp=200))
    assert value == 0.0


# --- the splits ----------------------------------------------------------


def _foe(stats):
    from champions_ai.domain import ObservedPokemon

    return ObservedPokemon(
        species="Snorlax", level=50, hp_percent=100, fainted=False
    ), stats


def test_a_split_is_worth_taking_when_their_stats_are_higher():
    observed, stats = _foe({"def": 160, "spd": 160})
    value, why = score_support_move(
        _move("guardsplit", target="normal"),
        attacker=_mon(), observed=observed, observed_stats=stats,
        attacker_stats={"def": 80, "spd": 80},
    )
    assert value > 0
    assert "averages" in why[0]


def test_a_split_is_worthless_when_ours_are_already_better():
    observed, stats = _foe({"def": 40, "spd": 40})
    value, _ = score_support_move(
        _move("guardsplit", target="normal"),
        attacker=_mon(), observed=observed, observed_stats=stats,
        attacker_stats={"def": 120, "spd": 120},
    )
    assert value == 0.0


def test_power_split_reads_the_offensive_pair():
    observed, stats = _foe({"atk": 200, "spa": 200})
    value, why = score_support_move(
        _move("powersplit", target="normal"),
        attacker=_mon(), observed=observed, observed_stats=stats,
        attacker_stats={"atk": 60, "spa": 60},
    )
    assert value > 0
    assert "atk" in why[0]


# --- Magnetic Flux -------------------------------------------------------


def test_magnetic_flux_needs_an_ally_with_plus_or_minus():
    value, why = score_support_move(
        _move("magneticflux", target="allySide"),
        attacker=_mon(), ally=_mon(), ally_ability="levitate",
    )
    assert value == 0.0
    assert "Plus or Minus" in why[0]


def test_magnetic_flux_buffs_a_qualifying_ally():
    value, why = score_support_move(
        _move("magneticflux", target="allySide"),
        attacker=_mon(), ally=_mon(), ally_ability="minus",
    )
    assert value > 0
    assert "defences" in why[0]


# --- Healing Wish --------------------------------------------------------


def test_healing_wish_is_right_when_we_are_nearly_dead_and_they_are_hurt():
    value, _ = score_support_move(
        _move("healingwish"), attacker=_mon(hp=10), bench_hp_fractions=(0.2,)
    )
    assert value > 0


def test_healing_wish_throws_away_a_healthy_pokemon():
    value, _ = score_support_move(
        _move("healingwish"), attacker=_mon(hp=200), bench_hp_fractions=(0.9,)
    )
    assert value < 0


def test_healing_wish_with_an_empty_bench_does_nothing():
    value, why = score_support_move(
        _move("healingwish"), attacker=_mon(hp=10), bench_hp_fractions=()
    )
    assert value == 0.0
    assert "nobody" in why[0]
