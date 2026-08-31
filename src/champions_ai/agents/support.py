"""What the moves the engine cannot describe are worth.

Fifty-four status moves in this dex carry their whole effect in an `onHit`
callback, so the bridge dumps nothing about them and they all shared one flat
value. Many of them are nonetheless perfectly computable from state we already
hold -- a Belly Drum is six stages against half a health bar, a Pain Split is
arithmetic on two HP totals, a Haze is the difference between the stages on
each side.

They are modelled here **regardless of how often they appear in the corpus**.
Rarity in 500 games is a fact about that sample, not about the game: a move
absent today is one metagame shift from being everywhere, and the project's
first goal is a correct model rather than a higher score on one instrument.

Priced in the same currencies as everything else (`agents.currency`), so a
Belly Drum is worth what six stages are worth minus what half a health bar is
worth -- not a number invented for it.
"""

from collections.abc import Sequence

from champions_ai.agents.currency import (
    LOW_HP_FRACTION,
    STAT_STAGE_VALUE,
    STAT_STAGE_WEIGHT,
    STATUS_VALUE,
    STATUS_WEIGHT,
    SUSTAIN_WEIGHT,
    SWITCH_WHEN_WEAKENED_BONUS,
)
from champions_ai.dex import ItemInfo, MoveInfo
from champions_ai.domain.boosts import BOOST_FIELDS, MAX_STAGE, MIN_STAGE, Boosts

# Weather-dependent recovery. The engine gives 2/3 in sun, 1/4 in any other
# weather, and 1/2 on a clear field -- so Synthesis is a very different move
# depending on what is overhead.
WEATHER_HEALS = frozenset({"moonlight", "morningsun", "synthesis"})
SUN = frozenset({"sunnyday", "desolateland"})
WEATHER_HEAL_SUN = 2 / 3
WEATHER_HEAL_CLEAR = 1 / 2
WEATHER_HEAL_OTHER = 1 / 4

BELLY_DRUM = "bellydrum"
BELLY_DRUM_COST = 0.5

REST = "rest"
# Rest heals everything and costs two turns asleep. Priced as exactly what
# being asleep is worth elsewhere, because that is what it is -- and in a
# format lasting about five turns, giving up two of them is most of the price.
# The consequence is that Rest scores negative almost everywhere, which is the
# right answer for VGC doubles rather than a bug.
REST_SLEEP_COST = STATUS_VALUE["slp"] * STATUS_WEIGHT

PAIN_SPLIT = "painsplit"
STRENGTH_SAP = "strengthsap"
HEAL_PULSE = "healpulse"
HEAL_PULSE_FRACTION = 0.5

HAZE = "haze"
PSYCH_UP = "psychup"
TOPSY_TURVY = "topsyturvy"
ACUPRESSURE = "acupressure"
# Two stages on a stat chosen at random. Which stat is unknown, so this is
# priced as two stages flat -- an over-estimate when the useful ones are
# already maxed and an under-estimate when it happens to hit Speed.
ACUPRESSURE_STAGES = 2

# Swap only the stages of the named stats with the target.
STAGE_SWAPS = {
    "powerswap": ("attack", "special_attack"),
    "guardswap": ("defense", "special_defense"),
    "speedswap": ("speed",),
}

PARTING_SHOT = "partingshot"
PARTING_SHOT_DROPS = {"attack": 1, "special_attack": 1}

HEAL_BELL = "healbell"
DEFOG = "defog"
TIDY_UP = "tidyup"
TIDY_UP_BOOSTS = {"attack": 1, "speed": 1}

# Side conditions Defog and Tidy Up sweep away. Defog clears both sides;
# Tidy Up clears hazards and substitutes only.
HAZARDS = frozenset({"stealthrock", "spikes", "toxicspikes", "stickyweb"})
SCREENS = frozenset({"reflect", "lightscreen", "auroraveil"})

# Force the target out, which undoes whatever it spent turns setting up.
PHAZING = frozenset({"whirlwind", "roar"})

# --- moves that need to know about held items ---------------------------
#
# All six were unpriceable until the tracker learned to tell "we never saw an
# item" from "we watched it go". They are still only as good as that
# knowledge: an opponent's item is hidden until it fires, so several of these
# resolve to "cannot say" against a Pokemon that has shown us nothing.

