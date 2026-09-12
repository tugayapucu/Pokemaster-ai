"""Team Preview scores our own Mega Stone holders as the Megas they become.

It scored the base forme, so a Mega's whole reason to be brought was invisible
to the pick. And only one Pokemon Mega Evolves per battle -- 23.8% of pool
teams hold two or more stones -- so a selection with several holders is scored
with exactly one of them evolved: the one players evolve most often when that
is measured, and otherwise whichever the agent finds best.

Synthetic species throughout. A Mega forme is given much stronger stats than
its base so that a row which uses it is unmistakable.
"""

from champions_ai.agents import HeuristicAgent
from champions_ai.dex import BaseStats, Dex, ItemInfo, MoveInfo, SpeciesInfo, TypeChart
from champions_ai.domain import REGULATION_M_C, PokemonSet, RevealedPokemon, Team, TeamPreview

WEAK = BaseStats(hp=70, attack=70, defense=70, special_attack=70, special_defense=70, speed=70)
STRONG = BaseStats(
    hp=70, attack=150, defense=120, special_attack=150, special_defense=120, speed=120
)


def _species(species_id, name, stats=WEAK, base=None):
    return SpeciesInfo(
        species_id=species_id, name=name, types=("Normal",), base_stats=stats,
        abilities=("Run Away",), base_species=base or name,
    )


OURS = ["drake", "wyrm", "fill1", "fill2", "fill3", "fill4"]
THEIRS = ["foe1", "foe2", "foe3", "foe4", "foe5", "foe6"]

DEX = Dex(
    species={
        s.species_id: s
        for s in [
            _species("drake", "Drake"),
            _species("drakemega", "Drake-Mega", STRONG, base="Drake"),
            _species("wyrm", "Wyrm"),
            _species("wyrmmega", "Wyrm-Mega", STRONG, base="Wyrm"),
            *(_species(n, n.capitalize()) for n in OURS[2:] + THEIRS),
        ]
    },
    moves={
        "bash": MoveInfo(
            move_id="bash", name="Bash", type="Normal", category="Physical",
            base_power=80, accuracy=100, priority=0, target="normal",
        ),
    },
    types=("Normal",),
    type_chart=TypeChart(multipliers={"Normal": {"Normal": 1.0}}),
    items={
        "drakite": ItemInfo(item_id="drakite", name="Drakite",
                            mega_stone="Drake", mega_forme="Drake-Mega"),
        "wyrmite": ItemInfo(item_id="wyrmite", name="Wyrmite",
                            mega_stone="Wyrm", mega_forme="Wyrm-Mega"),
    },
)


def _set(species, item=None):
    return PokemonSet(species=species, level=50, ability="runaway", moves=("bash",), item=item)


def _preview(items=None):
    items = items or {}
    return TeamPreview(
        regulation=REGULATION_M_C,
        own_team=Team(pokemon=tuple(_set(s, items.get(s)) for s in OURS)),
        opponent_team=tuple(RevealedPokemon(species=s, level=50) for s in THEIRS),
    )


HOLDERS = {"drake": "drakite", "wyrm": "wyrmite"}


def test_a_holder_is_scored_as_the_mega_it_becomes():
    table = HeuristicAgent(DEX).matchup_table(_preview(HOLDERS))
    plain = HeuristicAgent(DEX, own_megas=False).matchup_table(_preview(HOLDERS))
    assert sum(table[0]) > sum(plain[0])
    assert sum(table[1]) > sum(plain[1])


def test_pokemon_without_a_stone_are_untouched():
    table = HeuristicAgent(DEX).matchup_table(_preview(HOLDERS))
    plain = HeuristicAgent(DEX, own_megas=False).matchup_table(_preview(HOLDERS))
    assert table[2:] == plain[2:]


def test_off_reproduces_the_old_table_exactly():
    """Without stones the flag cannot matter, and with it off stones do not."""
    no_stones = HeuristicAgent(DEX).matchup_table(_preview())
    assert HeuristicAgent(DEX, own_megas=False).matchup_table(_preview(HOLDERS)) == no_stones


def test_a_stone_for_another_species_is_not_a_mega():
    agent = HeuristicAgent(DEX)
    assert agent._own_mega_set(_set("drake", "wyrmite")) is None
    assert agent._own_mega_set(_set("fill1", "drakite")) is None
    evolved = agent._own_mega_set(_set("drake", "drakite"))
    assert evolved is not None and evolved.species == "Drake-Mega"


def test_a_selection_with_two_holders_evolves_only_one_at_a_time():
    agent = HeuristicAgent(DEX)
    preview = _preview(HOLDERS)
    base, mega = agent._team_preview_rows(preview)
    tables = agent._mega_assignments(preview, (0, 1, 2, 3), base, mega)
    assert len(tables) == 2
    for table in tables:
        evolved = [i for i in (0, 1) if table[i] == mega[i] and table[i] != base[i]]
        assert len(evolved) == 1


def test_measured_rates_decide_which_holder_evolves():
    """Players evolve the species they evolve more often -- so with rates
    loaded, only that holder is tried."""
    agent = HeuristicAgent(
        DEX, mega_priors={"drake": ("Drake-Mega", 0.9), "wyrm": ("Wyrm-Mega", 0.2)}
    )
    preview = _preview(HOLDERS)
    base, mega = agent._team_preview_rows(preview)
    (table,) = agent._mega_assignments(preview, (0, 1, 2, 3), base, mega)
    assert table[0] == mega[0]
    assert table[1] == base[1]


def test_a_selection_without_holders_uses_the_base_table():
    agent = HeuristicAgent(DEX)
    preview = _preview(HOLDERS)
    base, mega = agent._team_preview_rows(preview)
    assert agent._mega_assignments(preview, (2, 3, 4, 5), base, mega) == [base]
