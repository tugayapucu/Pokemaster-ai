"""A hand-built battle that unit tests can reconstruct without Node.

Shared because two things now need it -- observation reconstruction and the
human-agreement benchmark -- and a second copy would drift from the first.

The log is shaped after a real replay header rather than invented: `|teamsize|`
comes *after* Team Preview and reports the picked 4, not the declared 6, which
was verified against both a live engine battle and a published replay.
"""

import pytest

from champions_ai.data.reconstruct import reconstruct_decisions
from champions_ai.data.replay import Replay, ReplayMetadata
from champions_ai.dex import Dex
from champions_ai.domain import REGULATION_M_B


def _species(name, hp, atk, df, spa, spd, spe, types):
    return {
        "name": name,
        "types": list(types),
        "baseStats": {"hp": hp, "atk": atk, "def": df, "spa": spa, "spd": spd, "spe": spe},
        "abilities": [],
        "weightkg": 1.0,
        "baseSpecies": name,
    }


def _move(name, target, power=80, category="Physical", move_type="Normal"):
    return {
        "name": name,
        "type": move_type,
        "category": category,
        "basePower": power,
        "accuracy": 100,
        "priority": 0,
        "target": target,
        "flags": [],
    }


TYPES = ["Normal", "Fire", "Flying", "Dragon", "Ground", "Dark"]

DEX = Dex.from_payload(
    {
        "species": {
            "charizard": _species("Charizard", 78, 84, 78, 109, 85, 100, ("Fire", "Flying")),
            "charizardmegay": _species(
                "Charizard-Mega-Y", 78, 104, 78, 159, 115, 100, ("Fire", "Flying")
            ),
            "garchomp": _species("Garchomp", 108, 130, 95, 80, 85, 102, ("Dragon", "Ground")),
            "dragonite": _species("Dragonite", 91, 134, 95, 100, 100, 80, ("Dragon", "Flying")),
            "incineroar": _species("Incineroar", 95, 115, 90, 80, 90, 60, ("Fire", "Dark")),
            "torkoal": _species("Torkoal", 70, 85, 140, 85, 70, 20, ("Fire",)),
        },
        "moves": {
            "heatwave": _move(
                "Heat Wave", "allAdjacentFoes", category="Special", move_type="Fire"
            ),
            "protect": _move("Protect", "self", power=0, category="Status"),
            "earthquake": _move("Earthquake", "allAdjacent", move_type="Ground"),
            "fakeout": _move("Fake Out", "normal"),
            "knockoff": _move("Knock Off", "normal", move_type="Dark"),
            "dragonclaw": _move("Dragon Claw", "normal", move_type="Dragon"),
        },
        "types": TYPES,
        "chart": {a: dict.fromkeys(TYPES, 1.0) for a in TYPES},
    }
)

LOG = (
    "|player|p1|Alice|1|1600",
    "|player|p2|Bob|2|1580",
    "|gametype|doubles",
    "|teampreview|4",
    "|teamsize|p1|4",
    "|teamsize|p2|4",
    "|start",
    "|switch|p1a: Charizard|Charizard, L50, M|100/100",
    "|switch|p1b: Garchomp|Garchomp, L50, F|100/100",
    "|switch|p2a: Incineroar|Incineroar, L50, M|100/100",
    "|switch|p2b: Torkoal|Torkoal, L50, F|100/100",
    "|turn|1",
    "|move|p1a: Charizard|Heat Wave|p2a: Incineroar|[spread] p2a,p2b",
    "|-damage|p2a: Incineroar|70/100",
    "|move|p1b: Garchomp|Protect",
    "|move|p2a: Incineroar|Fake Out|p1a: Charizard",
    "|-damage|p1a: Charizard|82/100",
    "|turn|2",
    "|switch|p1a: Dragonite|Dragonite, L50, M|100/100",
    "|move|p1b: Garchomp|Earthquake",
    "|move|p2a: Incineroar|Knock Off|p1b: Garchomp",
    "|turn|3",
    "|move|p1a: Dragonite|Dragon Claw|p2a: Incineroar",
    "|move|p1b: Garchomp|Protect",
    "|move|p2b: Torkoal|Heat Wave|p1a: Dragonite|[spread] p1a,p1b",
    "|turn|4",
)


class SampleBattle:
    """The fixture's API: build decisions, then find things inside them."""

    dex = DEX
    log = LOG
    regulation = REGULATION_M_B

    def through(self, marker, log=LOG):
        """Everything up to and including `marker`.

        Sliced by content rather than index, so inserting a line into LOG
        cannot silently retarget a test at a different turn.
        """
        return log[: log.index(marker) + 1]

    def replay(self, log=LOG):
        return Replay(
            metadata=ReplayMetadata(
                replay_id="test",
                format_id=REGULATION_M_B.format_id,
                players=("Alice", "Bob"),
                ratings=(1600, 1580),
                upload_time=0,
                rated=True,
            ),
            log=log,
        )

    def decisions(self, log=LOG):
        return reconstruct_decisions(self.replay(log), REGULATION_M_B, DEX)

    def at(self, decisions, turn, player):
        found = [d for d in decisions if d.turn == turn and d.player == player]
        assert found, f"no decision for turn {turn}, player {player}"
        return found[0]

    def own(self, decision, species):
        for mon in decision.observation.own_side.team:
            if mon.pokemon_set.species == species:
                return mon
        raise AssertionError(f"{species} not on own side")

    def foe(self, decision, species):
        for mon in decision.observation.opponent_side.revealed:
            if mon.species == species:
                return mon
        raise AssertionError(f"{species} not revealed")


@pytest.fixture(scope="session")
def battle() -> SampleBattle:
    return SampleBattle()