STUFF_CHEEKS = "stuffcheeks"
STUFF_CHEEKS_BOOST = 2

# Taking an item away is worth roughly what the item was doing. We only price
# the ones we model the effect of; anything else is worth *something* but not
# a number we can defend, so it falls back to this.
ITEM_DENIAL_VALUE = 18.0
CORROSIVE_GAS = "corrosivegas"

# Trick and Switcheroo swap items rather than removing one, so they are only
# good when ours is worse than theirs -- which is the whole point of the
# move, and needs to know both.
ITEM_SWAPS = frozenset({"trick", "switcheroo"})

RECYCLE = "recycle"
TEATIME = "teatime"

# --- moves that were "blocked on plumbing" rather than on knowledge --------
#
# The backlog carried these as unpriceable. They were not: every one of them
# reads state the tracker already holds, and the work was passing it in.

# Swallow eats the Stockpile it was saving. The engine announces each layer as
# `|-start|...|stockpile1` and up, so the count is an ordinary tracked
# volatile -- and the layers are also what the healing scales with.
SWALLOW = "swallow"
STOCKPILE_HEAL = {1: 0.25, 2: 0.5, 3: 1.0}
# Stockpile raised Defense and Special Defense by one per layer on the way up,
# and Swallow gives all of it back. Healing that costs two stages is a
# different move from healing that does not -- and once that price is counted,
# **Swallow comes out negative in every state we can price**, because six
# defensive stages are worth more here than one health bar.
#
# Left as computed rather than tuned into positivity, for the same reason Rest
# is: Stockpile is a fringe line in VGC doubles and the number is saying so.
# The one case the currency cannot see is a Pokemon about to be knocked out,
# where stages it will not live to use are worth nothing -- a one-turn scorer
# has no way to express that, and inventing a discount to paper over it would
# be worse than the honest negative.
STOCKPILE_STAGES_LOST = 2

# Wish heals half the *wisher's* maximum HP, at the end of the following turn,
# to whoever is standing in the slot by then. Priced as the healing it will
# most likely deliver -- usually to the same Pokemon -- with the delay stated
# rather than discounted by an invented factor.
WISH = "wish"
WISH_FRACTION = 0.5

# Guard Split and Power Split average two stats between the pair. That is a
# pure transfer: whatever we gain, they lose, so it is worth doing exactly when
# theirs are higher than ours.
STAT_SPLITS: dict[str, tuple[str, ...]] = {
    "guardsplit": ("def", "spd"),
    "powersplit": ("atk", "spa"),
}

# Magnetic Flux buffs only allies with Plus or Minus, and fails outright when
# there are none -- `if (!targets.length) return false`.
# Healing Wish faints its user to send in a replacement at full health and
# free of status. Priced as exactly that trade -- the health somebody on the
# bench gets back, minus the health we throw away making it -- which makes it
# right in the one situation it is actually played: the user is nearly dead
# anyway and somebody worth more is hurt.
HEALING_WISH = "healingwish"

MAGNETIC_FLUX = "magneticflux"
MAGNETIC_FLUX_ABILITIES = frozenset({"plus", "minus"})
MAGNETIC_FLUX_BOOSTS = {"defense": 1, "special_defense": 1}

# A split moves raw stat *points*, not stages, so it needs its own rate. One
# stage is worth STAT_STAGE_VALUE of a Pokemon and multiplies a stat by 1.5,
# so a point is worth roughly a stage divided by half a typical stat -- taken
# as 100 here, which makes twenty points about a third of a stage. Deliberately
# modest: this is the one number on the page that is a judgement rather than a
# reading of the engine.
SPLIT_POINT_VALUE = STAT_STAGE_VALUE * STAT_STAGE_WEIGHT / 100

# --- keeping something on the field --------------------------------------
#
# Trapping is worth exactly what the escape we are denying is worth, so it is
# priced with the constant our *own* switches use rather than a new one: a
# weakened Pokemon wants out, and Block is the move that says no.
TRAPPING_MOVES = frozenset({"block", "meanlook"})
# Ghost types cannot be trapped -- `trapped: 3` in the engine's type chart, the
# same mechanism that makes them immune to Normal and Fighting.
UNTRAPPABLE_TYPE = "Ghost"
TRAPPED = "trapped"

