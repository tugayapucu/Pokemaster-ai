"""Abilities that change how fast something is.

Four double Speed under their own weather and one does it when the holder's
item is gone. All five are `onModifySpe` handlers, like Tailwind and the items,
so they multiply in alongside rather than before or after.

**Speed Boost is deliberately not here.** It raises the stat with
`this.boost({spe: 1})`, which announces itself as an ordinary `|-boost|` line,
and boosts are already tracked on both sides. Modelling it again would
double-count it — the backlog said it "needs a per-turn counter" and that was
simply wrong.

Protosynthesis and Quark Drive are absent for a different reason: zero species
in this dex have either.
"""

from champions_ai.mechanics.turn_order import effective_speed, speed_ability_multiplier


def test_each_ability_doubles_under_its_own_weather():
    for ability, weather in (
        ("chlorophyll", "sunnyday"),
        ("swiftswim", "raindance"),
        ("sandrush", "sandstorm"),
        ("slushrush", "snowscape"),
    ):
        assert speed_ability_multiplier(ability, weather=weather) == 2, ability


def test_the_wrong_weather_does_nothing():
    assert speed_ability_multiplier("chlorophyll", weather="raindance") == 1
    assert speed_ability_multiplier("swiftswim", weather="sunnyday") == 1
    assert speed_ability_multiplier("sandrush", weather=None) == 1


def test_the_primal_weathers_count_too():
    """Not in Reg M-B, and listed anyway: wrong-by-omission is the failure this
    kind of table exists to avoid."""
    assert speed_ability_multiplier("chlorophyll", weather="desolateland") == 2
    assert speed_ability_multiplier("swiftswim", weather="primordialsea") == 2


def test_slush_rush_answers_to_both_names_for_snow():
    assert speed_ability_multiplier("slushrush", weather="hail") == 2
    assert speed_ability_multiplier("slushrush", weather="snowscape") == 2


def test_unburden_needs_the_item_to_be_gone_not_merely_used():
    """The engine checks `!pokemon.item`, so having *had* an item is not
    enough -- it has to be gone now."""
    assert speed_ability_multiplier("unburden", holds_item=False) == 2
    assert speed_ability_multiplier("unburden", holds_item=True) == 1


def test_an_unknown_ability_changes_nothing():
    assert speed_ability_multiplier(None, weather="sunnyday") == 1
    assert speed_ability_multiplier("hugepower", weather="sunnyday") == 1


# --- how it composes with everything else --------------------------------


def test_the_doubling_stacks_with_a_choice_scarf():
    plain = effective_speed(100)
    both = effective_speed(
        100, item="choicescarf", ability="chlorophyll", weather="sunnyday"
    )
    assert plain == 100
    assert both == 300      # 100 x1.5 scarf, then x2


def test_paralysis_still_lands_last():
    """The engine's `onModifySpePriority: -101` halves the *total*, after the
    ability has doubled it -- not the raw stat."""
    doubled = effective_speed(100, ability="swiftswim", weather="raindance")
    slowed = effective_speed(
        100, ability="swiftswim", weather="raindance", paralysed=True
    )
    assert doubled == 200
    assert slowed == 100


def test_speed_boost_arrives_as_an_ordinary_stage():
    """Which is the whole reason it needs no rule of its own."""
    assert effective_speed(100, boost_stage=1, ability="speedboost") == 150
