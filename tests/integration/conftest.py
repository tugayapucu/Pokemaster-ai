import shutil

import pytest

from champions_ai.data import BattleTeam, TeamPool, parse_showdown_team
from champions_ai.domain import REGULATION_M_B
from champions_ai.env import BattleEnv
from champions_ai.simulator import ShowdownBridge

# Showdown's Champions random-team generator. Not Reg M-B aware -- it's only a
# source of plausible sets, which the validator then filters.
TEAM_GENERATOR = "gen9championsrandombattle"

# Legal Reg M-B, verified with TeamValidator. Random teams are fine for "does a
# battle run", but a test asserting on Mega needs a team known to hold a stone --
# otherwise it passes or fails by luck rather than correctness.
#
# Building this also surfaced real roster facts: Champions has a restricted
# Pokedex (Amoonguss is absent entirely) and restricted learnsets (Charizard
# has no Tailwind, Grimmsnarl no Thunder Wave).
MEGA_TEAM = """
Charizard @ Charizardite Y
Ability: Blaze
Level: 50
EVs: 32 SpA / 32 Spe
Timid Nature
- Heat Wave
- Solar Beam
- Protect
- Flamethrower

Garchomp @ Life Orb
Ability: Rough Skin
Level: 50
EVs: 32 Atk / 32 Spe
Jolly Nature
- Earthquake
- Rock Slide
- Protect
- Swords Dance

Incineroar @ Sitrus Berry
Ability: Intimidate
Level: 50
EVs: 32 HP / 32 SpD
Careful Nature
- Fake Out
- Flare Blitz
- Parting Shot
- Protect

Gholdengo @ Leftovers
Ability: Good as Gold
Level: 50
EVs: 32 HP / 32 SpA
Modest Nature
- Make It Rain
- Shadow Ball
- Nasty Plot
- Protect

Annihilape @ Focus Sash
Ability: Defiant
Level: 50
EVs: 32 Atk / 32 Spe
Adamant Nature
- Rage Fist
- Close Combat
- Bulk Up
- Protect

Grimmsnarl @ Light Clay
Ability: Prankster
Level: 50
EVs: 32 HP / 32 SpD
Careful Nature
- Reflect
- Light Screen
- Spirit Break
- Play Rough
""".strip()


@pytest.fixture(scope="session")
def battle_format() -> str:
    return REGULATION_M_B.format_id


@pytest.fixture(scope="session")
def team_generator() -> str:
    return TEAM_GENERATOR


@pytest.fixture(scope="session")
def bridge():
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    with ShowdownBridge() as running:
        yield running


@pytest.fixture(scope="session")
def teams(bridge, battle_format, team_generator) -> tuple[str, str]:
    """Two validated Reg M-B teams, generated once and shared -- sampling is slow."""
    return (
        bridge.random_team(battle_format, team_generator),
        bridge.random_team(battle_format, team_generator),
    )


@pytest.fixture(scope="session")
def mega_team_text() -> str:
    """The export-format source of MEGA_TEAM, for tests that need the declared sets."""
    return MEGA_TEAM


@pytest.fixture(scope="session")
def mega_team(bridge, battle_format) -> BattleTeam:
    """A known-legal team holding a Mega stone, in both the forms a battle needs."""
    return BattleTeam(
        team=parse_showdown_team(MEGA_TEAM),
        packed=bridge.validate_team(battle_format, MEGA_TEAM),
        name="mega",
    )


@pytest.fixture(scope="session")
def mega_teams(mega_team) -> tuple[BattleTeam, BattleTeam]:
    """Both sides on the same team: isolates agent behaviour from team strength."""
    return mega_team, mega_team


@pytest.fixture(scope="session")
def team_pool(bridge, battle_format, team_generator) -> TeamPool:
    """A small pool of generated teams.

    Kept small and session-scoped because generation is slow -- Showdown's
    generator is not regulation-aware, so most attempts fail validation.
    """
    return TeamPool.generated(bridge, battle_format, size=4, generator=team_generator)


@pytest.fixture(scope="module")
def env(bridge) -> BattleEnv:
    return BattleEnv(REGULATION_M_B, bridge=bridge)
