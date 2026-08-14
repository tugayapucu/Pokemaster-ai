from champions_ai.domain.health import color_for_percent, parse_shared_health


def test_plain_percentage():
    health = parse_shared_health("77/100")
    assert health.percent == 77
    assert health.color == "green"
    assert not health.fainted
    assert health.status is None


def test_fainted():
    health = parse_shared_health("0 fnt")
    assert health.fainted
    assert health.percent == 0
    assert health.status is None


def test_status_is_kept():
    health = parse_shared_health("56/100 brn")
    assert health.percent == 56
    assert health.status == "brn"


def test_twenty_percent_yellow_suffix_means_above_the_red_threshold():
    health = parse_shared_health("20/100y")
    assert health.percent == 20
    assert health.color == "yellow"


def test_twenty_percent_red_suffix_means_at_or_below_it():
    assert parse_shared_health("20/100r").color == "red"


def test_fifty_percent_suffixes_disambiguate_green_from_yellow():
    assert parse_shared_health("50/100g").color == "green"
    assert parse_shared_health("50/100y").color == "yellow"


def test_colour_is_inferred_when_no_suffix_is_sent():
    assert color_for_percent(100) == "green"
    assert color_for_percent(51) == "green"
    assert color_for_percent(35) == "yellow"
    assert color_for_percent(21) == "yellow"
    assert color_for_percent(19) == "red"
    assert color_for_percent(1) == "red"


def test_own_side_exact_hp_still_parses():
    """Own-side conditions are exact rather than percentages; parsing must not choke."""
    health = parse_shared_health("114/153")
    assert health.percent == 114
    assert not health.fainted
