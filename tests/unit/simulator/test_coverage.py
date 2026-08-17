"""Protocol coverage measurement.

Exists because the tracker ignores line types it cannot handle, so a gap costs
information without failing anything. Measured against real replays this sits
at 97.2%; this file checks the measuring instrument itself.
"""

from champions_ai.simulator.coverage import handler_name, measure_coverage


def test_handler_name_matches_the_trackers_dispatch():
    assert handler_name("switch") == "_on_switch"
    assert handler_name("-damage") == "_on_minor_damage"
    assert handler_name("t:") == "_on_t"


def test_major_and_minor_lines_are_separate_namespaces():
    """`|start|` begins the battle, `|-start|` begins a volatile condition.

    Stripping the dash sent both to one handler, which crashed on the first
    real battle.
    """
    assert handler_name("start") != handler_name("-start")


def test_counts_handled_lines():
    report = measure_coverage([("|switch|p2a: X|X, L50|100/100", "|-damage|p2a: X|50/100")])
    assert report.fraction_handled == 1.0
    assert report.handled["switch"] == 1
    assert report.handled["-damage"] == 1


def test_counts_unhandled_lines_and_names_them():
    report = measure_coverage([("|-notarealline|p2a: X",)])
    assert report.fraction_handled == 0.0
    assert report.missing() == [("-notarealline", 1)]


def test_cosmetic_lines_neither_flatter_nor_depress_the_figure():
    """Chat and timers say nothing about the battle, so they are not coverage."""
    report = measure_coverage(
        [("|j|☆player", "|t:|123", "|inactive|30 seconds left", "|switch|p2a: X|X, L50|100/100")]
    )
    assert report.meaningful_total == 1
    assert report.fraction_handled == 1.0
    assert sum(report.cosmetic.values()) == 3


def test_effect_announcements_count_as_cosmetic():
    """Super-effective and resisted are derivable from the type chart."""
    report = measure_coverage([("|-supereffective|p2a: X", "|-resisted|p2a: X")])
    assert report.meaningful_total == 0
    assert sum(report.cosmetic.values()) == 2


def test_mixed_logs_produce_a_fraction():
    report = measure_coverage([("|switch|p2a: X|X, L50|100/100", "|-notarealline|p2a: X")])
    assert report.fraction_handled == 0.5


def test_empty_input_is_fully_covered_rather_than_a_division_error():
    report = measure_coverage([])
    assert report.fraction_handled == 1.0
    assert report.meaningful_total == 0


def test_render_reports_the_gaps():
    rendered = measure_coverage([("|-notarealline|p2a: X",)]).render()
    assert "coverage" in rendered
    assert "-notarealline" in rendered


def test_the_handlers_added_for_replays_are_recognised():
    """The gaps a real-replay audit turned up should now register as handled."""
    report = measure_coverage(
        [
            (
                "|detailschange|p2a: X|X-Mega, L50",
                "|-start|p2a: X|Substitute",
                "|-end|p2a: X|Substitute",
                "|-singleturn|p2a: X|Protect",
                "|-activate|p2a: X|ability: Rough Skin",
            )
        ]
    )
    assert report.fraction_handled == 1.0