# Perish Song is deliberately *not* priced. It cuts both ways -- everything on
# the field faints, ours included -- so its worth depends on whether we are
# ahead and on whether the target can be trapped, neither of which is modelled.
# A first attempt gave it a flat value below the unknown-support fallback and
# lost three labels of agreement for it: when a computed number is worse than
# admitting ignorance, admitting ignorance is the better model.


# Rage Powder and Follow Me draw the opponent's single-target attacks onto the
# user, which is worth something only while there is a partner to draw them
# *off*. Alone they change nothing at all, and the agent was picking them
# anyway -- one battle in 200 turned into a fifteen-turn standoff of both sides
# redirecting at nobody, dragging it to 49 turns.
#
# Only the no-ally case is decided here. What a redirect is worth *with* a
# partner is a live question (experiment 0026) and is left to the unknown
# support value until it is measured.
REDIRECTION_MOVES = frozenset({"ragepowder", "followme"})


def _stage(boosts: Boosts, field: str) -> int:
    return getattr(boosts, field)


def _net_stages(boosts: Boosts) -> int:
    """Sum of every stage, positive and negative."""
    return sum(getattr(boosts, field) for field in BOOST_FIELDS.values())


def _headroom(boosts: Boosts, field: str, delta: int) -> int:
    """How much of `delta` this Pokemon can actually take, given the cap."""
    current = _stage(boosts, field)
    if delta >= 0:
        return max(0, min(delta, MAX_STAGE - current))
    return -max(0, min(-delta, current - MIN_STAGE))


def _stockpile_layers(mon) -> int:
    """How many Stockpile layers this Pokemon is holding, 0 if none.

    The engine announces them as `stockpile1`, `stockpile2`, `stockpile3`, so
    the count is already in the tracked volatiles -- the backlog listed this as
    needing "a Stockpile counter that nothing tracks", and the counter was
    there all along.
    """
    layers = [
        int(v[-1])
        for v in mon.volatile_conditions
        if v.startswith("stockpile") and v[-1].isdigit()
    ]
    return max(layers, default=0)


def _hp_fraction(mon) -> float:
    return mon.current_hp / max(1, mon.max_hp)


def _missing(mon) -> float:
    return max(0.0, 1.0 - _hp_fraction(mon))


