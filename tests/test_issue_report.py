"""The report for a bug report: plain text, nothing that locates an area."""

from __future__ import annotations

from datetime import timedelta

import aiohttp
from yarl import URL

from custom_components.streckenwacht.button import (
    area_line,
    settings_lines,
    source_line,
)
from custom_components.streckenwacht.const import (
    CONF_AREA_SOURCES,
    CONF_DIRECTIONS,
    CONF_JAM_THRESHOLD,
    CONF_RADIUS,
    CONF_ROADS,
    CONF_SCAN_INTERVAL,
    CONF_TYPES,
)
from custom_components.streckenwacht.issue_report import render
from custom_components.streckenwacht.providers import ProviderError, failure_kind

AREA = {
    "latitude": 48.7403,
    "longitude": 9.1201,
    CONF_RADIUS: 12_400.0,
    CONF_AREA_SOURCES: ["autobahn", "mobidata_bw", "stuttgart"],
    CONF_ROADS: ["A8", "A81"],
    CONF_DIRECTIONS: ["Singen -> Stuttgart"],
    CONF_JAM_THRESHOLD: 15,
    CONF_TYPES: ["closure", "accident"],
}


def test_render_sections_and_lines() -> None:
    text = render(
        "Streckenwacht 0.9.3, Home Assistant 2026.11.0",
        [
            ("entry", [("areas", "1")]),
            ("sources", []),
            ("settings", settings_lines({CONF_SCAN_INTERVAL: 20})),
        ],
    )
    assert text == (
        "Streckenwacht 0.9.3, Home Assistant 2026.11.0\n"
        "\n"
        "[entry]\n"
        "areas: 1\n"
        "\n"
        "[settings]\n"
        "scan_interval: 20 min\n"
        "include_inrix: yes\n"
        "merge_duplicates: yes"
    )


def test_area_by_its_shape_only() -> None:
    line = area_line(AREA, 7)
    assert line == (
        "radius 12 km, sources 3, roads 2, directions 1, jam threshold 15 min, "
        "types accident/closure, events 7"
    )
    for secret in ("48.7", "9.12", "A8", "Singen", "Stuttgart", "stuttgart"):
        assert secret not in line


def test_area_without_roads_and_filters() -> None:
    area = {CONF_RADIUS: 300.0, CONF_AREA_SOURCES: ["berlin"], CONF_TYPES: None}
    line = area_line(area, 0)
    assert line == "radius 0.3 km, sources 1, roads 0, types all, events 0"
    # Below 10 km as in the settings overview, not rounded to whole km.
    assert area_line(area | {CONF_RADIUS: 2500.0}, 0).startswith("radius 2.5 km,")


def test_source_lines() -> None:
    assert (
        source_line(
            success=True,
            failures=0,
            failure=None,
            since=timedelta(minutes=3, seconds=50),
            fetched=1520,
            in_areas=12,
        )
        == "ok, 3 min ago, 1520 fetched, 12 in the areas"
    )
    assert (
        source_line(
            success=False,
            failures=3,
            failure="timeout",
            since=timedelta(hours=5),
            fetched=40,
            in_areas=2,
        )
        == "failed 3x (timeout), last success 5 h ago, 40 fetched, 2 in the areas kept"
    )
    assert (
        source_line(
            success=False,
            failures=1,
            failure="HTTP 503",
            since=None,
            fetched=None,
            in_areas=None,
        )
        == "failed 1x (HTTP 503), last success never, no data"
    )


def _wrapped(cause: BaseException) -> ProviderError:
    # The message names the URL, and with it the chosen road.
    err = ProviderError("Error fetching https://verkehr.autobahn.de/o/autobahn/A8")
    err.__cause__ = cause
    return err


def test_failure_kind_leaves_out_the_message() -> None:
    url = URL("https://verkehr.autobahn.de/o/autobahn/A8/services/roadworks")
    request = aiohttp.RequestInfo(url, "GET", {}, url)  # type: ignore[arg-type]
    assert failure_kind(_wrapped(TimeoutError())) == "timeout"
    assert (
        failure_kind(_wrapped(aiohttp.ClientResponseError(request, (), status=503)))
        == "HTTP 503"
    )
    assert (
        failure_kind(_wrapped(aiohttp.ServerDisconnectedError()))
        == "connection error (ServerDisconnectedError)"
    )
    assert failure_kind(_wrapped(ValueError("bad json"))) == "unexpected data"
    assert failure_kind(ProviderError("Unexpected format for A8/roadworks")) == (
        "unexpected data"
    )
    assert failure_kind(KeyError("A8")) == "unexpected error (KeyError)"


def test_text_and_utc() -> None:
    """Settings in plain text, not Python's spelling (same in all sister projects)."""
    from datetime import UTC, date, datetime, timedelta, timezone

    from custom_components.streckenwacht.issue_report import text, utc

    assert text(True) == "yes"
    assert text(False) == "no"
    assert text(None) == "none"
    assert text([7.94, 8]) == "7.94, 8"
    assert text([]) == "none"
    assert text({"a": 1, "b": None}) == "a 1, b none"
    assert text(date(2026, 1, 1)) == "2026-01-01"
    assert text(0.5) == "0.5"
    moment = datetime(
        2026, 11, 7, 13, 39, 32, 639925, tzinfo=timezone(timedelta(hours=1))
    )
    assert text(moment) == utc(moment) == "2026-11-07 12:39 UTC"
    assert utc(datetime(2026, 11, 7, 12, 0, tzinfo=UTC)) == "2026-11-07 12:00 UTC"
    assert utc(None) == "-"
