import pytest
from pydantic import ValidationError

from champions_ai.domain import StatSpread


def test_default_is_all_zero():
    spread = StatSpread()
    assert spread.hp == 0
    assert spread.speed == 0


def test_valid_spread_within_limits():
    spread = StatSpread(hp=24, special_attack=24, speed=18)
    assert spread.hp + spread.special_attack + spread.speed == 66


def test_rejects_over_32_in_a_single_stat():
    with pytest.raises(ValidationError):
        StatSpread(hp=33)


def test_rejects_total_over_66():
    with pytest.raises(ValidationError):
        StatSpread(hp=32, attack=32, defense=3)


def test_rejects_negative():
    with pytest.raises(ValidationError):
        StatSpread(hp=-1)
