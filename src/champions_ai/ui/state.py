"""A typed position as JSON, for the browser client.

The terminal client asks a player to type what is on screen, which is fast to
read and slow to type: about forty seconds a turn, most of it spent naming
things. The browser client turns the same facts into buttons, and every button
sends exactly the line `position.commands` already accepts -- so the language,
its refusals and its tests stay the one source of truth, and this module only
answers "what is there to press".

Nothing here decides anything. It reads a `Position`, and the advice the
recommender produced, into plain dictionaries.
"""

import traceback

from champions_ai.domain import Observation
from champions_ai.position import Position

STAGES = (
    ("atk", "attack"),
    ("def", "defense"),
    ("spa", "special_attack"),
    ("spd", "special_defense"),
    ("spe", "speed"),
    ("acc", "accuracy"),
    ("eva", "evasion"),
)


def _name(dex, species: str) -> str:
    """The dex spelling, falling back to whatever was typed."""
    try:
        return dex.get_species(species).name
    except (KeyError, AttributeError):
        return species


def _stages(boosts) -> dict[str, int]:
    """Only the stages that are not zero: the rest are noise on a board."""
    return {short: getattr(boosts, attr) for short, attr in STAGES if getattr(boosts, attr)}


def _move(dex, move_id: str, pp: int | None, disabled: bool) -> dict:
    entry = {"id": move_id, "name": move_id, "pp": pp, "disabled": disabled,
             "type": None, "power": None}
    try:
        move = dex.get_move(move_id)
    except (KeyError, AttributeError):
        return entry
    entry["name"] = move.name
    entry["type"] = move.type
    entry["power"] = move.base_power or None
    return entry


def _ours(position: Position, dex, index: int) -> dict:
    mon = position.own.team[index]
    slot = next((s for s, i in enumerate(position.own.active_slots) if i == index), None)
    pp = mon.move_pp
    return {
        "index": index,
        "species": _name(dex, mon.pokemon_set.species),
        "id": mon.pokemon_set.species,
        "hp_percent": mon.hp_percent,
        "fainted": mon.fainted,
        "status": mon.status,
        "stages": _stages(mon.boosts),
        "item": mon.current_item,
        "ability": mon.current_ability,
        "slot": slot,
        "moves": [
            _move(dex, move_id, pp[order] if pp else None, move_id in mon.disabled_moves)
            for order, move_id in enumerate(mon.selectable_moves)
        ],
    }


def _theirs(position: Position, dex, index: int) -> dict:
    mon = position.their_seen[index]
    slot = next((s for s, i in enumerate(position.their_active) if i == index), None)
    return {
        "index": index,
        "species": _name(dex, mon.species),
        "id": mon.species,
        "hp_percent": mon.hp_percent,
        "fainted": mon.fainted,
        "status": mon.status,
        "stages": _stages(mon.boosts),
        "item": mon.revealed_item,
        "item_gone": mon.item_consumed,
        "ability": mon.revealed_ability,
        "slot": slot,
        "moves": sorted(mon.revealed_moves),
        "seen": True,
    }


def board(position: Position, dex) -> dict:
    """Both sides, the field and the turn, as the client draws them."""
    seen_ids = {mon.species for mon in position.their_seen}
    unseen = [
        {"id": species, "species": _name(dex, species), "seen": False}
        for species in position.their_team
        if species not in seen_ids
    ]
    return {
        "turn": position.turn,
        "weather": position.weather,
        "terrain": position.terrain,
        "field_conditions": dict(position.field_conditions),
        "ours": {
            "team": [_ours(position, dex, i) for i in range(len(position.own.team))],
            "active": list(position.own.active_slots),
            "side_conditions": dict(position.own.side_conditions),
            "mega_used": position.own.mega_used,
        },
        "theirs": {
            "seen": [_theirs(position, dex, i) for i in range(len(position.their_seen))],
            "unseen": unseen,
            "active": list(position.their_active),
            "side_conditions": dict(position.their_side_conditions),
            "mega_used": position.their_mega_used,
        },
    }


def _entry(recommendation) -> dict:
    # The cost, not the confidence: the confidence is a softmax share at a
    # temperature nobody swept, and the cost is measured by rollout (0041).
    if recommendation.rank == 1:
        note = "top choice"
    elif recommendation.cost is not None:
        note = str(recommendation.cost)
    else:
        note = "not measured"
    return {
        "rank": recommendation.rank,
        "description": recommendation.description,
        "note": note,
        "reasons": list(recommendation.reasons[:3]),
    }


def advice(position: Position, dex, move_data, recommender) -> dict:
    """The ranked shortlist, or why there is not one.

    Every refusal the terminal client prints is reported here in the same
    terms. A client that showed an empty list for "no move data" would be
    inviting the player to read the absence as "nothing good to do".
    """
    from champions_ai.domain import legal_joint_actions

    try:
        observation: Observation = position.observation()
    except ValueError as error:
        return {"problem": f"That position does not hold together: {error}"}
    if all(index is None for index in observation.own_side.active_slots):
        return {"problem": "Nobody of yours is on the field."}
    try:
        legal = legal_joint_actions(observation, move_data)
    except KeyError as error:
        return {"problem": f"No move data for {error}, so this position cannot be scored."}
    if not legal:
        return {"problem": "No legal action from here, which usually means a switch is owed."}

    try:
        ranked = recommender.recommend(observation, legal)
    except Exception as error:  # noqa: BLE001 - reported to the player, not swallowed
        # A scoring bug on a position nobody tested must not take the page down
        # with it: the request would fail, the page would keep the last board,
        # and that reads exactly like "no recommendation". Say what broke, and
        # put the traceback in the terminal for the bug report.
        traceback.print_exc()
        return {
            "problem": f"The adviser failed on this position ({type(error).__name__}: {error}). "
                       "The board still works; the terminal has the details."
        }
    return {
        "considered": ranked.considered,
        "clear": ranked.is_clear,
        "recommendations": [_entry(entry) for entry in ranked.recommendations],
    }
