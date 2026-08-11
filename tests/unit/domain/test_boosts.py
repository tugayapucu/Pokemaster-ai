import pytest
from pydantic import ValidationError

from champions_ai.domain import Boosts


def test_default_is_all_zero():
    boosts = Boosts()
    assert boosts.attack == 0
    assert boosts.evasion == 0


def test_rejects_above_six():
    with pytest.raises(ValidationError):
        Boosts(attack=7)


def test_rejects_below_minus_six():
    with pytest.raises(ValidationError):
        Boosts(speed=-7)


def test_clamped_add_stays_within_range():
    boosts = Boosts(attack=5)
    boosted = boosts.clamped_add("attack", 3)
    assert boosted.attack == 6


def test_clamped_add_does_not_go_below_minimum():
    boosts = Boosts(defense=-5)
    lowered = boosts.clamped_add("defense", -3)
    assert lowered.defense == -6


def test_clamped_add_is_immutable():
    boosts = Boosts()
    boosts.clamped_add("speed", 2)
    assert boosts.speed == 0
