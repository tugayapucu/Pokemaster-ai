"""The pure parts of `review`: naming the actor, and reading a target.

Everything else in that command needs a corpus and a bridge. These three
helpers are where it turns protocol into something a person reads, and they are
where it got the human's action wrong twice while being written.
"""

from champions_ai.cli.review import _actor, _describe_human, _target
from champions_ai.data.choices import ObservedChoice
from champions_ai.domain import (
    REGULATION_M_B,
    BattlePokemon,
    Observation,
    ObservedSide,
    PokemonSet,
    Side,
    StatSpread,
)


class _Dex:
    """Just enough dex to name a move, and to fail the way the real one does."""

    class _Move:
        def __init__(self, name):
            self.name = name

    def get_move(self, move_id):
        known = {"fakeout": "Fake Out", "tailwind": "Tailwind"}
        if move_id not in known:
            raise KeyError(move_id)
        return self._Move(known[move_id])


def _mon(species: str) -> BattlePokemon:
    return BattlePokemon(
        pokemon_set=PokemonSet(
            species=species,
            level=50,
            ability="blaze",
            moves=("fakeout",),
            stats=StatSpread(hp=32, speed=32),
        ),
        current_hp=100,
        max_hp=100,
    )


def _observation() -> Observation:
    return Observation(
        regulation=REGULATION_M_B,
        turn=1,
        player=0,
        own_side=Side(team=(_mon("Sneasler"), _mon("Aerodactyl")), active_slots=(0, 1)),
        opponent_side=ObservedSide(revealed=(), active_slots=(None, None)),
    )


def _choice(**kwargs) -> ObservedChoice:
    base = dict(turn=1, player=0, slot=0, kind="move", actor="Try me")
    return ObservedChoice(**{**base, **kwargs})


def test_a_nicknamed_pokemon_is_named_by_species_as_well():
    """A log calls it "Try me", which tells a reader nothing about which acted."""
    assert _actor(_choice(slot=0), _observation()) == "Sneasler (Try me)"
    assert _actor(_choice(slot=1), _observation()) == "Aerodactyl (Try me)"


def test_an_unnicknamed_pokemon_is_not_repeated():
    assert _actor(_choice(slot=1, actor="Aerodactyl"), _observation()) == "Aerodactyl"


def test_an_actor_in_an_empty_slot_falls_back_to_the_nickname():
    empty = Observation(
        regulation=REGULATION_M_B,
        turn=1,
        player=0,
        own_side=Side(team=(_mon("Sneasler"),), active_slots=(None, None)),
        opponent_side=ObservedSide(revealed=(), active_slots=(None, None)),
    )
    assert _actor(_choice(slot=0), empty) == "Try me"


def test_a_target_drops_the_protocol_prefix():
    assert _target("p2b: Staraptor") == "Staraptor"
    assert _target("Staraptor") == "Staraptor"
    assert _target(None) == ""


def test_a_move_aimed_at_its_own_user_does_not_name_a_target():
    """`Tailwind -> After Me` is the log being literal, not information."""
    choice = _choice(actor="After Me", move="tailwind", target="p1a: After Me")
    assert _describe_human(choice, _Dex()) == "Tailwind"


def test_a_move_names_its_target_when_it_has_a_real_one():
    choice = _choice(move="fakeout", target="p2b: Staraptor")
    assert _describe_human(choice, _Dex()) == "Fake Out -> Staraptor"


def test_a_move_the_dex_does_not_know_still_renders():
    """A stale cache is a reason to show the raw id, not to crash the walk."""
    choice = _choice(move="someunknownmove", target="p2a: Garchomp")
    assert _describe_human(choice, _Dex()) == "someunknownmove -> Garchomp"


def test_a_switch_reads_as_a_switch():
    choice = _choice(kind="switch", switched_to="p1a: Charizard")
    assert _describe_human(choice, _Dex()) == "switch to Charizard"
