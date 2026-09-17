"""An agent that reasons about damage instead of guessing.

Scores every legal action and takes the best. The scoring is deliberately
readable rather than tuned: each component says something a player would say
out loud, and `explain()` returns those reasons, which is what the
recommendation system (Milestone 4) will need to show a human.

What it knows is limited to what a player knows. Opponent defensive stats are
never revealed (ADR 0002), so they are estimated from base stats under an
assumed investment -- a modelling choice to be replaced by inference in
Milestone 10, not a fact.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import combinations
from typing import NamedTuple

from champions_ai.agents.base import Agent
from champions_ai.agents.belief import OpponentBelief
from champions_ai.agents.currency import (
    DEFENSIVE_STATS,
    LOW_HP_FRACTION,
    STAT_STAGE_VALUE,
    STAT_STAGE_WEIGHT,
    STATUS_IMMUNE_TYPES,
    STATUS_VALUE,
    STATUS_WEIGHT,
    SUSTAIN_WEIGHT,
    SWITCH_WHEN_WEAKENED_BONUS,
)
from champions_ai.agents.support import REDIRECTION_MOVES, score_support_move
from champions_ai.agents.tenure import (
    OFFENSIVE_STATS,
    expected_tenure,
    offensive_boost_value,
    stage_multiplier,
)
from champions_ai.dex import Dex, MoveInfo, SpeciesInfo, to_id
from champions_ai.domain import (
    FIRST_TURN_MOVES,
    PROTECT_MOVES,
    JointAction,
    MoveAction,
    Observation,
    PassAction,
    PokemonSet,
    SlotAction,
    SwitchAction,
    TeamPreview,
    TeamPreviewAction,
)
from champions_ai.domain.boosts import BOOST_FIELDS, MAX_STAGE, MIN_STAGE
from champions_ai.mechanics import (
    ABILITY_MOVES,
    AFTER_YOU,
    BORROWING_MOVES,
    COPYCAT,
    INSTRUCT,
    MAX_BORROW_DEPTH,
    PARALYSIS,
    QUASH,
    REFLECT_TYPE,
    SLEEP_TALK,
    SPITE,
    TAILWIND,
    TRICK_ROOM,
    TURN_ORDER_MOVES,
    TYPE_CHANGING_MOVES,
    abilities_after,
    ability_move_succeeds,
    apply_boost,
    assumed_attacks,
    assumed_stats,
    attacking_side,
    copycat_borrows,
    dynamic_base_power,
    effective_speed,
    effective_types,
    estimate_damage,
    estimate_stats,
    gains_from_repeating,
    instruct_repeats,
    is_grounded,
    is_removable,
    matchup,
    move_priority,
    moves_first,
    ohko_chance,
    other_stat,
    retyped_by,
    sleep_talk_candidates,
    spite_removes,
    weather_on_arrival,
)
from champions_ai.mechanics.abilities import terrain_on_arrival
from champions_ai.mechanics.charge import (
    CHARGE_TURN_MULTIPLIER,
    RECHARGE_FLAG,
    charges_this_turn,
    recharge_multiplier,
)

# Scoring weights. Chosen to be legible rather than optimal: damage is the
# baseline currency, and everything else is priced relative to it.
DAMAGE_WEIGHT = 100.0
GUARANTEED_KO_BONUS = 120.0
POSSIBLE_KO_BONUS = 30.0
# Hitting your own partner is almost never intended, and a spread move that
# happens to catch them is priced separately by the damage term anyway.
ALLY_DAMAGE_PENALTY = -250.0
IMMUNE_PENALTY = -60.0
RESISTED_PENALTY = -15.0
# The fallback for the 56 status moves whose effects live in an `onHit`
# callback the engine cannot dump. Fitted from 12 up to 30: humans reach for
# Belly Drum, Haze, Defog and Baton Pass far more than a token value implied,
# so "unknown" should not mean "probably not worth it".
STATUS_MOVE_VALUE = 30.0

# Protect's three were hand-chosen in experiment 0003 and fitted in 0010: the
# agreement curve has a sharp peak at this combination (44.5% at a tempo cost
# of -60, 45.7% at -160, 44.7% at -260). Together they say something specific
# and legible: protect only against a *large* incoming hit, because the turn it
# costs is expensive. The knockout bonus is flat anywhere between 0 and 40, so
# it keeps a positive value on the grounds that surviving a knockout plainly
# matters even where agreement cannot see it.
#
# Protect is priced as damage *avoided*, in the same currency as damage dealt,
# so the two compete on equal terms instead of Protect carrying a flat value
# that almost any attack outbids. Measured against real humans (experiment
# 0002), the flat value made the heuristic protect almost never: 90 of 643
# disagreements were a human protecting where it attacked.
PROTECT_DAMAGE_WEIGHT = 430.0
# Surviving a knockout is worth less than landing one -- you keep a Pokemon,
# but you have not removed theirs.
PROTECT_SAVES_KO_BONUS = 40.0
# Attacking advances the game and protecting does not, so blocking N% of your
# HP is worth slightly less than dealing N% of theirs.
PROTECT_TEMPO_COST = -160.0


# A flinch denies the target its whole turn. Priced above a single status
# because it is immediate and unconditional once it lands -- but it is worth
# nothing at all unless we move first, which is where most of its subtlety is.
FLINCH_VALUE = 0.40
FLINCH_WEIGHT = 100.0

# --- what a status move that is not Protect is worth -------------------------
#
# Three of these are *not* new judgements. A stat stage is priced with
# STAT_STAGE_VALUE, a status with STATUS_VALUE and healing with SUSTAIN_WEIGHT,
# which are the same numbers the damaging path already uses for the same
# things -- so Swords Dance is worth what a Swords Dance rider is worth, and a
# Recover is worth what a drain of the same size is worth. Nothing about a
# move being "a status move" changes what it buys.
#
# The tables below are judgements in the same sense STATUS_VALUE is, and are
# priced as a fraction of a health bar for the same reason: so they compete
# with damage on equal terms rather than sitting on a separate scale.
#
# They were then *fitted* by coordinate descent against human agreement on the
# training half of the corpus, and reported on the test half, which the sweep
# never saw (experiment 0010). The test gain came out larger than the training
# gain, which is the sign that they generalise rather than memorise.

# Which targets mean "our side". Boosts land on the move's target, so a Swords
# Dance and a Growl carry the same field with opposite meanings.
SELF_TARGETS = frozenset(
    {
        "self",
        "adjacentAlly",
        "adjacentAllyOrSelf",
        "allies",
        "allySide",
        "allyTeam",
    }
)

# A screen halves damage for several turns. Priced off the incoming threat the
# way Protect is, rather than flat: a screen with nothing to block is worth
# nothing, and one in front of a knockout is worth a great deal.
SCREEN_CONDITIONS = frozenset({"reflect", "lightscreen", "auroraveil"})
SCREEN_TURNS = 3.0
SCREEN_FRACTION_BLOCKED = 0.5
SCREEN_WEIGHT = 30.0

# Everything else a move can put on a side. Hazards are deliberately cheap:
# this is a four-Pokemon format where rated humans switch on 11.8% of decisions
# and this agent on 4.4%, so a hazard collects far less than it would in
# singles.
#
# The "about five turns" this used to say was measured on the singles-generated
# pool 0024 replaced; harvested teams run thirteen. That staleness is what made
# Tailwind worth re-pricing, and 0036 swept it from 0 to 8 without finding
# anything better than the values below.
SIDE_CONDITION_VALUE = {
    "tailwind": 45.0,
    "safeguard": 15.0,
    "mist": 8.0,
    "stealthrock": 10.0,
    "spikes": 7.0,
    "toxicspikes": 7.0,
    "stickyweb": 10.0,
    "luckychant": 5.0,
}

# Weather and terrain are worth something to a team built around them and
# little to one that is not, which this cannot see. A modest flat value is the
# honest placeholder rather than a confident number.
WEATHER_VALUE = 26.0
TERRAIN_VALUE = 14.0
# Trick Room is capped deliberately. Agreement keeps rising with it all the way
# to 5,000, because a team that brought Trick Room nearly always uses it -- so
# the fit degenerates from "worth this much" into "always do this". An agent
# that recommends Trick Room regardless of the matchup would be wrong in a way
# human agreement cannot see, so this stays a valuation.
PSEUDO_WEATHER_VALUE = {"trickroom": 55.0, "gravity": 12.0}
PSEUDO_WEATHER_DEFAULT = 10.0

# Volatiles inflicted on an opponent, ordered by how much of a turn they take
# away. Taunt was fitted to 50 (a real peak); Encore and Leech Seed were left
# where they were, because the agreement curve is flat across their whole
# plausible range and moving them would be fitting noise. Taunt and Encore
# remove a choice outright; Leech Seed is chip damage with a heal attached.
VOLATILE_VALUE = {
    "taunt": 50.0,
    "encore": 30.0,
    "yawn": 30.0,
    "leechseed": 26.0,
    "confusion": 25.0,
    "disable": 22.0,
    "attract": 18.0,
    "torment": 14.0,
    "healblock": 14.0,
    "embargo": 8.0,
    "telekinesis": 5.0,
}
# Ours, on ourselves.
SELF_VOLATILE_VALUE = {"substitute": 28.0, "aquaring": 14.0, "ingrain": 10.0, "focusenergy": 12.0}
VOLATILE_DEFAULT = 12.0

# Low enough that anything else legal is preferred, without being so
# extreme that it swamps a whole joint action's score.
UNUSABLE_MOVE_SCORE = -200.0

# How a Team Preview pick is judged. A team is not a collection of good
# Pokemon, it is a set of *answers*: what matters is having something for each
# thing they brought, not maximising an average.
COVERAGE_WEIGHT = 1.0
# A small pull towards picks that are good on average, to break ties between
# two sets with the same worst case.
AVERAGE_WEIGHT = 0.25
# Switching costs a turn and buys a better position. Priced flatly, which is
# crude and known to be crude: rated humans switch on 11.5% of decisions and
# this agent on 1.8%.
#
# A matchup-based replacement was built, measured and **reverted** -- see
# docs/experiments/0004. It tripled switch agreement (6.8% -> 23.2%) and still
# came out worse on every other measure: 3.4 points of overall agreement
# (McNemar chi2 = 172 on 11,133 labels), worse against Random (96.7% against
# 99.0%), and a head-to-head edge that did not survive being re-run at higher
# power. Switching remains an open problem, not a solved one.
# Matchup switching, **on**, at a horizon of 2. Experiment 0032.
#
# This question was answered wrongly three times, and every wrong answer came
# from testing a single horizon rather than sweeping one. On the fixed harness
# the curve is monotone and crosses even between 2 and 4:
#
#   horizon  2.0   57.8%  p = 0.013     switch rate  4.4%
#   horizon  3.0   57.3%  p = 0.011     switch rate  5.9%
#   horizon  4.0   50.2%  p = 0.95
#   horizon  8.0   42.9%  p = 0.016
#   horizon 16.0   39.6%  p = 0.000
#
# 0004 tuned the horizon to reproduce the *human* switch rate and landed at a
# setting deep in the harmful region; 0027 tested horizon 8, also harmful, and
# concluded the agent's near-zero rate was correct. Both were measuring a real
# effect at the wrong point on the curve.
#
# Confirmed on three independent seed sets -- 56.1%, 57.8%, 55.4% -- with the
# middle one pre-registered before it ran. Against Random it costs one matchup
# in 1,704 (99.9% against the flat cost's 100.0%), which settles the third
# objection 0004 raised and nothing since had re-examined.
#
# The rate this produces is 4.4%, against 0.27% for the flat cost and 11.8% for
# rated humans. Both ends were wrong: chasing the human rate overshoots badly,
# and the flat cost barely switches at all.
# Redirection draws the opponent's single-target attacks onto the user and off
# the partner. It does not remove the damage, it *moves* it, so the flat 30 it
# used to collect (the unknown-support fallback) priced the wrong thing --
# exactly the mistake 0032 found in switching, where a constant stood in for a
# trade.
#
# What it actually buys is the difference in how much the hit costs. Both
# threats are fractions of their own bearer's health bar, so an attack taking
# 60% of a frail partner and 30% of a bulky redirector converts a 60% loss into
# a 30% one -- and a partner that would faint into one that does not.
#
# Swept, and it loses. Experiment 0033, on the fixed harness, priced against
# the shipped unpriced agent -- the paired figure is over the matchups the two
# actually decided differently, which is only about 3% of them:
#
#   weight  4    23.5%   p = 0.029        weight 16    24.0%   p = 0.009
#   weight  8    25.0%   p = 0.025        weight 32    26.7%   p = 0.011
#
# Negative at every weight that changes a decision, with and without a tempo
# cost for the turn it spends. So **zero ships**, and zero means *unchanged*:
# the scorer bows out and the move collects the flat unknown-support value it
# always did. Kept constructible so the result can be re-checked rather than
# taken on trust.
#
# Worth knowing before anyone tries again: the ceiling is small either way.
# Pricing it at all only changes 17-31 matchups in 798, so even a version that
# worked could be worth at most about a point of win rate.
REDIRECT_WEIGHT = 0.0

SWITCH_HORIZON = 2.0
# Saving a Pokemon that would otherwise be knocked out is worth roughly what
# losing it would cost: a slot, an attacker and a switch option at once.
SWITCH_SAVES_KO_BONUS = 35.0

SWITCH_COST = -25.0

# High Jump Kick, Axe Kick and Supercell Slam take half the user's maximum HP
# when they miss. The engine spells it `baseMaxhp / 2`.
CRASH_DAMAGE_FRACTION = 0.5

# The one special mechanic Reg M-B enables.
MEGA = "mega"
LOCK_ON = "lockon"


class _BestMove(NamedTuple):
    """One of our own moves, with what the scorer made of it."""

    move: MoveInfo
    score: float
    knocks_out: bool


@dataclass(frozen=True)
class ScoredAction:
    """One action, its score, and why."""

    action: SlotAction
    score: float
    reasons: tuple[str, ...] = field(default=())
    # What this action does, and to whom. Needed because the joint score is a
    # sum of independent slots, and two attacks aimed at the same Pokemon are
    # not independent: their damage combines, and their knockout bonuses
    # overlap.
    target_index: int | None = None
    damage_fraction: float = 0.0
    knockout_bonus: float = 0.0


def _mega_count(joint: JointAction | None) -> int:
    """How many slots of a joint action Mega Evolve (0 or 1 in practice)."""
    if joint is None:
        return 0
    return sum(1 for action in joint.slot_actions if getattr(action, "special", None) == MEGA)


def _combined_targets(scored: Sequence[ScoredAction]) -> float:
    """Correct the knockout bonus for slots aimed at the same Pokemon.

    The joint score is a sum of independently scored slots, which cannot see
    that two attacks land on one target. That is wrong in both directions:

    - **Overkill.** Two guaranteed knockouts on the same Pokemon each collect
      the full bonus, so the agent was *rewarded* for wasting an attack.
    - **Focus fire.** Two attacks that each take half a health bar remove a
      Pokemon between them and collected nothing for it, because neither is a
      knockout on its own.

    So the bonus is recomputed once per target from the combined damage, and
    what the slots already claimed is taken back off.
    """
    by_target: dict[int, list[ScoredAction]] = {}
    for entry in scored:
        if entry.target_index is None:
            continue
        by_target.setdefault(entry.target_index, []).append(entry)

    adjustment = 0.0
    for entries in by_target.values():
        if len(entries) < 2:
            continue
        claimed = sum(entry.knockout_bonus for entry in entries)
        combined = sum(entry.damage_fraction for entry in entries)
        if combined >= 1.0:
            deserved = GUARANTEED_KO_BONUS
        else:
            deserved = max(entry.knockout_bonus for entry in entries)
        adjustment += deserved - claimed
    return adjustment


class ResolvedTarget(NamedTuple):
    """What a move is aimed at, with the stats that move will read off it.

    Named rather than a bare tuple because the last field is conditional: it
    holds a value only for a move whose attacking stat comes from this side of
    the field, and `_, _, _, _, x = target` would say nothing about that.
    """

    species: SpeciesInfo
    remaining_hp: int
    defending_stat: int
    is_ally: bool
    # Set only for Foul Play, which swings with the target's Attack rather
    # than the user's. None means "the user's own stat applies", which is
    # every other move.
    attacking_stat: int | None = None
    # Hex and Infernal Parade double against a target carrying any status.
    status: str | None = None
    # A resist berry halves the hit it fires on. None means "none that we know
    # of", which for an opponent is the honest answer until they show it.
    item: str | None = None
    # Sticky Hold refuses to give the item up, so Knock Off gets no boost.
    ability: str | None = None
    # False only when we watched an item leave. An opponent we have learnt
    # nothing about is assumed to be holding something, because they usually
    # are.
    may_hold_item: bool = True
    # A Focus Sash and Sturdy both need the holder at full health.
    at_full_hp: bool = False
    # One-turn effects, most importantly Roost, which strips the Flying type.
    volatiles: tuple[str, ...] = ()
    # Where this Pokemon sits in the opponent's revealed list, so two slots
    # aiming at the same one can be recognised as doing so.
    index: int | None = None
    # How long it has been out. Stakeout doubles against a Pokemon on the
    # turn it arrives. Defaults to 1 -- 'has been out a while' -- so a
    # target built without it is never handed the boost.
    turns_on_field: int = 1


class HeuristicAgent(Agent):
    """Picks the highest-scoring legal action.

    Needs a `Dex` because a player who could not read type matchups or move
    power would not be playing a heuristic at all.
    """

    def __init__(
        self,
        dex: Dex,
        *,
        name: str = "heuristic",
        # 11, not 12: six stats at 12 is 72 points, over Reg M-B's budget of
        # 66, so the old default modelled every opponent with a spread that
        # cannot legally exist. Uniform beats concentrated priors against real
        # damage (0.89x versus 1.14-1.18x), so the shape stays.
        assumed_opponent_points: int = 11,
        # Inference is opt-in until it has earned its place. Experiment 0018
        # put the whole ceiling at +4.3 points, so this is a modest effect that
        # has to be measured rather than assumed.
        infer_spreads: bool = False,
        # Species id -> the ability the corpus says it almost always runs, from
        # `data.priors`. Empty means "behave exactly as before", and it is
        # opt-in for the same reason `infer_spreads` is: it changes what the
        # agent believes about an opponent, and this project does not ship
        # unproven changes to the shipped agent.
        #
        # A *revealed* ability always wins over it -- see `_known_ability`.
        # The prior only fills the gap where there was nothing.
        ability_priors: dict[str, str] | None = None,
        # Species id -> (effect, kind, probability): the field an opponent's
        # previewed Pokemon is likely to put up, from `data.priors`. Used
        # only at Team Preview, which is the one moment we see six Pokemon
        # and none of them has been on the field. Opt-in, and measured
        # before it ships -- see experiments/0048.
        field_priors: dict[str, tuple[str, str, float]] | None = None,
        # Off by default: measured at +0.9 points over 1,600 battles, 95% CI
        # 48.4%-53.3%, p = 0.48. That is neutral, not an improvement, and this
        # project does not ship unproven changes to the shipped agent. The code
        # stays because the finding it rests on is solid -- setup moves are
        # roughly break-even here, which is worth knowing and worth being able
        # to re-measure -- and because pricing a stat stage in damage terms is
        # machinery the position evaluator needs next.
        tenure_boosts: bool = False,
        # On by default since 0032, at SWITCH_HORIZON = 2. The flag stays so
        # the flat cost remains constructible for comparison.
        matchup_switching: bool = True,
        # Whether the switch scorer is told what field is actually up.
        #
        # It was not. `_matchup_against_field` had the `Observation` in hand and
        # passed neither `weather` nor `terrain` to `matchup()`, while this file
        # threads `observation.weather` into eleven other call sites and
        # `observation.terrain` into six. So in rain it priced their Fire move
        # at full and decided whether to switch on a battle nobody was playing.
        #
        # Second lap of one bug: `tracker._on_minor_fieldstart` still carries
        # the comment about `terrain` being "declared, read into every
        # Observation and never once assigned". That fix made the field real.
        # This consumer never started reading it.
        #
        # Unlike `ability_priors` and `field_priors`, which are guesses and are
        # off until measured, this is a fact the agent already has -- so it is
        # **on** by default, and 0049 sizes it rather than deciding it. The flag
        # stays so the bare-field behaviour remains constructible, the way
        # `matchup_switching` kept the flat cost after 0032.
        field_aware_switching: bool = True,
        # Whether a move that spends this turn charging is priced as the turn it
        # charges rather than as the hit it eventually lands.
        #
        # `MoveInfo.flags` has carried the engine's `charge` flag since the dex
        # loader was written, and nothing read it -- so Solar Beam and Electro
        # Shot (6.8% and 11.1% of pool teams) were a full hit on the turn the
        # engine spends charging. The rules are `mechanics.charge`, transcribed
        # from `data/moves.ts`.
        #
        # An engine fact, so on by default like `field_aware_switching`; 0050
        # sizes it. The flag keeps the old pricing constructible.
        charge_turns: bool = True,
        # The mirror image: a move that hits now and costs the next turn
        # recharging. The engine's `recharge` flag was loaded and never read, so
        # a recharge move was priced as a free hit. Priced at
        # `recharge_multiplier` -- 1 / (1 + accuracy), since a miss costs no
        # recharge. An engine fact, so on; 0054 sizes it.
        recharge_turns: bool = True,
        # Whether Trick Room is priced by what flipping the speed order does for
        # *us*, rather than at a flat value that ignores who is faster.
        #
        # Two things were wrong with the flat price. It paid the same for
        # setting Trick Room with a fast team as with a slow one. And it scored
        # Trick Room at nothing when it was already up -- but the engine's
        # `onFieldRestart` calls `removePseudoWeather('trickroom')`, so using it
        # then *ends* it, which is worth a great deal when the opponent set it.
        #
        # Off by default: the mechanic is a fact, but pricing it is a judgement,
        # and this project does not ship unmeasured judgements. See 0051.
        trick_room_by_speed: bool = False,
        # Team Preview scores a Pokemon holding its own Mega Stone as the Mega it
        # becomes. It scored the base forme, so a Mega's whole reason to be
        # brought was invisible to the pick. Only one Pokemon Mega Evolves per
        # battle and 23.8% of pool teams hold two or more stones, so each
        # selection has exactly one holder evolve. On by default: our own items
        # are known, so this is a fact about our team rather than a guess.
        own_megas: bool = True,
        # Base species id -> (Mega forme, rate), from
        # `data.priors.build_mega_priors`: how often the species Mega Evolves
        # once it is on the field. With several holders in one selection, the
        # one players evolve more often is the one assumed to evolve -- which is
        # how players actually choose. Without it, the agent tries each.
        mega_priors: dict[str, tuple[str, float]] | None = None,
        # Whether Team Preview allows that an opponent may Mega Evolve. Their
        # items are hidden, so every previewed species was scored as its base
        # forme -- a species that evolves 90% of the time it takes the field was
        # rated as though it never did. On, each cell against a species in
        # `mega_priors` is its base matchup moved toward its Mega matchup by the
        # measured rate. Off by default: the rate is a prior, and priors are
        # measured before they ship. See 0052.
        opponent_megas: bool = False,
        # Whether `matchup()` is told our own ability and item. It never was,
        # so Team Preview and every switch decision scored our Pokemon as
        # holding nothing, with no ability, and compared Speed on the raw stat.
        # On by default: our set is known, so this is a fact rather than a guess.
        matchup_reads_our_set: bool = True,
        # Whether Team Preview scores each candidate four in the weather and
        # terrain its own setters put up. It scored every four on bare ground,
        # so a team built around its own weather was ranked as though it never
        # set any. Our abilities are known and they set the field on arrival, so
        # on by default; the simplifications are in `_own_field`.
        own_field: bool = True,
        # Whether `matchup()` prices a charge move charging now and a recharge
        # move per turn they commit, as the move scorer already does. It priced
        # both as free, instant hits, overrating at Team Preview and when
        # switching any Pokemon whose best move was one. An engine fact, so on;
        # 0054 sizes it.
        matchup_turn_costs: bool = True,
        # Whether `matchup()` values moving first over a race of any length.
        # It only counted a one-hit knockout race, so a Pokemon that outspeeds
        # the field but rarely knocks out in one hit got nothing for its speed.
        # The race model is a judgement -- no switching, Protect or partners --
        # so off until measured. See 0055.
        speed_beyond_knockouts: bool = False,
        # With `speed_beyond_knockouts`, the share of a denied hit credited in
        # a race longer than one hit. 1.0 is 0055's rule, which over-valued
        # speed; 0056 sweeps smaller values.
        speed_race_credit: float = 1.0,
        # A joint action that Mega Evolves and scores exactly the same as the
        # best that does not -- a Protect turn, a move the forme does not
        # strengthen -- is taken instead of it. The one-turn scorer cannot
        # price a permanent upgrade, so these ties went to the non-Mega by
        # enumeration order alone. Players Mega on a Pokemon's first turn out
        # 88.9% of the time (Reg M-C corpus). A judgement, so off until
        # measured; see 0060.
        mega_on_ties: bool = False,
        # Per-agent so a sweep can put a priced agent against an unpriced one.
        # As a module global it was read by *both* sides of a head-to-head, so
        # every setting compared an agent with itself and tied every matchup --
        # which reads exactly like a null.
        redirect_weight: float | None = None,
        # Scales Tailwind and Trick Room. Swept in 0036 across 0 to 8 and
        # nothing beat the shipped 1.0; the leading candidate, never using them
        # at all, came back 53.4% with p = 0.56 on fresh seeds. Kept so the
        # result can be re-checked rather than taken on trust -- and because
        # "scale 0 is indistinguishable from the shipped price" is a mildly
        # uncomfortable fact somebody should be able to poke at again.
        speed_control_scale: float = 1.0,
        # How far the status scorer is trusted against the damage scorer.
        #
        # Opened because `review --all` found the disagreement with rated
        # players is a whole category rather than a move: Charm 3%, Disable 4%,
        # Hypnosis 4%, Will-O-Wisp 4%, Reflect 5%, Substitute 6%, Roost 8%,
        # Calm Mind 8%, Swords Dance 8%, Yawn 8%, Parting Shot 8% agreement,
        # on 44 to 449 plays each. Humans reach for non-damaging moves far more
        # than this agent ranks them.
        #
        # A scalar rather than the `tenure_boosts` flag next to it, because the
        # flag is the shape 0032 warned about: switching was called a null
        # three times by testing one setting each time, and the answer changed
        # the moment it was swept. Per-agent for 0033's reason -- as a module
        # global both sides of a head-to-head read it and every matchup ties.
        status_scale: float = 1.0,
    ) -> None:
        self.dex = dex
        self.name = name
        self.assumed_opponent_points = assumed_opponent_points
        self.infer_spreads = infer_spreads
        self.ability_priors = ability_priors or {}
        self.field_priors = field_priors or {}
        self.tenure_boosts = tenure_boosts
        self.matchup_switching = matchup_switching
        self.field_aware_switching = field_aware_switching
        self.charge_turns = charge_turns
        self.recharge_turns = recharge_turns
        self.trick_room_by_speed = trick_room_by_speed
        self.own_megas = own_megas
        self.mega_priors = mega_priors or {}
        self.opponent_megas = opponent_megas
        self.matchup_reads_our_set = matchup_reads_our_set
        self.own_field = own_field
        self.matchup_turn_costs = matchup_turn_costs
        self.speed_beyond_knockouts = speed_beyond_knockouts
        self.speed_race_credit = speed_race_credit
        self.mega_on_ties = mega_on_ties
        self.redirect_weight = (
            REDIRECT_WEIGHT if redirect_weight is None else redirect_weight
        )
        self.speed_control_scale = speed_control_scale
        self.status_scale = status_scale
        self.belief = OpponentBelief(dex) if infer_spreads else None
        # What the field looked like when we last chose, and what we chose.
        # Diffing the two is the only way an agent sees damage: it is handed
        # `Observation`s, never protocol.
        self._previous: Observation | None = None
        self._last_action: JointAction | None = None

    def on_battle_start(self) -> None:
        if self.infer_spreads:
            self.belief = OpponentBelief(self.dex)
        self._previous = None
        self._last_action = None

    # ------------------------------------------------------------- selection

    def select_action(
        self, observation: Observation, legal_actions: Sequence[JointAction]
    ) -> JointAction:
        if self.belief is not None:
            self._learn_from(observation)
        best, best_score = None, float("-inf")
        # Joint actions are products of per-slot choices, so the same slot
        # action recurs many times; scoring it once keeps this linear in the
        # number of distinct choices rather than their product.
        cache: dict[tuple[int, SlotAction], ScoredAction] = {}

        for joint in legal_actions:
            scored = [
                self._cached(observation, slot, action, cache)
                for slot, action in enumerate(joint.slot_actions)
            ]
            total = sum(s.score for s in scored) + _combined_targets(scored)
            if total > best_score or (
                self.mega_on_ties
                and total == best_score
                and _mega_count(joint) > _mega_count(best)
            ):
                best, best_score = joint, total

        assert best is not None, "legal_actions must not be empty"
        # Kept so the next turn can diff against it: an agent is handed
        # `Observation`s, never protocol, so the only way it sees damage is by
        # comparing what the field looked like when it last chose.
        self._previous, self._last_action = observation, best
        return best

    def explain(self, observation: Observation, action: JointAction) -> tuple[ScoredAction, ...]:
        """Per-slot scores and reasons for a chosen action."""
        return tuple(
            self.score_slot_action(observation, slot, slot_action)
            for slot, slot_action in enumerate(action.slot_actions)
        )

    def _cached(
        self,
        observation: Observation,
        slot: int,
        action: SlotAction,
        cache: dict[tuple[int, SlotAction], ScoredAction],
    ) -> ScoredAction:
        key = (slot, action)
        if key not in cache:
            cache[key] = self.score_slot_action(observation, slot, action)
        return cache[key]

    # --------------------------------------------------------------- scoring

    def score_slot_action(
        self, observation: Observation, slot: int, action: SlotAction
    ) -> ScoredAction:
        if isinstance(action, PassAction):
            return ScoredAction(action, 0.0, ("nothing to do",))
        if isinstance(action, SwitchAction):
            return self._score_switch(observation, slot, action)
        return self._score_move(observation, slot, action)

    def _score_switch(
        self, observation: Observation, slot: int, action: SwitchAction
    ) -> ScoredAction:
        """A flat cost, plus a bonus for rescuing something nearly dead.

        Deliberately unsophisticated. The matchup-based version this replaced
        is recoverable from git history and documented in experiment 0004; it
        was reverted on evidence, not abandoned for lack of one.
        """
        if self.matchup_switching:
            return self._score_switch_on_matchup(observation, slot, action)

        attacker = self._own_active(observation, slot)
        if attacker is None:
            # The slot is empty, so this is a forced replacement rather than a
            # choice to give up momentum.
            return ScoredAction(action, 0.0, ("filling an empty slot",))

        score = SWITCH_COST
        reasons = ["switching costs a turn"]
        if attacker.hp_fraction <= LOW_HP_FRACTION:
            score += SWITCH_WHEN_WEAKENED_BONUS
            reasons.append(f"{attacker.pokemon_set.species} is weakened")
        return ScoredAction(action, score, tuple(reasons))

    def _score_switch_on_matchup(
        self, observation: Observation, slot: int, action: SwitchAction
    ) -> ScoredAction:
        """Worth the matchup it buys, minus the turn and the free hit it costs.

        The old scoring was a flat cost plus a bonus when weakened, which made
        switching almost never worth it: measured against rated humans, they
        switched on 11.0% of decisions and this agent on 1.7%, agreeing on 8 of
        117 switch labels.
        """
        incoming = observation.own_side.team[action.team_index]
        current = self._own_active(observation, slot)

        if current is None:
            # An empty slot must be refilled, so there is no turn to give up
            # and nothing to compare against -- only which Pokemon is best
            # placed against what is on the field.
            replacement = self._matchup_against_field(observation, incoming)
            return ScoredAction(
                action,
                replacement * DAMAGE_WEIGHT,
                (f"{incoming.pokemon_set.species} is best placed to come in",),
            )

        staying = self._matchup_against_field(observation, current)
        coming_in = self._matchup_against_field(observation, incoming)

        gain = (coming_in - staying) * SWITCH_HORIZON * DAMAGE_WEIGHT
        reasons = [
            f"{incoming.pokemon_set.species} matches up "
            f"{'better' if coming_in > staying else 'worse'} than "
            f"{current.pokemon_set.species}"
        ]

        # Giving up this turn's attack is the price, and it is only a price if
        # there was something worth attacking.
        forgone, _, _ = self._best_offence(observation, slot, current)
        score = gain - forgone * DAMAGE_WEIGHT
        if forgone > 0:
            reasons.append(f"but gives up a ~{forgone:.0%} hit this turn")

        threat, would_ko, _ = self._incoming_threat(observation, slot, current)
        if would_ko:
            score += SWITCH_SAVES_KO_BONUS
            reasons.append(f"and saves {current.pokemon_set.species} from a knockout")
        elif threat >= current.hp_fraction:
            score += SWITCH_SAVES_KO_BONUS * 0.5
            reasons.append(f"{current.pokemon_set.species} may not survive the turn")

        return ScoredAction(action, score, tuple(reasons))

    def _matchup_against_field(self, observation: Observation, mon) -> float:
        """Our net matchup against the live opponents, from this Pokemon.

        Averaged rather than maximised: in doubles both of them get to act, so
        being excellent against one and helpless against the other is not the
        same as being solid against both.
        """
        scores = []
        opponent = observation.opponent_side
        for index in opponent.active_slots:
            if index is None:
                continue
            observed = opponent.revealed[index]
            if observed.fainted:
                continue
            try:
                species = self.dex.get_species(observed.species)
            except KeyError:
                continue
            revealed = [m for m in self._revealed_moves(observed) if m.is_damaging]
            estimated = estimate_stats(species.base_stats, self.assumed_opponent_points)
            scores.append(
                matchup(
                    self.dex,
                    mon.pokemon_set,
                    species,
                    level=observation.regulation.level,
                    doubles=observation.regulation.game_type == "doubles",
                    assumed_points=self.assumed_opponent_points,
                    our_stats=mon.computed_stats or None,
                    our_hp=max(1, mon.current_hp),
                    their_hp=max(1, estimated["hp"] * observed.hp_percent // 100),
                    their_moves=revealed or None,
                    # The field we are actually standing on. Deciding whether to
                    # switch means comparing two Pokemon on *this* battle's
                    # ground: in rain their Water move is the threat and our
                    # Fire answer is not an answer.
                    weather=observation.weather if self.field_aware_switching else None,
                    terrain=observation.terrain if self.field_aware_switching else None,
                    # The battle's current ability and item, not the set's: an
                    # item can be consumed or knocked off, and an ability swapped.
                    our_ability=mon.current_ability if self.matchup_reads_our_set else None,
                    our_item=mon.current_item if self.matchup_reads_our_set else None,
                    price_turn_costs=self.matchup_turn_costs,
                    speed_beyond_knockouts=self.speed_beyond_knockouts,
                    speed_race_credit=self.speed_race_credit,
                ).net
            )
        return sum(scores) / len(scores) if scores else 0.0

    def _best_offence(
        self, observation: Observation, slot: int, attacker
    ) -> tuple[float, str | None, bool]:
        """The best damaging move available to this slot right now."""
        best, name, ko = 0.0, None, False
        for index, move_id in enumerate(attacker.selectable_moves):
            if move_id in attacker.disabled_moves:
                continue
            try:
                move = self.dex.get_move(move_id)
            except KeyError:
                continue
            if not move.is_damaging:
                continue
            scored = self._score_move(observation, slot, MoveAction(move_index=index))
            if scored.score > best * DAMAGE_WEIGHT:
                best = max(best, scored.score / DAMAGE_WEIGHT)
                name, ko = move.name, False
        return max(0.0, min(best, 1.0)), name, ko

    def _score_move(self, observation: Observation, slot: int, action: MoveAction) -> ScoredAction:
        attacker = self._own_active(observation, slot)
        if attacker is None:
            return ScoredAction(action, 0.0, ("no active Pokemon",))

        if action.move_index >= len(attacker.selectable_moves):
            # A reconstructed replay knows only the moves it saw used, so an
            # index can outrun the list. Neutral rather than a crash: an
            # unknown move is a gap in the data, not a reason to rank it.
            return ScoredAction(action, 0.0, ("no move at that index",))
        move_id = attacker.selectable_moves[action.move_index]
        try:
            move = self.dex.get_move(move_id)
            attacker_species = self.dex.get_species(attacker.pokemon_set.species)
        except KeyError as error:
            # Unknown data is a gap to fix, not a reason to prefer or avoid the
            # move, so it scores neutrally rather than silently ranking last.
            return ScoredAction(action, 0.0, (f"no data: {error}",))
        return self._score_chosen_move(observation, slot, action, move, attacker, attacker_species)

    def _score_chosen_move(
        self,
        observation: Observation,
        slot: int,
        action: MoveAction,
        move: MoveInfo,
        attacker,
        attacker_species: SpeciesInfo,
        borrow_depth: int = 0,
    ) -> ScoredAction:
        """Score `move` used from `slot`, whatever action nominally chose it.

        Split out of `_score_move` so Copycat, Sleep Talk and Instruct can be
        priced as the move they stand in for rather than as generic support --
        they go through this with a substituted `move`, and everything they
        borrow is therefore scored by exactly the same arithmetic as if it had
        been picked directly.
        """
        # A Mega action is the same move thrown by a different Pokemon, so it
        # is scored as that Pokemon. Everything below -- damage, typing,
        # ability, speed -- then follows without a special case of its own.
        # The weather this move will actually be thrown in. Usually the field's,
        # but a Mega whose forme sets weather on arrival has it up before it
        # attacks: the queue runs `megaEvo` (104) before moves (200), and
        # `formeChange` hands the forme its ability through `setAbility`, which
        # fires `Start`. Scoring the Mega turn in the old weather priced the
        # one turn the forme changes the field as though it did not.
        move_weather = observation.weather
        if action.special == MEGA and borrow_depth == 0:
            became = self._mega_form(attacker, attacker_species)
            if became is not None:
                attacker_species, attacker = became
                move_weather = weather_on_arrival(attacker.current_ability) or move_weather

        if move.move_id in FIRST_TURN_MOVES and attacker.turns_on_field > 1:
            # The engine refuses these outright after the first turn out, and
            # it does so at runtime rather than reporting them as disabled, so
            # nothing upstream filters them for us.
            return ScoredAction(
                action,
                UNUSABLE_MOVE_SCORE,
                (f"{move.name} only works on its first turn out",),
            )

        if not move.is_damaging:
            scored = self._score_status_move(
                observation, slot, action, move, attacker, borrow_depth
            )
            if self.status_scale == 1.0:
                return scored
            # The whole score, not only the positive part: this scales how far
            # the status scorer is trusted against the damage scorer, so a
            # status move it prices *below* zero should be avoided harder too.
            return ScoredAction(
                scored.action,
                scored.score * self.status_scale,
                (*scored.reasons, f"status scored at {self.status_scale:g}x"),
            )

        target = self._resolve_target(observation, slot, action, move)
        if target is None:
            return ScoredAction(action, 0.0, (f"{move.name} has no visible target",))

        defender_species = target.species
        is_ally = target.is_ally
        estimate = estimate_damage(
            self.dex,
            move,
            attacker=attacker_species,
            # `attacking_stat` is set only for Foul Play, which swings with
            # whatever it is aimed at rather than with the user.
            attack_stat=(
                self._attack_stat(attacker, move)
                if target.attacking_stat is None
                else target.attacking_stat
            ),
            defender=defender_species,
            defense_stat=target.defending_stat,
            defender_hp=target.remaining_hp,
            # Twenty-nine moves have their power computed per hit. Most are
            # exact here; Gyro Ball and Electro Ball need the target's Speed,
            # which the target resolution does not carry, and fall back to a
            # middling value rather than to zero.
            base_power=dynamic_base_power(
                move,
                attacker=attacker_species,
                defender=defender_species,
                # Mega Sol makes Solar Beam stop being halved by the weather.
                attacker_ability=self._own_ability(attacker),
                # Terrain bonuses need footing, and the two sides are asked
                # separately because Rising Voltage reads the target's while
                # everything else reads ours.
                attacker_grounded=is_grounded(
                    effective_types(
                        attacker_species.types,
                        tuple(attacker.volatile_conditions),
                    ),
                    ability=attacker.current_ability,
                    item=attacker.current_item,
                    volatiles=tuple(attacker.volatile_conditions),
                    field_conditions=tuple(observation.field_conditions),
                ),
                defender_grounded=is_grounded(
                    effective_types(defender_species.types, target.volatiles),
                    ability=target.ability,
                    item=target.item,
                    volatiles=target.volatiles,
                    field_conditions=tuple(observation.field_conditions),
                ),
                attacker_hp_fraction=attacker.hp_fraction,
                attacker_speed=(attacker.computed_stats or {}).get("spe"),
                attacker_holds_item=attacker.current_item is not None,
                attacker_positive_boosts=attacker.boosts.positive_total,
                attacker_status=attacker.status,
                defender_status=target.status,
                # An opponent's item is hidden until it fires, and "we have
                # not seen it" is not the same as "there is none" -- almost
                # every Pokemon here carries one. What we *do* know is when an
                # item has left, because the engine announces it. Holding one
                # is still not enough on its own: a Mega Stone cannot be taken
                # off the species it evolves, and this dex is full of them.
                defender_item_removable=self._item_can_be_taken(target, defender_species),
                fainted_allies=sum(1 for mon in observation.own_side.team if mon.fainted),
                terrain=observation.terrain,
                weather=move_weather,
            ),
            level=observation.regulation.level,
            doubles=observation.regulation.game_type == "doubles",
            attacker_burned=attacker.status == "brn",
            weather=move_weather,
            # Ours comes from our own request and is never hidden. Theirs is
            # None until the engine announces it -- `revealed_item` was
            # tracked from the day it was written and read by nothing.
            attacker_item=attacker.current_item,
            defender_item=target.item,
            # Endeavor and Final Gambit are priced off our own remaining HP.
            attacker_hp=attacker.current_hp,
            terrain=observation.terrain,
            # Dragon Darts splits its two hits across the opposing side.
            opponents=sum(
                1
                for i in observation.opponent_side.active_slots
                if i is not None and not observation.opponent_side.revealed[i].fainted
            ),
            # A Focus Sash only works from full health, and we can see that
            # even when we cannot see the item.
            defender_at_full_hp=target.at_full_hp,
            defender_turns_on_field=target.turns_on_field,
            defender_ability=target.ability,
            # A Roost strips the Flying type for the turn, on either side.
            attacker_volatiles=tuple(attacker.volatile_conditions),
            defender_volatiles=target.volatiles,
            # Gravity drags everything down, so footing is not decidable from
            # a Pokemon's own type and item alone.
            field_conditions=tuple(observation.field_conditions),
            # Ours is in our own request; theirs is None until it shows itself,
            # and an unknown ability is treated as doing nothing rather than
            # as an invented one.
            attacker_ability=self._own_ability(attacker),
            attacker_hp_fraction=attacker.hp_fraction,
            attacker_status=attacker.status,
            defender_status=target.status,
        )

        reasons: list[str] = []
        if is_ally:
            return ScoredAction(
                action,
                ALLY_DAMAGE_PENALTY,
                (f"{move.name} would hit our own {defender_species.name}",),
            )

        if estimate.is_immune:
            return ScoredAction(
                action, IMMUNE_PENALTY, (f"{defender_species.name} is immune to {move.name}",)
            )

        score = estimate.average_fraction * DAMAGE_WEIGHT
        reasons.append(
            f"{move.name} deals ~{estimate.average_fraction:.0%} of "
            f"{defender_species.name}'s remaining HP"
        )

        knockout_bonus = 0.0
        if estimate.guaranteed_ko:
            knockout_bonus = GUARANTEED_KO_BONUS
            reasons.append("guaranteed knockout")
        elif estimate.possible_ko:
            knockout_bonus = POSSIBLE_KO_BONUS
            reasons.append("knockout on a high roll")
        score += knockout_bonus

        # A move that charges this turn lands nothing now and the engine locks
        # the next turn in, so the choice is two turns for one hit. Priced at
        # `CHARGE_TURN_MULTIPLIER` of that hit, applied to the damage and the
        # knockout together and before anything else is added. Only the move as
        # chosen: Sleep Talk, Instruct and Copycat cannot call a charge move,
        # which the engine marks with `nosleeptalk` / `failinstruct`.
        charging = (
            self.charge_turns
            and borrow_depth == 0
            and charges_this_turn(
                move,
                weather=move_weather,
                ability=self._own_ability(attacker),
                item=attacker.current_item,
                already_charging=self._locked_mid_charge(attacker, action),
            )
        )
        if charging:
            score *= CHARGE_TURN_MULTIPLIER
            reasons.append(f"{move.name} charges this turn and lands next")

        # A recharge move lands this turn and spends the next one, if it hits.
        # The damage is real *now*, so focus fire keeps counting it; only the
        # score is priced per turn committed. Not limited to the move as chosen:
        # Sleep Talk and Copycat can call a recharge move, and pay for it.
        if self.recharge_turns and RECHARGE_FLAG in move.flags:
            score *= recharge_multiplier(move)
            reasons.append(f"{move.name} costs the next turn recharging")

        # Deliberately *not* scaled by how dangerous the target is. That was
        # built and measured (experiment 0013): it made agreement significantly
        # worse on both halves and *increased* the wrong-target count it was
        # meant to reduce. Humans prefer the more threatening of two opponents
        # only 53.7% of the time, which is barely above a coin flip.

        if estimate.effectiveness > 1:
            reasons.append(f"super effective ({estimate.effectiveness:g}x)")
        elif estimate.effectiveness < 1:
            score += RESISTED_PENALTY
            reasons.append(f"resisted ({estimate.effectiveness:g}x)")

        # An accurate move is worth more than a strong one that misses. Applied
        # last so it discounts the whole package, KO bonus included.
        #
        # A one-hit knockout move gets its own number: the engine ignores every
        # accuracy modifier for these and uses a flat 30, or 20 for Sheer Cold
        # from a non-Ice user -- and the named type is outright immune, which
        # the dumped accuracy of 30 cannot express.
        landed = ohko_chance(move, attacker=attacker_species, defender=defender_species)
        if landed is not None:
            if landed == 0.0:
                return ScoredAction(
                    action,
                    IMMUNE_PENALTY,
                    (f"{defender_species.name} cannot be hit by {move.name}",),
                )
            score *= landed
            reasons.append(f"{landed:.0%} to land a one-hit knockout")
        elif not move.always_hits:
            score *= move.hit_chance
            if move.hit_chance < 1:
                reasons.append(f"{move.accuracy}% accurate")

        sustain, sustain_reasons = self._sustain(move, estimate, attacker)
        score += sustain * move.hit_chance
        reasons.extend(sustain_reasons)

        rider, rider_reasons = self._rider_value(move, defender_species, observation, slot)
        score += rider * move.hit_chance
        reasons.extend(rider_reasons)

        return ScoredAction(
            action,
            score,
            tuple(reasons),
            target_index=target.index,
            # Focus fire adds up what the slots do to one target *this* turn,
            # and a charging Pokemon does nothing to it yet.
            damage_fraction=0.0 if charging else estimate.average_fraction * move.hit_chance,
            knockout_bonus=0.0 if charging else knockout_bonus,
        )

    @staticmethod
    def _locked_mid_charge(attacker, action: MoveAction) -> bool:
        """Whether this is the engine's second turn of a charge move.

        A Pokemon locked mid-charge is sent its one move with the target field
        omitted, which is how `choosable_move_targets` comes to hold None for
        it. Choice and Encore locks trim the list too but keep the target, so
        a missing target is specific to this case. No request, no lock.
        """
        targets = attacker.choosable_move_targets
        if targets is None or action.move_index >= len(targets):
            return False
        return targets[action.move_index] is None

    def _rider_value(
        self, move, defender_species, observation: Observation, slot: int
    ) -> tuple[float, list[str]]:
        """What the move does besides damage: status, stat changes, self-cost.

        Priced by expected value -- a 30% burn is worth 30% of a burn -- with
        one exception that is not a rounding detail: a guaranteed rider is
        certain, and Nuzzle's paralysis or Zap Cannon's are the entire reason
        those moves are worth pressing at 20 base power and 50% accuracy.
        """
        value = 0.0
        reasons: list[str] = []
        target = self._observed_target(observation, slot)

        for secondary in move.secondaries:
            chance = secondary.chance / 100

            if secondary.status:
                gain = self._status_value(secondary.status, defender_species, target)
                if gain:
                    value += chance * gain * STATUS_WEIGHT
                    certainty = "always" if secondary.is_guaranteed else f"{secondary.chance}%"
                    reasons.append(f"{certainty} inflicts {secondary.status}")

            if secondary.volatile_status == "flinch":
                first = self._moves_first(move, observation, slot)
                if first > 0 and (target is None or not target.fainted):
                    value += chance * first * FLINCH_VALUE * FLINCH_WEIGHT
                    reasons.append(
                        f"{secondary.chance}% flinch"
                        + ("" if first == 1.0 else " if we move first")
                    )
                else:
                    reasons.append("its flinch is wasted moving second")

            for stat, stages in secondary.boosts.items():
                # Negative stages on the target are good for us.
                value += chance * -stages * STAT_STAGE_VALUE * STAT_STAGE_WEIGHT
                if stages < 0:
                    reasons.append(f"drops their {stat}")

            for stat, stages in secondary.self_boosts.items():
                value += chance * stages * STAT_STAGE_VALUE * STAT_STAGE_WEIGHT
                if stages > 0:
                    reasons.append(f"raises our {stat}")

        # Unconditional, as distinct from a rider: Close Combat always drops
        # its own defences rather than rolling for it.
        attacker = self._own_active(observation, slot)
        threat = 1.0
        if attacker is not None and any(
            stat in DEFENSIVE_STATS and stages < 0 for stat, stages in move.self_boosts.items()
        ):
            threat, _, _ = self._incoming_threat(observation, slot, attacker)

        for stat, stages in move.self_boosts.items():
            cost = stages * STAT_STAGE_VALUE * STAT_STAGE_WEIGHT
            if stat in DEFENSIVE_STATS and stages < 0:
                # Priced against what is actually coming: dropping our defence
                # in front of something harmless costs nothing.
                cost *= threat
            value += cost
            if stages < 0:
                reasons.append(f"but lowers our own {stat}")

        return value, reasons

    def _status_value(self, status: str, defender_species, target) -> float:
        """Worth of landing `status`, or zero when it cannot land at all."""
        if status not in STATUS_VALUE:
            return 0.0
        # A Pokemon can only carry one status, so a second never lands.
        if target is not None and target.status:
            return 0.0
        immune = STATUS_IMMUNE_TYPES.get(status, set())
        if immune & set(defender_species.types):
            return 0.0
        return STATUS_VALUE[status]

    def _moves_first(self, move: MoveInfo, observation: Observation, slot: int) -> float:
        """Probability we act before everything on the other side.

        The worst case over both opponents, which is what the flinch this
        drives actually needs: a flinch is wasted if *anything* moves before
        us and knocks the flincher out.

        The rule itself lives in `mechanics.turn_order` and is checked against
        the engine directly. What is uncertain here, and only here, is the
        opponent's *move* -- we are choosing before they reveal it.
        """
        attacker = self._own_active(observation, slot)
        if attacker is None:
            return 0.0

        trick_room = TRICK_ROOM in observation.field_conditions
        ours = self._our_speed(observation, attacker)

        chance = 1.0
        opponent = observation.opponent_side
        for index in opponent.active_slots:
            if index is None:
                continue
            observed = opponent.revealed[index]
            if observed.fainted:
                continue
            try:
                species = self.dex.get_species(observed.species)
            except KeyError:
                continue
            theirs = self._their_speed(observation, observed, species)
            chance = min(
                chance,
                moves_first(
                    move_priority(
                        move,
                        attacker.current_ability,
                        at_full_hp=attacker.hp_fraction >= 1.0,
                    ),
                    ours,
                    self._revealed_priority(observed),
                    theirs,
                    trick_room=trick_room,
                ),
            )
        return chance

    def _our_speed(self, observation: Observation, mon) -> float:
        """One of our Pokemon's effective Speed right now.

        Split out of `_moves_first` so that turn-order reasoning and anything
        pricing a change to the speed order read the same number -- the two
        must not disagree about who is faster.
        """
        return effective_speed(
            (mon.computed_stats or {}).get("spe", 0),
            boost_stage=mon.boosts.speed,
            tailwind=TAILWIND in observation.own_side.side_conditions,
            paralysed=mon.status == PARALYSIS,
            item=mon.current_item,
            ability=mon.current_ability,
            weather=observation.weather,
            holds_item=mon.current_item is not None,
        )

    def _their_speed(self, observation: Observation, observed, species: SpeciesInfo) -> float:
        """An opponent's effective Speed, as far as we can know it."""
        return effective_speed(
            self._opponent_stats(species)["spe"],
            boost_stage=observed.boosts.speed,
            tailwind=TAILWIND in observation.opponent_side.side_conditions,
            paralysed=observed.status == PARALYSIS,
            item=self._known_item(observed),
            # A Mega forme has one possible ability, so this is often
            # known without ever having watched it fire.
            ability=self._known_ability(observed),
            weather=observation.weather,
            holds_item=observed.may_hold_item,
        )

    def _revealed_priority(self, observed) -> float:
        """The highest priority we have actually seen this Pokemon use.

        Their ability counts too, once revealed -- a Grimmsnarl whose Prankster
        has shown itself puts every status move it has a bracket above ours.
        `revealed_ability` was tracked by the tracker and read by nothing until
        now, which is the same shape as most of the bugs in this project. It is
        asked through `_known_ability`, which also settles the species that
        only have one ability to have.

        Unrevealed moves are assumed ordinary. That is optimistic -- they may
        be holding an Aqua Jet we have not seen -- but assuming one would be
        worse: it would make our own priority moves look useless against a
        Pokemon that has shown nothing at all, which is every Pokemon on the
        turn it arrives.
        """
        ability = self._known_ability(observed)
        at_full_hp = observed.hp_percent >= 100
        return max(
            (
                move_priority(m, ability, at_full_hp=at_full_hp)
                for m in self._revealed_moves(observed)
            ),
            default=0.0,
        )

    @staticmethod
    def _observed_target(observation: Observation, slot: int):
        """The opponent this slot would most likely be hitting, if visible."""
        opponent = observation.opponent_side
        for index in opponent.active_slots:
            if index is not None and not opponent.revealed[index].fainted:
                return opponent.revealed[index]
        return None

    def _sustain(self, move, estimate, attacker) -> tuple[float, list[str]]:
        """HP the move moves onto or off our own bar.

        Drain and recoil are damage too, just pointed at us, so they belong in
        the same currency rather than as a separate adjustment. Both are
        clamped to what is actually available: healing above full is wasted,
        and recoil cannot take more HP than the Pokemon has.
        """
        if not (move.drain or move.recoil or move.has_crash_damage or move.self_switch):
            return 0.0, []

        dealt = estimate.average
        value = 0.0
        reasons: list[str] = []

        if move.drain:
            missing = max(0, attacker.max_hp - attacker.current_hp)
            healed = min(move.drain_fraction * dealt, missing)
            gain = healed / attacker.max_hp
            value += gain * SUSTAIN_WEIGHT
            if gain > 0:
                reasons.append(f"heals back ~{gain:.0%} of its own HP")
            else:
                reasons.append("already at full HP, so the drain is wasted")

        if move.recoil:
            taken = min(move.recoil_fraction * dealt, attacker.current_hp)
            loss = taken / attacker.max_hp
            value -= loss * SUSTAIN_WEIGHT
            reasons.append(f"but costs ~{loss:.0%} of its own HP in recoil")
            if taken >= attacker.current_hp:
                reasons.append("which would knock it out")

        if move.has_crash_damage:
            # High Jump Kick and friends take half a health bar on a *miss*,
            # so the cost is the miss chance times that. A 90%-accurate move
            # is not 90% of a good move here; it is 90% of a good move and 10%
            # of a disaster.
            miss = 1.0 - move.hit_chance
            loss = miss * CRASH_DAMAGE_FRACTION
            value -= loss * SUSTAIN_WEIGHT
            reasons.append(f"and costs half its HP on the {miss:.0%} chance it misses")

        if move.self_switch and attacker.hp_fraction <= LOW_HP_FRACTION:
            # U-turn, Volt Switch and Flip Turn attack *and* pivot. Getting
            # something weakened out of danger is worth what it is worth
            # anywhere else.
            value += SWITCH_WHEN_WEAKENED_BONUS
            reasons.append("and pivots something weakened out of danger")

        return value, reasons

    def _score_status_move(
        self,
        observation: Observation,
        slot: int,
        action: MoveAction,
        move: MoveInfo,
        attacker,
        borrow_depth: int = 0,
    ) -> ScoredAction:
        """What this move actually changes, priced like everything else.

        Every status move but Protect used to score a flat 12.0, so Swords
        Dance, Thunder Wave, Recover and Trick Room were indistinguishable --
        and, worse, a *redundant* one scored the same as a fresh one. Recover
        at full HP, Swords Dance at +6 and a second Tailwind were as attractive
        as the first use of any of them.

        Fifty-six of the 175 status moves here keep the flat value, because
        their effects live in an `onHit` callback the engine cannot dump: Belly
        Drum, Haze, Heal Bell, Defog, Baton Pass. Those are unknown rather than
        worthless, and a flat value says so.
        """
        if move.move_id in PROTECT_MOVES:
            return self._score_protect(observation, slot, action, move, attacker)

        if move.move_id in ABILITY_MOVES:
            swapped = self._score_ability_move(observation, slot, action, move, attacker)
            if swapped is not None:
                return swapped

        if move.move_id in TURN_ORDER_MOVES:
            ordered = self._score_turn_order(observation, slot, action, move, attacker)
            if ordered is not None:
                return ordered

        if move.move_id in TYPE_CHANGING_MOVES:
            retyped = self._score_retype(observation, slot, action, move, attacker)
            if retyped is not None:
                return retyped

        if move.move_id == LOCK_ON:
            locked = self._score_lock_on(observation, slot, action, attacker)
            if locked is not None:
                return locked

        if move.move_id in BORROWING_MOVES:
            borrowed = self._score_borrowed(observation, slot, action, move, attacker, borrow_depth)
            if borrowed is not None:
                return borrowed

        if move.move_id in REDIRECTION_MOVES:
            drawn = self._score_redirection(observation, slot, action, move, attacker)
            if drawn is not None:
                return drawn

        observed = self._observed_target(observation, slot)
        on_us = move.target in SELF_TARGETS
        value = 0.0
        reasons: list[str] = []

        # Moves whose whole effect lives in an `onHit` callback, so nothing
        # about them is dumped. Many are still perfectly computable from state
        # we hold, and are priced in the same currencies as everything else.
        computed = self._support_value(move, observation, slot, attacker, observed)
        if computed is not None:
            gained, why = computed
            return ScoredAction(action, gained * move.hit_chance, tuple(why))

        # Who actually receives the stages decides whether they are worth
        # anything. Six moves here hand a *positive* boost to somebody other
        # than the user -- three to an ally (Decorate, Coaching, Aromatic
        # Mist) and three to an opponent as a trade (Swagger, Flatter, Spicy
        # Extract) -- and the old split, "us or them", could express neither.
        recipient, friendly = self._boost_recipient(
            observation, slot, action, move, attacker, observed
        )
        value += self._boost_value(move, recipient, friendly, reasons, observation, slot, attacker)
        # Everything a move inflicts follows the same rule as its boosts: it
        # lands on whoever the action names. Aiming Swagger at our own partner
        # buys the +2 Attack and the confusion, and the confusion is ours.
        aimed_at_ally = friendly and move.target not in SELF_TARGETS
        inflicted = self._status_move_status(move, observed, reasons)
        value += -inflicted if aimed_at_ally else inflicted
        value += self._heal_value(move, attacker, reasons)
        value += self._field_value(move, observation, slot, attacker, reasons)
        landed = self._volatile_value(move, observed, on_us, reasons)
        value += -landed if aimed_at_ally else landed

        if not reasons:
            return ScoredAction(action, STATUS_MOVE_VALUE, (f"{move.name} is a support move",))
        return ScoredAction(action, value * move.hit_chance, tuple(reasons))

    def _score_lock_on(self, observation, slot, action, attacker):
        """Guaranteeing next turn's hit, worth the damage misses cost us now.

        Priced from our own moveset rather than as a flat value: Lock-On is
        worth a great deal to a Focus Blast and nothing at all to a Pokemon
        whose moves all land anyway. That is the accuracy gap on whichever
        move stands to gain most, in the currency damage already uses.
        """
        best = 0.0
        name = None
        for index, move_id in enumerate(attacker.selectable_moves):
            try:
                candidate = self.dex.get_move(move_id)
            except KeyError:
                continue
            # Damaging only, which also keeps this out of its own way: scoring
            # move index 0 blindly would recurse forever when Lock-On is the
            # first move in the set.
            if not candidate.is_damaging or candidate.hit_chance >= 1.0:
                continue
            scored = self._score_move(
                observation, slot, MoveAction(move_index=index, target=action.target)
            )
            # What the misses are costing: the move already scores its own
            # hit chance, so the gap is what perfect accuracy would add back.
            gap = scored.score * (1.0 / max(0.01, candidate.hit_chance) - 1.0)
            if gap > best:
                best, name = gap, candidate.name
        if name is None:
            return ScoredAction(action, 0.0, ("every move we have already lands",))
        return ScoredAction(action, best, (f"stops our {name} missing next turn",))

    def _mega_form(self, attacker, species: SpeciesInfo):
        """`attacker` as it would be after Mega Evolving, or None if it cannot.

        Scored as the forme rather than given a bonus, which is the whole
        point: a Mega is a different Pokemon with different stats, a different
        ability and sometimes a different typing, and the damage model already
        knows what all three are worth. Inventing a "Mega is good" constant
        would be guessing at a number the model can compute.

        Stats are carried across by *ratio* rather than recomputed, so the
        nature survives: `computed_stats` arrives from the engine with the
        nature already in it, and the ratio of two point-adjusted bases cancels
        it on both sides.
        """
        stone = self.dex.items.get(attacker.current_item or "")
        if stone is None or not stone.mega_forme:
            return None
        try:
            forme = self.dex.get_species(stone.mega_forme)
        except KeyError:
            return None

        points = attacker.pokemon_set.stats
        current = attacker.computed_stats or {}
        before, after = species.base_stats, forme.base_stats
        stats = dict(current)
        for key, old_base, new_base, invested in (
            ("atk", before.attack, after.attack, points.attack),
            ("def", before.defense, after.defense, points.defense),
            ("spa", before.special_attack, after.special_attack, points.special_attack),
            ("spd", before.special_defense, after.special_defense, points.special_defense),
            ("spe", before.speed, after.speed, points.speed),
        ):
            baseline = other_stat(old_base, invested)
            if key in current and baseline > 0:
                stats[key] = int(current[key] * other_stat(new_base, invested) / baseline)

        return forme, attacker.model_copy(
            update={
                "computed_stats": stats,
                # Every Mega forme has exactly one possible ability, so this is
                # a fact rather than a guess.
                "current_ability": (to_id(forme.abilities[0]) if forme.abilities else None),
                "pokemon_set": attacker.pokemon_set.model_copy(update={"species": forme.name}),
            }
        )

    def _score_borrowed(
        self,
        observation: Observation,
        slot: int,
        action: MoveAction,
        move: MoveInfo,
        attacker,
        depth: int,
    ) -> "ScoredAction | None":
        """Price Copycat, Sleep Talk, Instruct and Spite as what they stand in for.

        All four were unscoreable until the tracker learned which move went
        last, so all four took the flat support value -- a Copycat after an
        Earthquake was worth the same as a Copycat on turn one, when the first
        is an Earthquake and the second simply fails.

        Returning None hands the move back to the ordinary path, which is what
        should happen when we cannot say. Returning a score of zero is a
        different statement: the engine would refuse the move outright.
        """
        if depth >= MAX_BORROW_DEPTH:
            # Copycat can borrow Sleep Talk, which borrows again. Bounded here
            # rather than by trusting the refusal flags to close every loop.
            return None
        move_id = move.move_id

        if move_id == COPYCAT:
            borrowed = copycat_borrows(self._move_or_none(observation.last_move_used))
            if borrowed is None:
                return ScoredAction(action, 0.0, ("there is no move for Copycat to copy yet",))
            return self._as_borrowed(observation, slot, action, borrowed, attacker, depth, "copies")

        if move_id == SLEEP_TALK:
            known = [self._move_or_none(i) for i in attacker.selectable_moves]
            candidates = sleep_talk_candidates(
                [m for m in known if m is not None],
                asleep=attacker.status == "slp",
            )
            if not candidates:
                return ScoredAction(action, 0.0, ("Sleep Talk only works while asleep",))
            # Which one it picks is uniformly random, so the move is worth the
            # average of them -- not the best of them, which is the mistake
            # that would make Sleep Talk look like a free copy of our best hit.
            scores = [
                self._as_borrowed(observation, slot, action, candidate, attacker, depth, "may use")
                for candidate in candidates
            ]
            mean = sum(scored.score for scored in scores) / len(scores)
            return ScoredAction(
                action,
                mean,
                (f"picks at random from {len(candidates)} move(s) while asleep",),
            )

        if move_id == INSTRUCT:
            return self._score_instruct(observation, slot, action, attacker, depth)

        if move_id == SPITE:
            observed = self._observed_target(observation, slot)
            target_last = observed.last_move if observed is not None else None
            if spite_removes(self._move_or_none(target_last)) is None:
                return ScoredAction(
                    action, 0.0, ("they have not used a move for Spite to bite into",)
                )
            # PP is not modelled -- an opponent's is unknowable, and in a
            # format lasting about five turns four PP is rarely the binding
            # constraint. So this is genuinely unknown rather than zero, and
            # falls through to the flat support value.
            return None

        return None

    def _score_ability_move(
        self,
        observation: Observation,
        slot: int,
        action: MoveAction,
        move: MoveInfo,
        attacker,
    ) -> "ScoredAction | None":
        """Skill Swap, Role Play, Entrainment, Worry Seed and Simple Beam.

        These are the five the "ability tracking" backlog item was originally
        about, and they stayed unpriced through it -- tracking was the easy
        half. What an ability is *worth* is answerable now, and by the same
        route as everything else: run the damage estimate twice, once with the
        ability and once with what the move would replace it with, and the
        difference is the answer.

        An ability we have not seen makes this unanswerable rather than zero.
        `revealed_ability` is the gate, and it means these moves stay unpriced
        against anything that has not shown itself -- which is honest, because
        we genuinely do not know what we would be taking away.

        Only the offensive half is counted: what *we* can then do to *them*.
        Skill Swap and Entrainment also hand our ability to the opponent, and
        what that is worth to them is not modelled, so both read slightly
        generously against anything that would enjoy what we are giving away.
        """
        observed = self._observed_target(observation, slot)
        if observed is None:
            return ScoredAction(action, 0.0, ("nobody there to reach",))
        theirs = self._known_ability(observed)
        ours = attacker.current_ability
        if theirs is None:
            return None

        if not ability_move_succeeds(move.move_id, ours=ours, theirs=theirs):
            return ScoredAction(action, 0.0, (f"{move.name} would fail here",))

        after_ours, after_theirs = abilities_after(move.move_id, ours=ours, theirs=theirs)
        now = self._our_best_hit(observation, slot, observed, ours, theirs)
        later = self._our_best_hit(observation, slot, observed, after_ours, after_theirs)
        return ScoredAction(
            action,
            (later - now) * DAMAGE_WEIGHT,
            (
                f"leaves them with {after_theirs} and us with {after_ours}",
                f"which is worth ~{later - now:+.0%} of a health bar to us",
            ),
        )

    def _our_best_hit(
        self,
        observation: Observation,
        slot: int,
        observed,
        attacker_ability: str | None,
        defender_ability: str | None,
        offensive_stat: str | None = None,
    ) -> float:
        """Best fraction *this* Pokemon of ours could take off that target.

        Only our own slot, unlike the retyping moves: Skill Swap and Role Play
        change what *we* have, so the partner's numbers do not move.

        `offensive_stat` narrows the search to the moves a stat boost would
        actually help. Swords Dance raises Attack, so pricing it off a special
        attack -- or off Body Press, which is Physical but swings with Defense
        -- would credit it with damage it cannot buy.
        """
        attacker = self._own_active(observation, slot)
        if attacker is None:
            return 0.0
        try:
            species = self.dex.get_species(observed.species)
            attacker_species = self.dex.get_species(attacker.pokemon_set.species)
        except KeyError:
            return 0.0
        stats = self._opponent_stats(species)
        hp = max(1, round(stats["hp"] * observed.hp_percent / 100))

        best = 0.0
        for move_id in attacker.selectable_moves:
            try:
                candidate = self.dex.get_move(move_id)
            except KeyError:
                continue
            if not candidate.is_damaging:
                continue
            if offensive_stat is not None and candidate.offensive_stat != offensive_stat:
                continue
            estimate = estimate_damage(
                self.dex,
                candidate,
                attacker=attacker_species,
                attack_stat=self._attack_stat(attacker, candidate),
                defender=species,
                defense_stat=apply_boost(
                    stats.get(candidate.defensive_stat, 100),
                    observed.boosts.stage(candidate.defensive_stat),
                ),
                defender_hp=hp,
                level=observation.regulation.level,
                doubles=observation.regulation.game_type == "doubles",
                weather=observation.weather,
                terrain=observation.terrain,
                attacker_ability=attacker_ability,
                defender_ability=defender_ability,
                attacker_hp_fraction=attacker.hp_fraction,
                attacker_status=attacker.status,
                defender_status=observed.status,
                defender_at_full_hp=observed.hp_percent >= 100,
                defender_turns_on_field=observed.turns_on_field,
            )
            best = max(best, estimate.average_fraction * candidate.hit_chance)
        return min(best, 1.0)

    def _score_turn_order(
        self,
        observation: Observation,
        slot: int,
        action: MoveAction,
        move: MoveInfo,
        attacker,
    ) -> "ScoredAction | None":
        """After You and Quash, which buy an ordering rather than an effect.

        Both are worth the same thing seen from opposite sides: somebody on our
        side gets to act before somebody on theirs. That is only worth
        anything when the ordering would otherwise have cost us something we
        can name -- a turn our ally loses to a knockout, or a hit we could have
        pre-empted -- so both are priced as the damage the swap avoids, in the
        currency Protect already uses.

        Ally Switch is deliberately absent. Its whole value is dodging an
        attack aimed at a slot, and which slot they aimed at is precisely what
        we cannot see; a computed number there would be worse than admitting
        we do not know, which is the lesson Perish Song already taught.
        """
        if move.move_id == AFTER_YOU:
            return self._score_after_you(observation, slot, action)
        if move.move_id == QUASH:
            return self._score_quash(observation, slot, action)
        return None

    def _score_after_you(
        self, observation: Observation, slot: int, action: MoveAction
    ) -> "ScoredAction | None":
        """Letting our partner go first, worth the turn it would otherwise lose.

        Only nameable when the partner is facing a knockout. Moving earlier is
        worth something in plenty of other spots -- landing damage before a
        heal, setting a field before they use it -- and none of that is
        modelled here, so this is a floor on the move's value rather than an
        estimate of it.
        """
        found = self._ally_of(observation, slot)
        if found is None:
            return ScoredAction(action, 0.0, ("no ally to let through",))
        index, ally_slot = found
        partner = observation.own_side.team[index]

        best = self._best_own_move(observation, ally_slot, partner)
        if best is None:
            return None
        chance_first = self._moves_first(best.move, observation, ally_slot)
        if chance_first >= 1.0:
            return ScoredAction(
                action,
                0.0,
                (f"our {partner.pokemon_set.species} was going first anyway",),
            )

        _, would_ko, source = self._incoming_threat(observation, ally_slot, partner)
        if not would_ko:
            return ScoredAction(
                action,
                0.0,
                (f"our {partner.pokemon_set.species} survives either way",),
            )
        # The partner loses its whole turn if it is knocked out before acting,
        # so what After You buys is that turn -- weighted by how likely it was
        # to be lost.
        value = (1.0 - chance_first) * best.score
        return ScoredAction(
            action,
            value,
            (
                f"our {partner.pokemon_set.species} would be knocked out by {source} before moving",
                f"letting its {best.move.name} through first",
            ),
        )

    def _score_quash(
        self, observation: Observation, slot: int, action: MoveAction
    ) -> "ScoredAction | None":
        """Pushing an opponent to the back of the turn.

        Worth what their attack costs us, but only when our side can actually
        remove them in the window it buys -- a Quash on something we cannot
        knock out just delays the same hit to later in the same turn.
        """
        observed = self._observed_target(observation, slot)
        if observed is None:
            return ScoredAction(action, 0.0, ("nobody there to quash",))
        try:
            species = self.dex.get_species(observed.species)
        except KeyError:
            return None

        found = self._ally_of(observation, slot)
        if found is None:
            return ScoredAction(action, 0.0, ("nobody left to act in the window",))
        index, ally_slot = found
        partner = observation.own_side.team[index]

        best = self._best_own_move(observation, ally_slot, partner)
        if best is None or not best.knocks_out:
            return ScoredAction(
                action,
                0.0,
                (f"we cannot remove {species.name} in the window it buys",),
            )
        try:
            partner_species = self.dex.get_species(partner.pokemon_set.species)
        except KeyError:
            return None
        threat, _, _ = self._threat_from(observed, partner, partner_species, observation)
        chance_they_first = 1.0 - self._moves_first(best.move, observation, ally_slot)
        return ScoredAction(
            action,
            threat * chance_they_first * DAMAGE_WEIGHT,
            (
                f"pushes {species.name} to the back of the turn",
                f"so our {partner_species.name} removes it first",
            ),
        )

    def _best_own_move(self, observation: Observation, slot: int, mon):
        """The best move this Pokemon of ours has right now, and what it does.

        Used by the turn-order moves, which are worth what the move they let
        through is worth -- so the same scorer has to answer, or the two
        numbers are in different currencies.
        """
        best = None
        for index, move_id in enumerate(mon.selectable_moves):
            # Turn-order moves are skipped, and not only to stop this recursing
            # forever through a partner who also has one: what After You buys
            # is the partner's *real* move, never another ordering.
            if move_id in TURN_ORDER_MOVES:
                continue
            scored = self._score_move(observation, slot, MoveAction(move_index=index))
            if best is None or scored.score > best.score:
                try:
                    info = self.dex.get_move(move_id)
                except KeyError:
                    continue
                best = _BestMove(
                    move=info,
                    score=scored.score,
                    knocks_out=any("knockout" in reason for reason in scored.reasons),
                )
        return best

    def _score_retype(
        self,
        observation: Observation,
        slot: int,
        action: MoveAction,
        move: MoveInfo,
        attacker,
    ) -> "ScoredAction | None":
        """What rewriting somebody's typing is worth.

        Five moves in this dex do it and none of them was priced. What they are
        worth is entirely a matter of the type chart -- a Soak that strips a
        Steel type's resistances is worth a great deal, and the same Soak aimed
        at a Water type does nothing at all -- so it is computable, and only
        the wiring was missing.

        Priced as the difference between two damage estimates rather than as a
        number invented for it: how much more our side can do to them
        afterwards, or in Reflect Type's case how much less they can do to us.
        Both are in the currency our own attacks already use.
        """
        if move.move_id == REFLECT_TYPE:
            return self._score_reflect_type(observation, slot, action, attacker)

        observed = self._observed_target(observation, slot)
        if observed is None:
            return ScoredAction(action, 0.0, ("nobody to retype",))
        try:
            species = self.dex.get_species(observed.species)
        except KeyError:
            return None
        before = effective_types(species.types, tuple(observed.volatile_conditions))
        after = retyped_by(move.move_id, before)
        if after is None:
            # The engine's own answer: Soak on a Water type fails outright, and
            # so does Trick-or-Treat on anything already part Ghost.
            return ScoredAction(action, 0.0, (f"{move.name} would fail on {species.name}",))

        gained = self._best_damage(observation, slot, observed, after) - self._best_damage(
            observation, slot, observed, before
        )
        return ScoredAction(
            action,
            gained * DAMAGE_WEIGHT,
            (
                f"makes {species.name} {'/'.join(after)}",
                f"which is worth ~{gained:+.0%} of its health bar to us",
            ),
        )

    def _score_reflect_type(
        self, observation: Observation, slot: int, action: MoveAction, attacker
    ) -> "ScoredAction | None":
        """Copying their typing onto ourselves, worth the damage it avoids."""
        observed = self._observed_target(observation, slot)
        if observed is None:
            return ScoredAction(action, 0.0, ("nobody to copy",))
        try:
            theirs = self.dex.get_species(observed.species)
            ours = self.dex.get_species(attacker.pokemon_set.species)
        except KeyError:
            return None
        current = effective_types(ours.types, tuple(attacker.volatile_conditions))
        copied = effective_types(theirs.types, tuple(observed.volatile_conditions))
        after = retyped_by(REFLECT_TYPE, current, copied=copied)
        if after is None:
            return ScoredAction(action, 0.0, (f"we are already {'/'.join(current)}",))
        now, _, _ = self._incoming_threat(observation, slot, attacker)
        later, _, _ = self._incoming_threat(observation, slot, attacker, after)
        return ScoredAction(
            action,
            (now - later) * DAMAGE_WEIGHT,
            (
                f"turns us into {'/'.join(after)}",
                f"which avoids ~{now - later:+.0%} of the worst hit coming",
            ),
        )

    def _best_damage(
        self,
        observation: Observation,
        slot: int,
        observed,
        defender_types: tuple[str, ...],
    ) -> float:
        """The best fraction our side could take off this target, given a typing.

        Over both our active Pokemon, because a Soak is usually thrown so that
        the *partner* can hit -- scoring only the user's own moves would miss
        the reason the move is in the team.
        """
        try:
            species = self.dex.get_species(observed.species)
        except KeyError:
            return 0.0
        opponent_stats = self._opponent_stats(species)
        hp = max(1, round(opponent_stats["hp"] * observed.hp_percent / 100))

        best = 0.0
        for index in observation.own_side.active_slots:
            if index is None:
                continue
            mon = observation.own_side.team[index]
            if mon.fainted:
                continue
            try:
                mon_species = self.dex.get_species(mon.pokemon_set.species)
            except KeyError:
                continue
            for move_id in mon.selectable_moves:
                try:
                    candidate = self.dex.get_move(move_id)
                except KeyError:
                    continue
                if not candidate.is_damaging:
                    continue
                estimate = estimate_damage(
                    self.dex,
                    candidate,
                    attacker=mon_species,
                    attack_stat=self._attack_stat(mon, candidate),
                    defender=species,
                    defense_stat=apply_boost(
                        opponent_stats.get(candidate.defensive_stat, 100),
                        observed.boosts.stage(candidate.defensive_stat),
                    ),
                    defender_hp=hp,
                    level=observation.regulation.level,
                    doubles=observation.regulation.game_type == "doubles",
                    weather=observation.weather,
                    terrain=observation.terrain,
                    defender_types=defender_types,
                )
                best = max(best, estimate.average_fraction * candidate.hit_chance)
        return min(best, 1.0)

    def _score_instruct(
        self,
        observation: Observation,
        slot: int,
        action: MoveAction,
        attacker,
        depth: int,
    ) -> "ScoredAction | None":
        """What making somebody go again is worth.

        Two things about this move are easy to get wrong, and the corpus caught
        both:

        **It is usually not the *last* move that gets repeated.** Instruct is
        priority 0 and its users are slow, so the ally has almost always
        already moved this turn by the time it resolves. Pricing it off
        `last_move` read the previous turn's move, and in all seven human
        Instructs in the corpus that was the wrong move -- twice it read
        "nothing to repeat" for an ally that went on to fire an Eruption in
        that very turn. So when the ally acts first, the move repeated is the
        one we expect them to pick now, which is the best-scoring one they
        have: the same scorer chooses their action, so this is self-consistent
        rather than optimistic.

        **It can be aimed at an opponent.** The move's target is `normal`, not
        `adjacentAlly`, so the engine offers it against the other side too --
        and doing that hands them a free attack.
        """
        target = action.target
        if target is not None and target.side != "ally":
            return self._instruct_the_opposition(observation, slot, attacker)

        found = self._ally_of(observation, slot)
        if found is None:
            return ScoredAction(action, 0.0, ("no ally to instruct",))
        index, ally_slot = found
        partner = observation.own_side.team[index]
        try:
            partner_species = self.dex.get_species(partner.pokemon_set.species)
        except KeyError:
            return None

        # Everything the ally could be made to repeat, by the engine's rules.
        repeatable = [
            info
            for info in (self._move_or_none(m) for m in partner.selectable_moves)
            if info is not None
            and instruct_repeats(info) is not None
            and gains_from_repeating(info)
        ]
        if not repeatable:
            return ScoredAction(
                action,
                0.0,
                (f"nothing {partner_species.name} knows is worth doing twice in one turn",),
            )

        def repeat_value(info: MoveInfo) -> ScoredAction:
            # Scored from the *ally's* slot, because that is who acts.
            return self._score_chosen_move(
                observation, ally_slot, action, info, partner, partner_species, depth + 1
            )

        if self._ally_acts_first(observation, slot, ally_slot):
            best = max(repeatable, key=lambda info: repeat_value(info).score)
            scored = repeat_value(best)
            why = f"our {partner_species.name} goes twice, likely {best.name}"
        else:
            repeated = instruct_repeats(self._move_or_none(partner.last_move))
            if repeated is None:
                return ScoredAction(
                    action,
                    0.0,
                    (f"{partner_species.name} moves after us and has nothing to repeat",),
                )
            scored = repeat_value(repeated)
            why = f"our {partner_species.name} uses {repeated.name} again"
        return ScoredAction(action, scored.score, (why, *scored.reasons[:1]))

    def _instruct_the_opposition(
        self, observation: Observation, slot: int, attacker
    ) -> ScoredAction:
        """Instruct aimed across the field, which gives them a free attack.

        Worth minus what that attack costs us, in the same currency our own
        damage is worth -- so it lands well below every real option rather
        than at an invented penalty.
        """
        observed = self._observed_target(observation, slot)
        if observed is None:
            return ScoredAction(MoveAction(move_index=0), 0.0, ("nobody there to instruct",))
        try:
            species = self.dex.get_species(attacker.pokemon_set.species)
        except KeyError:
            return ScoredAction(MoveAction(move_index=0), 0.0, ("no species data",))
        fraction, _, _ = self._threat_from(observed, attacker, species, observation)
        return ScoredAction(
            MoveAction(move_index=0),
            -fraction * DAMAGE_WEIGHT,
            (f"lets {observed.species} attack again, at our expense",),
        )

    def _ally_acts_first(self, observation: Observation, slot: int, ally_slot: int) -> bool:
        """Whether our partner moves before us this turn.

        Both are on our side, so tailwind and Trick Room apply to both and this
        is a plain Speed comparison. Priority is left out deliberately: we are
        choosing their move at the same time as ours, so there is no priority
        to read yet.
        """
        ours = self._own_active(observation, slot)
        index = observation.own_side.active_slots[ally_slot]
        if ours is None or index is None:
            return False
        partner = observation.own_side.team[index]
        tailwind = TAILWIND in observation.own_side.side_conditions

        def speed(mon) -> int:
            return effective_speed(
                (mon.computed_stats or {}).get("spe", 0),
                boost_stage=mon.boosts.speed,
                tailwind=tailwind,
                paralysed=mon.status == PARALYSIS,
                item=mon.current_item,
                ability=mon.current_ability,
                weather=observation.weather,
                holds_item=mon.current_item is not None,
            )

        if TRICK_ROOM in observation.field_conditions:
            return speed(partner) < speed(ours)
        return speed(partner) > speed(ours)

    def _move_or_none(self, move_id: str | None) -> "MoveInfo | None":
        if not move_id:
            return None
        try:
            return self.dex.get_move(move_id)
        except KeyError:
            return None

    def _ally_of(self, observation: Observation, slot: int) -> "tuple[int, int] | None":
        """Our other active Pokemon as (team index, slot), if there is one."""
        for other, index in enumerate(observation.own_side.active_slots):
            if other == slot or index is None:
                continue
            if not observation.own_side.team[index].fainted:
                return index, other
        return None

    def _as_borrowed(
        self,
        observation: Observation,
        slot: int,
        action: MoveAction,
        borrowed: MoveInfo,
        attacker,
        depth: int,
        verb: str,
    ) -> ScoredAction:
        """Score `borrowed` as though we had picked it, keeping our own action."""
        try:
            species = self.dex.get_species(attacker.pokemon_set.species)
        except KeyError:
            return ScoredAction(action, STATUS_MOVE_VALUE, ("no species data",))
        scored = self._score_chosen_move(
            observation, slot, action, borrowed, attacker, species, depth + 1
        )
        return ScoredAction(action, scored.score, (f"{verb} {borrowed.name}", *scored.reasons[:1]))

    def _item_can_be_taken(self, target, species) -> bool:
        """Whether Knock Off would find something it can actually remove.

        Three states, not two. We watched an item leave: nothing to take. We
        have seen what they hold: check it properly. We have seen nothing:
        they almost certainly hold *something* in this format, so assume they
        do -- unless they are a species with a Mega Stone, in which case the
        thing they are most likely holding is the one item that cannot be
        taken off them.
        """
        if not target.may_hold_item:
            return False
        known = self.dex.items.get(target.item or "")
        if known is not None:
            return is_removable(known, species, target.ability)
        if species is not None and self.dex.mega_stone_for(species) is not None:
            return False
        return is_removable(None, species, target.ability, unknown_counts_as_held=True)

    def _support_value(self, move, observation, slot, attacker, observed):
        """Gather the state `support.score_support_move` needs, and ask it."""
        ally = None
        for index in observation.own_side.active_slots:
            if index is None:
                continue
            candidate = observation.own_side.team[index]
            if candidate is not attacker and not candidate.fainted:
                ally = candidate
                break

        observed_stats = None
        if observed is not None:
            try:
                species = self.dex.get_species(observed.species)
            except KeyError:
                species = None
            if species is not None:
                observed_stats = self._opponent_stats(species)

        return score_support_move(
            move,
            attacker=attacker,
            ally=ally,
            observed=observed,
            observed_stats=observed_stats,
            weather=observation.weather,
            own_side_conditions=tuple(observation.own_side.side_conditions),
            opponent_side_conditions=tuple(observation.opponent_side.side_conditions),
            team_statuses=tuple(mon.status for mon in observation.own_side.team if not mon.fainted),
            # Ours is never hidden from us; theirs is, until it fires.
            attacker_item=self.dex.items.get(attacker.current_item or ""),
            defender_item=(
                self.dex.items.get(self._known_item(observed) or "")
                if observed is not None
                else None
            ),
            consumed_item=(
                self.dex.items.get(observed.consumed_item or "") if observed is not None else None
            ),
            observed_may_hold_item=(observed.may_hold_item if observed is not None else True),
            # Trapping needs to know whether they are a Ghost, which cannot be
            # trapped at all.
            observed_types=(self._observed_types(observed) if observed is not None else ()),
            # Guard Split and Power Split average two stats between the pair,
            # so both halves have to be on the table.
            attacker_stats=attacker.computed_stats,
            # Magnetic Flux only reaches an ally with Plus or Minus.
            ally_ability=ally.current_ability if ally is not None else None,
            # Healing Wish sends its healing to whoever comes in next, so the
            # question is who on the bench needs it most.
            bench_hp_fractions=tuple(
                mon.hp_fraction
                for index, mon in enumerate(observation.own_side.team)
                if not mon.fainted and index not in observation.own_side.active_slots
            ),
        )

    # ------------------------------------------------------------- learning

    # A hit big enough that residual damage -- a burn tick, Leftovers, sand --
    # cannot account for it. Learning from a 3% change would teach the belief
    # that everything hits like a feather.
    MIN_LEARNABLE_LOSS = 0.08

    def _learn_from(self, observation: Observation) -> None:
        """Update what we believe about their spreads, from the last turn.

        **Only unambiguous turns teach anything.** In doubles two of ours
        attack and two of theirs can lose health, and attributing the wrong
        damage to the wrong Pokemon is worse than not learning at all -- a
        wrong belief is acted on with exactly the confidence of a right one.
        So each direction below refuses to guess when the pairing is not
        forced.
        """
        before, action = self._previous, self._last_action
        if before is None or action is None or self.belief is None:
            return
        self._learn_what_we_dealt(before, observation, action)
        self._learn_what_we_took(before, observation)

    def _learn_what_we_dealt(self, before, now, action) -> None:
        """Their defending stat, from what our own attack did.

        Cleanly attributable: we know our move and our target exactly, because
        we chose them.
        """
        attacks = [
            (slot, act)
            for slot, act in enumerate(action.slot_actions)
            if isinstance(act, MoveAction) and act.target is not None and act.target.side == "foe"
        ]
        if len(attacks) != 1:
            return  # two attackers, and the damage cannot be split
        slot, act = attacks[0]
        attacker = self._own_active(before, slot)
        if attacker is None:
            return
        try:
            move = self.dex.get_move(attacker.selectable_moves[act.move_index])
            attacker_species = self.dex.get_species(attacker.pokemon_set.species)
        except (KeyError, IndexError):
            return
        if not move.is_damaging:
            return

        hurt = self._who_lost_health(before.opponent_side, now.opponent_side)
        if len(hurt) != 1:
            return  # more than one of theirs moved, so who took what?
        index, lost = hurt[0]
        seen = now.opponent_side.revealed[index]
        try:
            defender = self.dex.get_species(seen.species)
        except KeyError:
            return
        self.belief.note_hit_we_landed(
            move=move,
            attacker=attacker_species,
            attack_stat=self._attack_stat(attacker, move),
            defender=defender,
            defender_max_hp=self.belief.of(defender.name).stats(defender)["hp"],
            fraction_lost=lost,
            level=now.regulation.level,
            doubles=now.regulation.game_type == "doubles",
            weather=now.weather,
            terrain=now.terrain,
        )

    def _learn_what_we_took(self, before, now) -> None:
        """Their attacking stat, from what their attack did to us.

        Harder, because we did not choose it: which of the two attacked, and
        with what, is not stated. Only taken when exactly one of theirs could
        have thrown it and exactly one of ours was hit.
        """
        live = [
            index
            for index in now.opponent_side.active_slots
            if index is not None and not now.opponent_side.revealed[index].fainted
        ]
        if len(live) != 1:
            return
        seen = now.opponent_side.revealed[live[0]]
        fresh = (
            set(seen.revealed_moves) - set(before.opponent_side.revealed[live[0]].revealed_moves)
            if live[0] < len(before.opponent_side.revealed)
            else set()
        )
        candidates = [m for m in self._as_moves(fresh) if m.is_damaging]
        if len(candidates) != 1:
            return  # nothing new, or two new moves and no way to pick
        move = candidates[0]
        try:
            attacker = self.dex.get_species(seen.species)
        except KeyError:
            return

        hurt = self._our_losses(before, now)
        if len(hurt) != 1:
            return
        mon, lost = hurt[0]
        try:
            defender = self.dex.get_species(mon.pokemon_set.species)
        except KeyError:
            return
        self.belief.note_hit_we_took(
            move=move,
            attacker=attacker,
            defender=defender,
            defence_stat=apply_boost(
                (mon.computed_stats or {}).get(move.defensive_stat, 100),
                mon.boosts.stage(move.defensive_stat),
            ),
            our_max_hp=mon.max_hp,
            fraction_lost=lost,
            level=now.regulation.level,
            doubles=now.regulation.game_type == "doubles",
            weather=now.weather,
            terrain=now.terrain,
        )

    def _as_moves(self, ids) -> list[MoveInfo]:
        found = []
        for move_id in ids:
            try:
                found.append(self.dex.get_move(move_id))
            except KeyError:
                continue
        return found

    def _who_lost_health(self, before_side, now_side):
        """(index, fraction lost) for opponents that visibly took a hit."""
        losses = []
        for index, seen in enumerate(now_side.revealed):
            if index >= len(before_side.revealed):
                continue
            was = before_side.revealed[index].hp_percent
            lost = (was - seen.hp_percent) / 100
            if lost >= self.MIN_LEARNABLE_LOSS:
                losses.append((index, lost))
        return losses

    def _our_losses(self, before, now):
        """(Pokemon, fraction lost) for our own side, which we can see exactly."""
        losses = []
        for index, mon in enumerate(now.own_side.team):
            if index >= len(before.own_side.team):
                continue
            was = before.own_side.team[index]
            if was.pokemon_set.species != mon.pokemon_set.species:
                continue
            lost = (was.current_hp - mon.current_hp) / max(1, mon.max_hp)
            if lost >= self.MIN_LEARNABLE_LOSS:
                losses.append((mon, lost))
        return losses

    def _own_ability(self, attacker) -> str | None:
        """Our own ability, which we always know exactly.

        A method rather than a field read so an experiment can take it away.
        Abilities are the largest term in damage accuracy ever measured here --
        80.1% to 92% on random teams -- which makes "an agent that ignores
        them" the sharpest available test of whether damage accuracy buys
        games at all.
        """
        return attacker.current_ability

    def _opponent_stats(
        self, species: SpeciesInfo, *, attacking: str | None = None
    ) -> dict[str, int]:
        """What we believe this opponent's stats are.

        **The single point of assumption about the other side.** Stat Points
        are never published (ADR 0002), so this is a modelling choice rather
        than a fact: 66 points spread evenly over six stats, which no real team
        does. Gathered into one method so an experiment can replace it
        wholesale -- and so Milestone 10 has one thing to improve rather than
        six call sites to find.

        `attacking` credits the investment to the stat the move actually uses:
        an opponent swinging a physical move is likely built for it.
        """
        if self.belief is not None:
            return self.belief.stats(species)
        if attacking is not None:
            return assumed_stats(
                species.base_stats, self.assumed_opponent_points, attacking=attacking
            )
        return estimate_stats(species.base_stats, self.assumed_opponent_points)

    def _known_item(self, observed) -> str | None:
        """The opponent's item, if we have actually seen it.

        The other half of what we do not know about them, and the other thing
        an experiment needs to be able to replace.
        """
        return observed.revealed_item if observed is not None else None

    def _known_ability(self, observed) -> str | None:
        """The opponent's ability, if it is actually knowable.

        `revealed_ability` answers "have we watched it fire", and that is the
        wrong question for a species with only one to have. A Mega forme has
        exactly one -- all 77 of them -- so the forme change *is* the reveal:
        Metagross-Mega is Tough Claws and there is nothing else it could be.
        Waiting for it to announce itself throws away information every player
        at the table already has.

        The rule is not special to Mega. 42 base formes also have a single
        ability, so it is stated as what it is: one candidate means no doubt.
        Anything with a choice stays unknown until it shows itself.
        """
        if observed is None:
            return None
        if observed.revealed_ability:
            return observed.revealed_ability
        try:
            species = self.dex.get_species(observed.species)
        except KeyError:
            return None
        if len(species.abilities) == 1:
            return to_id(species.abilities[0])
        # Nothing revealed and more than one candidate. A corpus-derived prior
        # can still be better than silence: Rillaboom is in 39% of teams and
        # the corpus holds 2,292 Grassy Surge activations against no Overgrow.
        #
        # Guarded by the species' own legal list rather than trusted outright:
        # a prior built against one regulation must not name an ability this
        # forme cannot have.
        guess = self.ability_priors.get(to_id(observed.species))
        if guess and guess in {to_id(a) for a in species.abilities}:
            return guess
        return None

    def _observed_types(self, observed) -> tuple[str, ...]:
        try:
            species = self.dex.get_species(observed.species)
        except KeyError:
            return ()
        return effective_types(species.types, tuple(observed.volatile_conditions))

    def _boost_recipient(self, observation, slot, action, move, attacker, observed):
        """Who the stages land on, and whether that is good for us.

        Three answers, not two. A move can raise our own stats, raise our
        *partner's* -- Decorate is +2/+2 and one of the strongest things in
        doubles -- or raise an opponent's, which Swagger and Flatter do
        deliberately as the price of confusing them.
        """
        if move.target in SELF_TARGETS:
            return attacker, True
        aimed = action.target
        if aimed is not None and aimed.side == "ally":
            index = observation.own_side.active_slots[aimed.slot]
            if index is not None:
                partner = observation.own_side.team[index]
                if not partner.fainted:
                    return partner, True
            return None, True
        return observed, False

    def _boost_value(
        self, move, recipient, friendly, reasons, observation, slot, attacker
    ) -> float:
        """Stat stages the move applies, worth only the headroom that is left.

        A stage is capped at six either way, so a second Swords Dance at +5
        buys one stage and a third buys none. That headroom check is most of
        the value here: without it the agent will boost forever.

        Symmetric in who benefits. The old version counted only *rises* on our
        side and only *drops* on theirs, so a move that hands the opponent a
        boost -- Swagger's +2 Attack, the price of confusing them -- cost us
        nothing at all in the model.
        """
        value = 0.0
        if recipient is None:
            return value
        for stat, delta in move.boosts.items():
            field = BOOST_FIELDS.get(stat)
            if field is None:
                continue
            current = getattr(recipient.boosts, field)
            # How much of the change the cap actually allows.
            if delta >= 0:
                moved = max(0, min(delta, MAX_STAGE - current))
            else:
                moved = -max(0, min(-delta, current - MIN_STAGE))
            worth = None
            # An offensive rise on the user itself is the one case with a
            # closed form: it multiplies our own damage for as long as we are
            # around to deal it. See `tenure` -- the flat price below asks
            # whether our attack is weak when the trade turns on how long we
            # last. Everything else (allies, opponents, drops, Speed and the
            # defensive stats) keeps the flat rate; each is a different
            # calculation and changing one at a time is the only way to know
            # which one moved the result.
            if (
                self.tenure_boosts
                and recipient is attacker
                and stat in OFFENSIVE_STATS
                and moved > 0
            ):
                priced = self._tenure_priced_boost(
                    observation, slot, attacker, stat, current, moved
                )
                if priced is not None:
                    worth, tenure = priced
                    reasons.append(f"and should get ~{tenure:.1f} turns to use it")
            if worth is None:
                worth = moved * STAT_STAGE_VALUE * STAT_STAGE_WEIGHT
            # A rise helps whoever gets it; on their side that is our loss.
            value += worth if friendly else -worth
            whose = "our" if friendly else "their"
            if moved > 0:
                reasons.append(f"raises {whose} {stat} by {moved}")
            elif moved < 0:
                reasons.append(f"drops {whose} {stat} by {-moved}")
            elif delta > 0:
                reasons.append(f"{whose} {stat} is already maxed out")
            elif delta < 0:
                reasons.append(f"{whose} {stat} is already at the floor")

        # A move that lowers its user's own stats while doing something else.
        for stat, delta in move.self_boosts.items():
            if delta < 0:
                value += delta * STAT_STAGE_VALUE * STAT_STAGE_WEIGHT
                reasons.append(f"but costs us {-delta} stage(s) of {stat}")
        return value

    def _tenure_priced_boost(
        self, observation, slot, attacker, stat, current, moved
    ) -> tuple[float, float] | None:
        """What a rise to our own attacking stat buys, and over how many turns.

        `None` when the pieces are not there -- nobody to hit, or no move the
        boost would help -- so the caller falls back to the flat rate rather
        than pricing the move at zero. An unknown is a gap in what we can
        compute, not evidence the move is worthless.
        """
        observed = self._observed_target(observation, slot)
        if observed is None:
            return None
        damage = self._our_best_hit(
            observation,
            slot,
            observed,
            attacker.current_ability,
            self._known_ability(observed),
            offensive_stat=stat,
        )
        if damage <= 0.0:
            return None
        threat, _, _ = self._incoming_threat(observation, slot, attacker)
        tenure = expected_tenure(attacker.hp_fraction, threat)
        multiplier = stage_multiplier(current, current + moved)
        worth = (
            offensive_boost_value(
                multiplier,
                damage,
                tenure,
                target_fraction=observed.hp_percent / 100,
            )
            * DAMAGE_WEIGHT
        )
        return worth, tenure

    def _score_redirection(
        self, observation: Observation, slot: int, action, move, attacker
    ) -> "ScoredAction | None":
        """What drawing the opponent's attacks onto us is worth.

        Redirection moves damage rather than preventing it, so its value is the
        difference between what the hit costs the partner and what it costs us.
        `_incoming_threat` reports a fraction of the defender's own health bar,
        which is what makes the subtraction meaningful: the same attack can take
        60% of a frail partner and 30% of a bulky redirector.

        `None` when there is no partner to protect -- `score_support_move`
        already prices that case at zero, and a move that changes nothing should
        say so there rather than here.
        """
        if not self.redirect_weight:
            # Unpriced, which is the shipped behaviour: fall through to the
            # unknown-support value rather than scoring it at zero.
            return None

        own = observation.own_side
        partner_slot = next(
            (
                other
                for other in range(len(own.active_slots))
                if other != slot and own.active_slots[other] is not None
            ),
            None,
        )
        if partner_slot is None:
            return None
        partner = own.team[own.active_slots[partner_slot]]
        if partner.fainted:
            return None

        theirs, their_ko, _ = self._incoming_threat(observation, partner_slot, partner)
        ours, _, _ = self._incoming_threat(observation, slot, attacker)
        saved = theirs - ours

        # Redirecting spends the turn dealing no damage, and every other
        # turn-consuming move here charges for that: Protect has
        # PROTECT_TEMPO_COST, and the switch scorer subtracts the forgone
        # attack. Leaving it out priced the benefit and none of the cost, and
        # the first sweep duly found that using redirection more lost games at
        # every weight it changed anything (18-26% on the matchups it moved).
        forgone, _, _ = self._best_offence(observation, slot, attacker)

        score = saved * self.redirect_weight * DAMAGE_WEIGHT - forgone * DAMAGE_WEIGHT
        reasons = [
            f"{move.name} takes a ~{theirs:.0%} hit off "
            f"{partner.pokemon_set.species} and a ~{ours:.0%} one onto us"
        ]
        if their_ko:
            reasons.append(f"which would otherwise knock {partner.pokemon_set.species} out")
        if forgone > 0:
            reasons.append(f"but gives up a ~{forgone:.0%} hit this turn")
        return ScoredAction(action, score, tuple(reasons))

    def _status_move_status(self, move, observed, reasons) -> float:
        """A status the move inflicts, priced exactly as a rider would be."""
        if not move.status or observed is None:
            return 0.0
        try:
            species = self.dex.get_species(observed.species)
        except KeyError:
            return 0.0
        gain = self._status_value(move.status, species, observed)
        if not gain:
            reasons.append(f"{move.status} cannot land on that target")
            return 0.0
        reasons.append(f"inflicts {move.status}")
        return gain * STATUS_WEIGHT

    def _heal_value(self, move, attacker, reasons) -> float:
        """Healing, in the same currency as a drain of the same size.

        Clamped to the HP actually missing, which is the whole point: a
        Recover at full health restores nothing and used to score the same as
        one at death's door.
        """
        if not move.heal:
            return 0.0
        fraction = move.heal[0] / move.heal[1]
        missing = max(0, attacker.max_hp - attacker.current_hp) / max(1, attacker.max_hp)
        restored = min(fraction, missing)
        if restored <= 0:
            reasons.append("already at full HP, so the healing is wasted")
            return 0.0
        reasons.append(f"restores ~{restored:.0%} of its HP")
        return restored * SUSTAIN_WEIGHT

    def _field_value(self, move, observation, slot, attacker, reasons) -> float:
        """Screens, Tailwind, weather, terrain and Trick Room.

        Anything already up is worth nothing, which is the check that stops
        the agent re-setting its own Tailwind every turn.
        """
        value = 0.0

        if move.side_condition:
            condition = to_id(move.side_condition)
            if condition in observation.own_side.side_conditions:
                reasons.append(f"{move.name} is already up on our side")
            elif condition in SCREEN_CONDITIONS:
                # Priced off what it would actually block, like Protect.
                fraction, _, source = self._incoming_threat(observation, slot, attacker)
                blocked = fraction * SCREEN_FRACTION_BLOCKED * SCREEN_TURNS
                value += blocked * SCREEN_WEIGHT
                reasons.append(f"halves ~{fraction:.0%} incoming for several turns ({source})")
            else:
                worth = SIDE_CONDITION_VALUE.get(condition, STATUS_MOVE_VALUE)
                if condition == "tailwind":
                    worth *= self.speed_control_scale
                value += worth
                reasons.append(f"sets {move.side_condition} on our side")

        if move.sets_weather:
            if to_id(move.sets_weather) == (observation.weather or ""):
                reasons.append(f"{move.sets_weather} is already up")
            else:
                value += WEATHER_VALUE
                reasons.append(f"sets {move.sets_weather}")

        if move.sets_terrain:
            if to_id(move.sets_terrain) == (observation.terrain or ""):
                reasons.append(f"{move.sets_terrain} is already up")
            else:
                value += TERRAIN_VALUE
                reasons.append(f"sets {move.sets_terrain}")

        if move.pseudo_weather:
            condition = to_id(move.pseudo_weather)
            if condition == TRICK_ROOM and self.trick_room_by_speed:
                value += self._trick_room_value(observation, reasons)
            elif condition in observation.field_conditions:
                reasons.append(f"{move.pseudo_weather} is already up")
            else:
                worth = PSEUDO_WEATHER_VALUE.get(condition, PSEUDO_WEATHER_DEFAULT)
                if condition == "trickroom":
                    worth *= self.speed_control_scale
                value += worth
                reasons.append(f"sets {move.pseudo_weather}")

        return value

    def _speed_share(self, observation: Observation, *, trick_room: bool) -> float | None:
        """How often our active Pokemon move before theirs, pairing by pairing.

        Every (ours, theirs) pairing on the field counts once: 1 when ours
        moves first, 0.5 on a tie, 0 when theirs does. Priority is held equal,
        because Trick Room only reorders Pokemon within a priority bracket.
        None when there is no pairing to judge.
        """
        own = observation.own_side
        ours = [
            self._our_speed(observation, own.team[index])
            for index in own.active_slots
            if index is not None and own.team[index].current_hp > 0
        ]
        theirs = []
        opponent = observation.opponent_side
        for index in opponent.active_slots:
            if index is None:
                continue
            observed = opponent.revealed[index]
            if observed.fainted:
                continue
            try:
                species = self.dex.get_species(observed.species)
            except KeyError:
                continue
            theirs.append(self._their_speed(observation, observed, species))
        if not ours or not theirs:
            return None
        outcomes = [
            moves_first(0, mine, 0, other, trick_room=trick_room)
            for mine in ours
            for other in theirs
        ]
        return sum(outcomes) / len(outcomes)

    def _trick_room_value(self, observation: Observation, reasons: list[str]) -> float:
        """What flipping the speed order is worth to us -- which can be negative.

        Using Trick Room while it is up ends it (`onFieldRestart` calls
        `removePseudoWeather('trickroom')`), so the move is a toggle either
        way. It is priced as the change in `_speed_share` the toggle causes,
        scaled by the value the flat price already used: turning every pairing
        from lost to won is worth exactly what Trick Room used to be worth
        unconditionally, and turning every one from won to lost costs that
        much.

        Not modelled: how many turns an active Trick Room has left -- the
        tracker's `field_conditions` counter never counts, so an active one is
        treated as fresh -- and the benches, since what switches in next is not
        on the field yet.
        """
        up = TRICK_ROOM in observation.field_conditions
        now = self._speed_share(observation, trick_room=up)
        after = self._speed_share(observation, trick_room=not up)
        if now is None or after is None:
            reasons.append("no pairing on the field to judge Trick Room by")
            return 0.0
        change = after - now
        verb = "ends" if up else "sets"
        reasons.append(
            f"{verb} Trick Room: we move first in {after:.0%} of pairings, from {now:.0%}"
        )
        return PSEUDO_WEATHER_VALUE[TRICK_ROOM] * self.speed_control_scale * change

    def _volatile_value(self, move, observed, on_us, reasons) -> float:
        """Taunt, Encore, Leech Seed, Substitute and the rest.

        Judgements, ordered by how much of a turn the volatile takes away.
        Worth nothing when the target already has it.
        """
        if not move.volatile_status:
            return 0.0
        volatile = to_id(move.volatile_status)
        if on_us:
            reasons.append(f"puts {move.volatile_status} on us")
            return SELF_VOLATILE_VALUE.get(volatile, VOLATILE_DEFAULT)
        if observed is None:
            return 0.0
        if volatile in observed.volatile_conditions:
            reasons.append(f"they already have {move.volatile_status}")
            return 0.0
        reasons.append(f"inflicts {move.volatile_status}")
        return VOLATILE_VALUE.get(volatile, VOLATILE_DEFAULT)

    def _score_protect(
        self,
        observation: Observation,
        slot: int,
        action: MoveAction,
        move: MoveInfo,
        attacker,
    ) -> ScoredAction:
        """Worth what it stops, discounted by how likely it is to fail.

        Priced against the incoming attack rather than against our own HP bar.
        A healthy Pokemon facing a knockout should protect and a weakened one
        facing nothing should not, and a flat value cannot express either.
        """
        fraction, would_ko, source = self._incoming_threat(observation, slot, attacker)

        # The engine's stall counter: each consecutive use succeeds a third as
        # often as the last. This is the game's own rule rather than a tuned
        # constant, and it is what stops a threat-aware Protect being spammed.
        success = 1.0 / (3.0**attacker.protect_streak)

        score = fraction * PROTECT_DAMAGE_WEIGHT
        reasons = [f"{move.name} would block ~{fraction:.0%} of this Pokemon's HP ({source})"]
        if would_ko:
            score += PROTECT_SAVES_KO_BONUS
            reasons.append("which would otherwise be a knockout")

        score = score * success + PROTECT_TEMPO_COST
        if attacker.protect_streak:
            reasons.append(
                f"but it protected {attacker.protect_streak} turn(s) running, "
                f"so this succeeds ~{success:.0%} of the time"
            )
        return ScoredAction(action, score, tuple(reasons))

    def _incoming_threat(
        self,
        observation: Observation,
        slot: int,
        defender,
        defender_types: tuple[str, ...] | None = None,
    ) -> tuple[float, bool, str]:
        """Worst expected hit on this Pokemon: (fraction of its HP, would KO, why).

        Revealed moves are used when there are any. When there are none the
        opponent is *not* treated as harmless -- experiment 0001 found that
        assumption is exactly why one-turn search was inert. A standard STAB
        attack is assumed instead, from their typing, which is information we
        genuinely have the moment they are on the field.
        """
        try:
            defender_species = self.dex.get_species(defender.pokemon_set.species)
        except KeyError:
            return 0.0, False, "unknown defender"

        worst, worst_ko, source = 0.0, False, "nothing visible"
        for index in observation.opponent_side.active_slots:
            if index is None:
                continue
            observed = observation.opponent_side.revealed[index]
            if observed.fainted:
                continue
            found, found_ko, label = self._threat_from(
                observed, defender, defender_species, observation, defender_types
            )
            if found > worst:
                worst, worst_ko, source = found, found_ko, label
        return min(worst, 1.0), worst_ko, source

    def _threat_from(
        self,
        observed,
        defender,
        defender_species,
        observation: Observation,
        defender_types: tuple[str, ...] | None = None,
    ) -> tuple[float, bool, str]:
        """Worst hit *one* named opponent could land on this Pokemon.

        Split out of `_incoming_threat`, which took the maximum over both and
        discarded which one it came from -- and knowing which one is exactly
        what target selection needs.
        """
        worst, worst_ko, source = 0.0, False, "nothing visible"
        try:
            species = self.dex.get_species(observed.species)
        except KeyError:
            return 0.0, False, "unknown attacker"

        known = [m for m in self._revealed_moves(observed) if m.is_damaging]
        candidates = known or assumed_attacks(species)
        label = "seen" if known else "assumed"

        for move in candidates:
            attacking = move.offensive_stat
            defending = move.defensive_stat
            # Credit investment to the stat the move actually uses: an
            # opponent swinging a physical move is likely built for it.
            stats = self._opponent_stats(species, attacking=attacking)
            # A Foul Play aimed at us swings with *our* Attack, which is
            # exactly why it is dangerous into our own physical attacker.
            swinging_stats, swinging_boosts = attacking_side(
                move,
                user=(stats, observed.boosts),
                target=(defender.computed_stats or {}, defender.boosts),
            )
            estimate = estimate_damage(
                self.dex,
                move,
                attacker=species,
                attack_stat=apply_boost(
                    swinging_stats.get(attacking, 100),
                    swinging_boosts.stage(attacking),
                ),
                defender=defender_species,
                defense_stat=apply_boost(
                    (defender.computed_stats or {}).get(defending, 100),
                    defender.boosts.stage(defending),
                ),
                defender_hp=max(1, defender.current_hp),
                level=observation.regulation.level,
                doubles=observation.regulation.game_type == "doubles",
                weather=observation.weather,
                # Set when something has rewritten our typing -- Reflect Type
                # is worth exactly the difference this makes.
                defender_types=defender_types,
            )
            expected = estimate.average_fraction * move.hit_chance
            if expected > worst:
                worst = expected
                worst_ko = estimate.guaranteed_ko
                source = f"{species.name}, {label}"
        return min(worst, 1.0), worst_ko, source

    def _revealed_moves(self, observed) -> list[MoveInfo]:
        found = []
        for move_id in observed.revealed_moves:
            try:
                found.append(self.dex.get_move(move_id))
            except KeyError:
                continue
        return found

    # ------------------------------------------------------------- resolution

    @staticmethod
    def _own_active(observation: Observation, slot: int):
        index = observation.own_side.active_slots[slot]
        return None if index is None else observation.own_side.team[index]

    @staticmethod
    def _attack_stat(attacker, move: MoveInfo) -> int:
        """The attacking stat as it stands *now*, stat stages included.

        Takes the move rather than its category because the two can disagree:
        Body Press is Physical and swings with Defense.

        Boosts were tracked in the domain model and `apply_boost` was written
        for exactly this, and nothing called either: a Pokemon that had just
        used Swords Dance scored identically to one that had not. Measured
        against 5,123 real attacks, applying them lifts predictions within ten
        points of the true damage from 35.8% to 39.2%.
        """
        key = move.offensive_stat
        # Falling back to a mid value keeps a missing stat from reading as a
        # devastating or useless attacker.
        base = (attacker.computed_stats or {}).get(key, 100)
        return apply_boost(base, attacker.boosts.stage(key))

    def _resolve_target(
        self,
        observation: Observation,
        slot: int,
        action: MoveAction,
        move: MoveInfo | None = None,
    ) -> "ResolvedTarget | None":
        """What the move is aimed at, with the stats the move will read off it.

        Spread moves carry no explicit target, so the first live opponent
        stands in -- enough to rank the move, though it undercounts a move
        that would hit both.
        """
        # `move` is passed in when something is standing in for the move the
        # action names -- a Copycat resolves its target as whatever it copied.
        if move is None:
            move = self.dex.get_move(attacker_move_id(observation, slot, action))
        defending_key = move.defensive_stat
        # Darkest Lariat and Sacred Sword ignore the target's defensive stages
        # outright, which is the whole reason to bring them into a boosted
        # matchup.
        guard_stage = 0 if move.ignore_defensive else None
        # Foul Play swings with the target's Attack, so the attacking stat has
        # to be gathered here, where the target is known.
        attacking_key = move.offensive_stat if move.uses_target_offense else None

        if action.target is not None and action.target.side == "ally":
            index = observation.own_side.active_slots[action.target.slot]
            if index is None:
                return None
            ally = observation.own_side.team[index]
            try:
                species = self.dex.get_species(ally.pokemon_set.species)
            except KeyError:
                return None
            stats = ally.computed_stats or {}
            return ResolvedTarget(
                species=species,
                remaining_hp=max(1, ally.current_hp),
                defending_stat=apply_boost(
                    stats.get(defending_key, 100),
                    guard_stage if guard_stage is not None else ally.boosts.stage(defending_key),
                ),
                is_ally=True,
                status=ally.status,
                item=ally.current_item,
                ability=ally.current_ability,
                may_hold_item=ally.current_item is not None,
                at_full_hp=ally.current_hp >= ally.max_hp,
                turns_on_field=ally.turns_on_field,
                volatiles=tuple(ally.volatile_conditions),
                attacking_stat=None
                if attacking_key is None
                else apply_boost(stats.get(attacking_key, 100), ally.boosts.stage(attacking_key)),
            )

        foe_slot = action.target.slot if action.target is not None else None
        opponent = observation.opponent_side
        candidates = [foe_slot] if foe_slot is not None else list(range(len(opponent.active_slots)))
        for candidate in candidates:
            if candidate >= len(opponent.active_slots):
                continue
            index = opponent.active_slots[candidate]
            if index is None:
                continue
            observed = opponent.revealed[index]
            if observed.fainted:
                continue
            try:
                species = self.dex.get_species(observed.species)
            except KeyError:
                continue
            estimated = self._opponent_stats(species)
            remaining = max(1, estimated["hp"] * observed.hp_percent // 100)
            return ResolvedTarget(
                species=species,
                remaining_hp=remaining,
                defending_stat=apply_boost(
                    estimated[defending_key],
                    guard_stage
                    if guard_stage is not None
                    else observed.boosts.stage(defending_key),
                ),
                is_ally=False,
                index=index,
                status=observed.status,
                item=self._known_item(observed),
                ability=self._known_ability(observed),
                may_hold_item=observed.may_hold_item,
                turns_on_field=observed.turns_on_field,
                at_full_hp=observed.hp_percent >= 100,
                volatiles=tuple(observed.volatile_conditions),
                # Uniform rather than credited: the calibrated attacking
                # investment is evidence from *using* a move, and a Foul Play
                # target is not the one using it.
                attacking_stat=None
                if attacking_key is None
                else apply_boost(estimated[attacking_key], observed.boosts.stage(attacking_key)),
            )
        return None

    # --------------------------------------------------------- team preview

    def select_team_preview(self, preview: TeamPreview, picked_team_size: int) -> TeamPreviewAction:
        """Pick which Pokemon to bring, and in what order, from the matchup.

        The first decision of every battle, and the one a player most wants
        help with -- they can see six species and nothing else.

        Scored as **coverage** rather than as a sum of individually good
        Pokemon. A team wins Team Preview by having an answer to each thing the
        opponent brought, so for every one of their six we take our *best*
        answer among the four we are considering, and add those up. Picking
        four Pokemon that all beat the same threat and lose to the rest scores
        badly, which is the point.
        """
        picks = self._rank_team_preview(preview, picked_team_size)
        return TeamPreviewAction(picks=picks)

    def _rank_team_preview(self, preview: TeamPreview, picked_team_size: int) -> tuple[int, ...]:
        return self._best_team_preview(preview, picked_team_size)[0]

    def _best_team_preview(
        self, preview: TeamPreview, picked_team_size: int
    ) -> tuple[tuple[int, ...], tuple[str | None, str | None]]:
        """The four to bring in lead order, and the field our side sets with them.

        Every candidate four is scored with one stone holder evolving and in the
        weather and terrain its own setters put up. Rows are computed once per
        distinct field -- there are only a handful -- not once per four.
        """
        bare: tuple[str | None, str | None] = (None, None)
        rows_by_field: dict[tuple[str | None, str | None], tuple] = {}

        def rows(field):
            if field not in rows_by_field:
                rows_by_field[field] = self._team_preview_rows(preview, own_field=field)
            return rows_by_field[field]

        base, mega = rows(bare)
        if not base:
            return tuple(range(picked_team_size)), bare

        best_set, best_score, best_table, best_field = None, float("-inf"), base, bare
        # Six choose four is fifteen combinations, so the exhaustive answer is
        # cheaper than any clever approximation would be -- and still is with
        # each Mega Stone holder in a selection tried as the one that evolves.
        for candidate in combinations(range(len(preview.own_team)), picked_team_size):
            for chosen in self._mega_choices(preview, candidate, mega):
                field = self._own_field(preview, candidate, chosen) if self.own_field else bare
                field_base, field_mega = rows(field)
                scores = [
                    field_mega[index] if index == chosen else field_base[index]
                    for index in range(len(field_base))
                ]
                score = self._score_selection(candidate, scores, len(preview.opponent_team))
                if score > best_score:
                    best_set, best_score, best_table, best_field = candidate, score, scores, field

        assert best_set is not None
        # Lead with the two that fare best against their roster as a whole,
        # since which of their six leads is still unknown.
        ordered = tuple(
            sorted(
                best_set,
                key=lambda index: sum(best_table[index]) / max(1, len(best_table[index])),
                reverse=True,
            )
        )
        return ordered, best_field

    def matchup_table(self, preview: TeamPreview) -> list[list[float]]:
        """`table[ours][theirs]` -- our net matchup against each of their six.

        Public because it is the reasoning behind the Team Preview pick, and
        a player looking at six unfamiliar species wants the grid far more
        than they want the conclusion drawn from it.
        """
        # Drawn in the field the recommended four would set, so a team that
        # brings its own weather is shown in that weather.
        _, field = self._best_team_preview(preview, preview.regulation.picked_team_size)
        base, mega = self._team_preview_rows(preview, own_field=field)
        # The grid shows a Mega Stone holder as the Mega it will become. When
        # two holders are brought only one can evolve; the ranking accounts for
        # that, and the grid shows each at its best.
        return [
            mega_row if mega_row is not None else base_row
            for base_row, mega_row in zip(base, mega)
        ]

    def _team_preview_rows(
        self,
        preview: TeamPreview,
        own_field: tuple[str | None, str | None] = (None, None),
    ) -> tuple[list[list[float]], list[list[float] | None]]:
        """Our six against their six: each as itself, and as its Mega if it holds its stone.

        The Mega rows are None for a Pokemon that cannot evolve, and for every
        Pokemon when `own_megas` is off.
        """
        # What field their six is likely to put up. None is set *yet* -- the
        # battle has not started -- but a team with Pelipper is going to be in
        # rain, and scoring the grid on a bare field is scoring a battle that
        # will not happen. Measured rather than asserted: a previewed Pelipper
        # reaches the field 68% of the time and Rillaboom 59%, so each effect
        # is weighted by its own probability rather than switched on.
        predicted = self._predicted_field(preview.opponent_team)
        shared = dict(
            level=preview.regulation.level,
            doubles=preview.regulation.game_type == "doubles",
            assumed_points=self.assumed_opponent_points,
        )
        base: list[list[float]] = []
        mega: list[list[float] | None] = []
        for ours in preview.own_team.pokemon:
            base.append(self._preview_row(ours, preview, predicted, shared, own_field))
            evolved = self._own_mega_set(ours) if self.own_megas else None
            mega.append(
                None
                if evolved is None
                else self._preview_row(evolved, preview, predicted, shared, own_field)
            )
        return base, mega

    def _preview_row(
        self, ours, preview: TeamPreview, predicted, shared, own_field=(None, None)
    ) -> list[float]:
        row: list[float] = []
        for theirs in preview.opponent_team:
            try:
                species = self.dex.get_species(theirs.species)
                row.append(
                    self._opponent_blended_net(ours, species, predicted, shared, own_field)
                )
            except KeyError:
                # Missing data must not read as a good or bad matchup.
                row.append(0.0)
        return row

    def _opponent_blended_net(
        self, ours, species: SpeciesInfo, predicted, shared, own_field=(None, None)
    ) -> float:
        """Our matchup against a previewed species, allowing that it may Mega Evolve.

        The expectation over "it evolves" and "it does not", weighted by how
        often the species evolves once it takes the field. That rate conflates
        carrying the stone with using it, which is exactly the uncertainty Team
        Preview has about an opponent. Without a measured rate the species is
        scored as itself.
        """
        net = self._preview_net(ours, species, predicted, shared, own_field)
        if not self.opponent_megas:
            return net
        found = self.mega_priors.get(to_id(species.base_species))
        if found is None:
            return net
        forme_name, rate = found
        try:
            forme = self.dex.get_species(forme_name)
        except KeyError:
            return net
        return net + rate * (
            self._preview_net(ours, forme, predicted, shared, own_field) - net
        )

    def _preview_net(
        self, ours, species: SpeciesInfo, predicted, shared, own_field=(None, None)
    ) -> float:
        own = self._set_for_matchup(ours)
        weather, terrain = own_field
        # Our own setters decide their kind of field outright: we choose to
        # bring them, and they set it the moment they arrive.
        fixed = {
            kind: value
            for kind, value in (("weather", weather), ("terrain", terrain))
            if value is not None
        }
        costs = {
            "price_turn_costs": self.matchup_turn_costs,
            "speed_beyond_knockouts": self.speed_beyond_knockouts,
            "speed_race_credit": self.speed_race_credit,
        }
        net = matchup(self.dex, ours, species, **shared, **own, **fixed, **costs).net
        # Each predicted effect of the *opponent's* contributes its own marginal
        # change, weighted by how likely it is -- except where our own setter
        # has already decided that kind of field. With one effect this is
        # exactly the expectation; with two it is a linear approximation of it,
        # which is the honest simplification.
        for effect, kind, chance in predicted:
            if kind in fixed:
                continue
            shifted = matchup(
                self.dex, ours, species, **{kind: effect}, **shared, **own, **fixed, **costs
            ).net
            net += chance * (shifted - net)
        return net

    def _set_for_matchup(self, pokemon_set: PokemonSet) -> dict[str, str | None]:
        """Our ability and item as `matchup()` takes them, from a team sheet.

        Converted to ids: a set parsed from an export says "Damp Rock" and
        "Drizzle", while every rule table is keyed "damprock" and "drizzle" --
        passing the names through would have matched nothing, silently.
        """
        if not self.matchup_reads_our_set:
            return {}
        return {
            "our_ability": to_id(pokemon_set.ability) or None,
            "our_item": to_id(pokemon_set.item) if pokemon_set.item else None,
        }

    def _own_mega_set(self, pokemon_set: PokemonSet) -> PokemonSet | None:
        """The set as its Mega forme, if it holds the stone for its own species.

        Item first, never species first: a species with two Megas has two
        stones, and asking the species for "its" stone returns whichever is
        found first -- the trap `Dex.mega_stone_for` documents. Stat Points,
        moves and nature carry over; `own_stats` rebuilds the stats from the
        forme's base.
        """
        stone = self.dex.items.get(to_id(pokemon_set.item or ""))
        if stone is None or not stone.mega_forme:
            return None
        try:
            species = self.dex.get_species(pokemon_set.species)
            forme = self.dex.get_species(stone.mega_forme)
        except KeyError:
            return None
        if stone.mega_stone not in (species.name, species.base_species):
            return None
        ability = to_id(forme.abilities[0]) if forme.abilities else pokemon_set.ability
        return pokemon_set.model_copy(update={"species": forme.name, "ability": ability})

    def _mega_assignments(
        self,
        preview: TeamPreview,
        selection: tuple[int, ...],
        base: list[list[float]],
        mega: list[list[float] | None],
    ) -> list[list[list[float]]]:
        """The score tables a selection could be played with: one holder evolves.

        No holder in the selection: the base table. Several: with measured
        rates, only the holder players evolve most often (ties keep all of
        them); without rates, every holder is tried and the ranking keeps the
        best, which is the agent choosing for itself.
        """
        return [
            [mega[index] if index == chosen else base[index] for index in range(len(base))]
            for chosen in self._mega_choices(preview, selection, mega)
        ]

    def _mega_choices(
        self,
        preview: TeamPreview,
        selection: tuple[int, ...],
        mega: list[list[float] | None],
    ) -> list[int | None]:
        """Which holder in a selection evolves; [None] when none can.

        Several holders: with measured rates, only the one players evolve most
        often (ties keep all of them); without rates, every holder, and the
        ranking keeps the best.
        """
        holders = [index for index in selection if mega[index] is not None]
        if not holders:
            return [None]
        if self.mega_priors:
            rates = {index: self._mega_rate(preview.own_team.pokemon[index]) for index in holders}
            top = max(rates.values())
            holders = [index for index in holders if rates[index] == top]
        return holders

    def _own_field(
        self, preview: TeamPreview, selection: tuple[int, ...], chosen: int | None
    ) -> tuple[str | None, str | None]:
        """The weather and terrain this four puts up on its own.

        Read off each member's ability -- the evolving holder's *forme* ability,
        since a forme that sets weather does so the moment it evolves.

        Simplifications, stated rather than hidden: the field is treated as up
        for the whole matchup, with no duration and no opposing setter taking
        it back; and with two setters of one kind in a four, the first in team
        order wins, because which lands last is a battle event Team Preview
        cannot see.
        """
        weather = terrain = None
        for index in selection:
            pokemon_set = preview.own_team.pokemon[index]
            if index == chosen:
                pokemon_set = self._own_mega_set(pokemon_set) or pokemon_set
            ability = to_id(pokemon_set.ability)
            weather = weather or weather_on_arrival(ability)
            terrain = terrain or terrain_on_arrival(ability)
        return weather, terrain

    def _mega_rate(self, pokemon_set: PokemonSet) -> float:
        """How often this species Mega Evolves on the field; 0 when never measured."""
        try:
            base_species = self.dex.get_species(pokemon_set.species).base_species
        except KeyError:
            return 0.0
        found = self.mega_priors.get(to_id(base_species))
        return found[1] if found is not None else 0.0

    def _predicted_field(self, opponent_team) -> list[tuple[str, str, float]]:
        """The likeliest weather and terrain their six will establish.

        At most one of each: two weathers cannot both be up, and the same for
        terrain, so the stronger prediction wins rather than both being
        applied. An empty list is the old behaviour exactly.
        """
        best: dict[str, tuple[str, str, float]] = {}
        for entry in opponent_team:
            found = self.field_priors.get(to_id(entry.species))
            if found is None:
                continue
            effect, kind, chance = found
            if kind not in best or chance > best[kind][2]:
                best[kind] = (effect, kind, chance)
        return list(best.values())

    @staticmethod
    def _score_selection(
        selection: tuple[int, ...], scores: list[list[float]], opponents: int
    ) -> float:
        coverage = sum(max(scores[index][foe] for index in selection) for foe in range(opponents))
        average = sum(scores[index][foe] for index in selection for foe in range(opponents)) / max(
            1, len(selection) * opponents
        )
        return COVERAGE_WEIGHT * coverage + AVERAGE_WEIGHT * average

    def explain_team_preview(
        self, preview: TeamPreview, picked_team_size: int
    ) -> tuple[tuple[str, float], ...]:
        """Per-pick reasons, for the recommendation system."""
        scores = self.matchup_table(preview)
        picks = self._rank_team_preview(preview, picked_team_size)
        reasons = []
        for index in picks:
            row = scores[index]
            worst = min(range(len(row)), key=lambda foe: row[foe])
            best = max(range(len(row)), key=lambda foe: row[foe])
            reasons.append(
                (
                    f"{preview.own_team.pokemon[index].species}: "
                    f"best into {preview.opponent_team[best].species}, "
                    f"worst into {preview.opponent_team[worst].species}",
                    sum(row) / max(1, len(row)),
                )
            )
        return tuple(reasons)


def attacker_move_id(observation: Observation, slot: int, action: MoveAction) -> str:
    index = observation.own_side.active_slots[slot]
    assert index is not None
    return observation.own_side.team[index].selectable_moves[action.move_index]