def score_support_move(
    move: MoveInfo,
    *,
    attacker,
    ally=None,
    observed=None,
    observed_stats: dict[str, int] | None = None,
    weather: str | None = None,
    own_side_conditions: Sequence[str] = (),
    opponent_side_conditions: Sequence[str] = (),
    team_statuses: Sequence[str | None] = (),
    attacker_item: ItemInfo | None = None,
    defender_item: ItemInfo | None = None,
    consumed_item: ItemInfo | None = None,
    observed_may_hold_item: bool = True,
    observed_types: tuple[str, ...] = (),
    attacker_stats: dict[str, int] | None = None,
    ally_ability: str | None = None,
    bench_hp_fractions: Sequence[float] = (),
) -> tuple[float, list[str]] | None:
    """What this move buys, or None if we genuinely cannot say.

    Returning None is meaningful: it means the effect depends on state nothing
    tracks, and the caller should fall back to its "unknown support move"
    value rather than to zero. Being unable to price a move is not the same as
    the move being worthless.
    """
    move_id = move.move_id
    reasons: list[str] = []

    if move_id in REDIRECTION_MOVES and (ally is None or ally.fainted):
        return 0.0, [f"{move.name} has no partner to draw attacks away from"]

    # ---------------------------------------------------------------- healing

    if move_id in WEATHER_HEALS:
        if weather in SUN:
            fraction, note = WEATHER_HEAL_SUN, "in sun"
        elif weather:
            fraction, note = WEATHER_HEAL_OTHER, f"weakened by {weather}"
        else:
            fraction, note = WEATHER_HEAL_CLEAR, "on a clear field"
        restored = min(fraction, _missing(attacker))
        if restored <= 0:
            return 0.0, ["already at full HP, so the healing is wasted"]
        return restored * SUSTAIN_WEIGHT, [f"restores ~{restored:.0%} of its HP ({note})"]

    if move_id == REST:
        restored = _missing(attacker)
        if restored <= 0:
            return 0.0, ["already at full HP, so Rest only costs turns"]
        value = restored * SUSTAIN_WEIGHT - REST_SLEEP_COST
        return value, [
            f"restores ~{restored:.0%} of its HP and cures its status",
            "but sleeps for two turns of about five",
        ]

    if move_id == PAIN_SPLIT and observed is not None and observed_stats:
        theirs = observed_stats.get("hp", attacker.max_hp) * observed.hp_percent / 100
        shared = (attacker.current_hp + theirs) / 2
        gained = (shared - attacker.current_hp) / max(1, attacker.max_hp)
        if gained <= 0:
            return 0.0, ["we are the healthier one, so Pain Split gives HP away"]
        return gained * SUSTAIN_WEIGHT, [f"takes ~{gained:.0%} of a health bar off them"]

    if move_id == STRENGTH_SAP and observed is not None and observed_stats:
        drained = min(observed_stats.get("atk", 0) / max(1, attacker.max_hp), _missing(attacker))
        dropped = -_headroom(observed.boosts, "attack", -1)
        value = drained * SUSTAIN_WEIGHT + dropped * STAT_STAGE_VALUE * STAT_STAGE_WEIGHT
        reasons.append(f"heals ~{drained:.0%} of its HP from their Attack")
        if dropped:
            reasons.append("and drops their Attack")
        return value, reasons

    if move_id == HEAL_PULSE:
        if ally is None:
            return 0.0, ["no ally to heal"]
        restored = min(HEAL_PULSE_FRACTION, _missing(ally))
        if restored <= 0:
            return 0.0, ["our ally is already at full HP"]
        return restored * SUSTAIN_WEIGHT, [f"heals our ally by ~{restored:.0%}"]

    # ------------------------------------------------------------ stat stages

    if move_id == BELLY_DRUM:
        gained = _headroom(attacker.boosts, "attack", MAX_STAGE)
        if not gained or _hp_fraction(attacker) <= BELLY_DRUM_COST:
            return 0.0, ["Belly Drum would fail here"]
        value = (
            gained * STAT_STAGE_VALUE * STAT_STAGE_WEIGHT
            - BELLY_DRUM_COST * SUSTAIN_WEIGHT
        )
        return value, [
            f"maximises Attack, {gained} stage(s) up",
            "at the cost of half a health bar",
        ]

    if move_id == HAZE:
        ours, theirs = _net_stages(attacker.boosts), 0
        if observed is not None:
            theirs = _net_stages(observed.boosts)
        gained = theirs - ours
        if gained == 0:
            return 0.0, ["there are no stat changes to clear"]
        return gained * STAT_STAGE_VALUE * STAT_STAGE_WEIGHT, [
            f"clears every stat change, worth {gained} net stage(s) to us"
        ]

    if move_id == PSYCH_UP and observed is not None:
        gained = _net_stages(observed.boosts) - _net_stages(attacker.boosts)
        if gained <= 0:
            return 0.0, ["their stat changes are no better than ours"]
        return gained * STAT_STAGE_VALUE * STAT_STAGE_WEIGHT, [
            f"copies their stat changes, {gained} stage(s) better than ours"
        ]

    if move_id == TOPSY_TURVY and observed is not None:
        net = _net_stages(observed.boosts)
        if net <= 0:
            return 0.0, ["inverting their stat changes would help them"]
        return 2 * net * STAT_STAGE_VALUE * STAT_STAGE_WEIGHT, [
            f"inverts their {net} net stage(s) of boosts"
        ]

    if move_id in STAGE_SWAPS and observed is not None:
        fields = STAGE_SWAPS[move_id]
        gained = sum(
            _stage(observed.boosts, field) - _stage(attacker.boosts, field)
            for field in fields
        )
        if gained <= 0:
            return 0.0, ["swapping those stages would not help us"]
        return gained * STAT_STAGE_VALUE * STAT_STAGE_WEIGHT, [
            f"takes {gained} net stage(s) from them"
        ]

    if move_id == ACUPRESSURE:
        # It only fails when *every* stat is already at the cap.
        if all(
            _stage(attacker.boosts, field) >= MAX_STAGE
            for field in BOOST_FIELDS.values()
        ):
            return 0.0, ["every stat is already maxed out"]
        gained = ACUPRESSURE_STAGES * STAT_STAGE_VALUE * STAT_STAGE_WEIGHT
        return gained, ["raises a random stat by two"]

    if move_id == PARTING_SHOT:
        value = 0.0
        if observed is not None:
            for field, delta in PARTING_SHOT_DROPS.items():
                dropped = -_headroom(observed.boosts, field, -delta)
                value += dropped * STAT_STAGE_VALUE * STAT_STAGE_WEIGHT
        reasons.append("drops their Attack and Special Attack")
        # It is a pivot as well as a debuff, and the first version priced only
        # the debuff -- which made it worth *less* than an unknown support move
        # and cost six labels of agreement. Getting something weakened out of
        # danger is worth what it is worth anywhere else.
        if _hp_fraction(attacker) <= LOW_HP_FRACTION:
            value += SWITCH_WHEN_WEAKENED_BONUS
            reasons.append("and pivots something weakened out of danger")
        else:
            reasons.append("and pivots out")
        return value, reasons

    if move_id == TIDY_UP:
        value = 0.0
        for field, delta in TIDY_UP_BOOSTS.items():
            value += (
                _headroom(attacker.boosts, field, delta)
                * STAT_STAGE_VALUE
                * STAT_STAGE_WEIGHT
            )
        swept = [c for c in own_side_conditions if c in HAZARDS]
        value += len(swept) * STAT_STAGE_VALUE * STAT_STAGE_WEIGHT
        reasons.append("raises our Attack and Speed")
        if swept:
            reasons.append(f"and clears {len(swept)} hazard(s) from our side")
        return value, reasons

    # ------------------------------------------------------- clearing the field

    if move_id == HEAL_BELL:
        cured = [s for s in team_statuses if s]
        if not cured:
            return 0.0, ["nobody on our team has a status to cure"]
        value = sum(STATUS_VALUE.get(s, 0.0) for s in cured) * STATUS_WEIGHT
        return value, [f"cures {len(cured)} status condition(s) on our team"]

    if move_id == DEFOG:
        ours = [c for c in own_side_conditions if c in HAZARDS]
        theirs = [c for c in opponent_side_conditions if c in SCREENS]
        cleared = len(ours) + len(theirs)
        if not cleared:
            return 0.0, ["there are no hazards or screens to clear"]
        return cleared * STAT_STAGE_VALUE * STAT_STAGE_WEIGHT, [
            f"clears {cleared} hazard(s) and screen(s)"
        ]

    if move_id in PHAZING and observed is not None:
        net = _net_stages(observed.boosts)
        value = max(0, net) * STAT_STAGE_VALUE * STAT_STAGE_WEIGHT
        reasons.append("forces them out")
        if net > 0:
            reasons.append(f"undoing {net} stage(s) they had set up")
        return value, reasons

    # ------------------------------------------------------------- held items

    if move_id == STUFF_CHEEKS:
        # The engine refuses the move outright without a Berry, so this is a
        # legality fact rather than a valuation.
        if not attacker_item or not attacker_item.is_berry:
            return 0.0, ["Stuff Cheeks needs a Berry to eat"]
        gained = _headroom(attacker.boosts, "defense", STUFF_CHEEKS_BOOST)
        return gained * STAT_STAGE_VALUE * STAT_STAGE_WEIGHT, [
            f"eats its {attacker_item.name} and raises Defense by {gained}"
        ]

    if move_id == CORROSIVE_GAS:
        if observed is not None and not observed_may_hold_item:
            return 0.0, ["they have nothing left to destroy"]
        return ITEM_DENIAL_VALUE, ["destroys the item they are holding"]

    if move_id in ITEM_SWAPS:
        # Worth doing when ours is a liability and theirs is not. With their
        # item unseen we cannot compare, and guessing here would be guessing
        # about the more important half.
        if observed is not None and not observed_may_hold_item and attacker_item:
            return 0.0, ["they have nothing to swap for"]
        if defender_item is None:
            return None
        return ITEM_DENIAL_VALUE, [f"takes their {defender_item.name}"]

    if move_id == RECYCLE:
        if consumed_item is None:
            return 0.0, ["there is no consumed item to bring back"]
        return ITEM_DENIAL_VALUE, [f"brings back its {consumed_item.name}"]

    if move_id == SWALLOW:
        layers = _stockpile_layers(attacker)
        if not layers:
            return 0.0, ["Swallow needs a Stockpile to eat"]
        restored = min(STOCKPILE_HEAL[layers], _missing(attacker))
        # Giving the stages back is part of the price, not a footnote.
        cost = layers * STOCKPILE_STAGES_LOST * STAT_STAGE_VALUE * STAT_STAGE_WEIGHT
        value = restored * SUSTAIN_WEIGHT - cost
        return value, [
            f"eats {layers} Stockpile layer(s) to restore ~{restored:.0%} of its HP",
            f"and hands back the {layers * STOCKPILE_STAGES_LOST} stage(s) it gained",
        ]

    if move_id == HEALING_WISH:
        if not bench_hp_fractions:
            return 0.0, ["nobody is left to send in"]
        neediest = min(bench_hp_fractions)
        gained = 1.0 - neediest
        spent = _hp_fraction(attacker)
        value = (gained - spent) * SUSTAIN_WEIGHT
        return value, [
            f"fully heals somebody sitting on ~{neediest:.0%}",
            f"at the cost of the ~{spent:.0%} this one still has",
        ]

    if move_id == WISH:
        restored = min(WISH_FRACTION, _missing(attacker))
        if restored <= 0:
            return 0.0, ["already at full HP, so the Wish would be wasted"]
        return restored * SUSTAIN_WEIGHT, [
            f"heals ~{restored:.0%} of a health bar at the end of next turn"
        ]

    if move_id in STAT_SPLITS:
        if observed is None or not observed_stats or not attacker_stats:
            return None
        gained = 0.0
        for key in STAT_SPLITS[move_id]:
            ours, theirs = attacker_stats.get(key), observed_stats.get(key)
            if ours is None or theirs is None:
                return None
            # A pure transfer: the average is what both end up with, so our
            # gain is exactly their loss.
            gained += ((ours + theirs) // 2) - ours
        if gained <= 0:
            return 0.0, ["our stats are already the better half of the average"]
        # Counted once, not twice: the same points leaving them and arriving
        # with us are one movement, and pricing both halves would double it.
        return gained * SPLIT_POINT_VALUE, [
            f"averages {' and '.join(STAT_SPLITS[move_id])} with them, "
            f"worth {gained:.0f} points to us"
        ]

    if move_id == MAGNETIC_FLUX:
        if ally is None or ally_ability not in MAGNETIC_FLUX_ABILITIES:
            return 0.0, ["nobody on our side has Plus or Minus"]
        gained = sum(
            _headroom(ally.boosts, field, delta)
            for field, delta in MAGNETIC_FLUX_BOOSTS.items()
        )
        if not gained:
            return 0.0, ["our ally's defences are already maxed out"]
        return gained * STAT_STAGE_VALUE * STAT_STAGE_WEIGHT, [
            f"raises our ally's defences by {gained} stage(s)"
        ]

    if move_id in TRAPPING_MOVES:
        if observed is None:
            return 0.0, ["nobody there to trap"]
        if UNTRAPPABLE_TYPE in observed_types:
            return 0.0, [f"a {UNTRAPPABLE_TYPE} type cannot be trapped"]
        if TRAPPED in observed.volatile_conditions:
            return 0.0, ["they are already trapped"]
        # Priced as the escape it denies, in the currency our own escapes use.
        # Something at full health was not leaving anyway, so trapping it buys
        # nothing this turn -- which is why this is not a flat value.
        if observed.hp_percent / 100 > LOW_HP_FRACTION:
            return 0.0, ["they are healthy enough that they were not leaving"]
        return SWITCH_WHEN_WEAKENED_BONUS, [
            "stops something weakened from escaping"
        ]

    if move_id == TEATIME:
        # Everything on the field eats its Berry, ours included. Whether that
        # is good depends on who is holding what, which is exactly the half we
        # cannot see.
        return None

    # Everything else genuinely depends on state we do not track.
    return None
