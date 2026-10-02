"""Tests for the Autobahn provider.

Pattern tests use inline lines copied from real responses. Fixture tests only
check invariants, so they keep passing after tools/fetch_fixtures.py refreshes
the files.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from custom_components.streckenwacht.const import Source
from custom_components.streckenwacht.model import EventType, ObservationArea, Period
from custom_components.streckenwacht.providers import ProviderError
from custom_components.streckenwacht.providers.autobahn import (
    SERVICES,
    TZ,
    AutobahnProvider,
    parse_item,
    parse_items,
    parse_periods,
)

from .conftest import load_fixture


def local(day: int, month: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=TZ)


# --- Periods -----------------------------------------------------------------


def test_phase_with_begin_and_end() -> None:
    lines = [
        "Zeitraum dieser Bauphase:",
        "Beginn: 31.07.26 um 08:30 Uhr",
        "Ende: 01.05.27 um 00:00 Uhr",
        "(Ende der Gesamtmaßnahme: 01.05.27)",
    ]
    assert parse_periods(lines) == (
        Period(local(31, 7, 8, 30), datetime(2027, 5, 1, tzinfo=TZ)),
    )


def test_start_timestamp_wins_over_begin_line() -> None:
    # Warnings: "Beginn" is local time, startTimestamp is exact (here UTC).
    lines = ["Beginn: 02.10.26 um 12:01 Uhr"]
    (period,) = parse_periods(lines, "2026-10-02T10:01:00Z")
    assert period.start == local(2, 10, 12, 1)
    assert period.end is None


def test_ranges() -> None:
    lines = [
        "Die Baustelle ist zu folgenden Zeiträumen gültig:",
        "02.10.26 22:00 bis zum 03.10.26 10:00 Uhr.",
        "03.10.26 22:00 bis zum 04.10.26 12:00 Uhr.",
        "(Ende der Gesamtmaßnahme: 09.11.26)",
    ]
    assert parse_periods(lines) == (
        Period(local(2, 10, 22), local(3, 10, 10)),
        Period(local(3, 10, 22), local(4, 10, 12)),
    )


def test_single_day_windows() -> None:
    lines = ["05.10.26 von 10:00 bis 16:30 Uhr", "06.10.26 von 08:00 bis 16:30 Uhr"]
    assert parse_periods(lines) == (
        Period(local(5, 10, 10), local(5, 10, 16, 30)),
        Period(local(6, 10, 8), local(6, 10, 16, 30)),
    )


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        # until midnight = start of the next day
        ("05.10.26 von 20:00 bis 00:00 Uhr", Period(local(5, 10, 20), local(6, 10))),
        # overnight
        (
            "05.10.26 von 22:30 bis 05:00 Uhr",
            Period(local(5, 10, 22, 30), local(6, 10, 5)),
        ),
    ],
)
def test_day_window_crossing_midnight(line: str, expected: Period) -> None:
    assert parse_periods([line]) == (expected,)


def test_recurring_every_day_with_exclusions() -> None:
    lines = [
        "Die Baustelle ist zu folgenden Zeiträumen gültig:",
        "Jeden Tag zwischen dem 04.10.26 und dem 08.10.26 von 20:00 bis 00:00 Uhr.",
        "07.10.26 von 00:00 bis 05:00 Uhr",
        "Die Baustelle gilt nicht an folgenden Tagen:",
        "06.10.26, 06.10.26, 07.10.26",
    ]
    periods = parse_periods(lines)
    starts = [p.start for p in periods]
    assert starts == [
        local(4, 10, 20),
        local(5, 10, 20),
        local(7, 10, 0),  # explicit window survives the exclusion
        local(8, 10, 20),
    ]


def test_recurring_weekdays() -> None:
    # 05.10.2026 is a Monday.
    lines = [
        "Jeden Montag und Mittwoch zwischen dem 05.10.26 und dem 18.10.26 "
        "von 09:00 bis 15:00 Uhr."
    ]
    starts = [p.start for p in parse_periods(lines)]
    assert starts == [
        local(5, 10, 9),
        local(7, 10, 9),
        local(12, 10, 9),
        local(14, 10, 9),
    ]


def test_daylight_saving_change() -> None:
    # Clocks go back on 25.10.2026: the night window is 8 hours long, not 7.
    (period,) = parse_periods(["24.10.26 von 22:00 bis 05:00 Uhr"])
    # Python ignores the offset when subtracting datetimes sharing a tzinfo: use UTC.
    duration = period.end.astimezone(UTC) - period.start.astimezone(UTC)
    assert duration == timedelta(hours=8)


@pytest.mark.parametrize(
    "lines",
    [
        [],
        ["A8: Stuttgart -> Karlsruhe"],
        ["31.02.26 von 10:00 bis 12:00 Uhr"],  # invalid date
    ],
)
def test_no_times(lines: list[str]) -> None:
    assert parse_periods(lines) == ()


def test_end_before_start_is_dropped() -> None:
    lines = ["Beginn: 05.10.26 um 10:00 Uhr", "Ende: 04.10.26 um 10:00 Uhr"]
    assert parse_periods(lines) == (Period(local(5, 10, 10), None),)


# --- Items -------------------------------------------------------------------

WARNING_ITEM = {
    "identifier": "INRIX--vi-avl.2026-10-02_10-01-00-000_015.de0",
    "display_type": "WARNING",
    "subtitle": " Stuttgart -> Karlsruhe",
    "title": "A8 | Heimsheim - Pforzheim-Nord",
    "startTimestamp": "2026-10-02T10:01:00Z",
    "delayTimeValue": "38",
    "abnormalTrafficType": "QUEUING_TRAFFIC",
    "coordinate": {"lat": 48.84092688646756, "long": 8.825682844901102},
    "description": [
        "Beginn: 02.10.26 um 12:01 Uhr",
        "",
        "",
        "",
        "Ereignismeldung:",
        "- Im Stillstand",
        "- Reisezeitverlust: 38 Minuten",
    ],
    "source": "inrix",
    "geometry": {"type": "LineString", "coordinates": [[8.8257, 48.8409]]},
}


def test_parse_warning_item() -> None:
    event = parse_item(WARNING_ITEM, "A8", "warning")
    assert event.id == "autobahn:INRIX--vi-avl.2026-10-02_10-01-00-000_015.de0"
    assert event.source is Source.AUTOBAHN
    assert event.event_type is EventType.TRAFFIC_JAM
    assert event.road == "A8"
    assert event.direction == "Stuttgart -> Karlsruhe"
    assert (event.latitude, event.longitude) == pytest.approx(
        (48.8409, 8.8257), abs=1e-4
    )
    assert event.delay_minutes == 38
    assert event.upstream == "inrix"
    assert event.impact == "queuing_traffic"
    assert event.description is not None and "\n\n\n" not in event.description
    assert event.geometry == WARNING_ITEM["geometry"]


@pytest.mark.parametrize(
    ("service", "changes", "expected"),
    [
        (
            "warning",
            {"description": ["Unfall, Fahrbahn blockiert"]},
            EventType.ACCIDENT,
        ),
        ("warning", {"title": "A8 | Unfallstelle"}, EventType.ACCIDENT),
        (
            "warning",
            {"display_type": "CLOSURE", "abnormalTrafficType": None},
            EventType.CLOSURE,
        ),
        (
            "warning",
            {"abnormalTrafficType": "UNSPECIFIED_ABNORMAL_TRAFFIC"},
            EventType.TRAFFIC_JAM,
        ),
        # no traffic type, but a travel time loss
        ("warning", {"abnormalTrafficType": None}, EventType.TRAFFIC_JAM),
        (
            "warning",
            {"abnormalTrafficType": None, "delayTimeValue": None},
            EventType.WARNING,
        ),
        # "Beseitigung Unfallfolgen" in roadworks is still roadworks
        (
            "roadworks",
            {"description": ["Beseitigung Unfallfolgen"]},
            EventType.ROADWORKS,
        ),
        ("closure", {}, EventType.CLOSURE),
    ],
)
def test_event_type(service: str, changes: dict, expected: EventType) -> None:
    assert parse_item(WARNING_ITEM | changes, "A8", service).event_type is expected


def test_malformed_items_are_skipped() -> None:
    items = [
        WARNING_ITEM,
        {"title": "no identifier"},
        "not a dict",
        {"identifier": " "},
        {"identifier": "bad-coordinate", "coordinate": [48.0, 9.0]},
    ]
    events = list(parse_items(items, "A8", "warning"))
    assert [e.id for e in events] == [f"autobahn:{WARNING_ITEM['identifier']}"]


def test_missing_optional_fields() -> None:
    event = parse_item({"identifier": "x"}, "A8", "roadworks")
    assert event.title == "A8"
    assert event.latitude is None
    assert event.periods == ()
    assert event.delay_minutes is None


# --- Fixtures ----------------------------------------------------------------


@pytest.mark.parametrize("road", ["A8", "A81"])
@pytest.mark.parametrize("service", SERVICES)
def test_fixture_invariants(road: str, service: str) -> None:
    items = load_fixture(f"autobahn_{road}_{service}.json")[service]
    events = list(parse_items(items, road, service))
    assert len(events) == len(items), "every real item must parse"
    assert len({e.id for e in events}) == len(events)
    for event in events:
        assert event.latitude is not None and event.longitude is not None
        assert event.periods, f"no time found for {event.title}"
        for period in event.periods:
            assert period.start is not None and period.start.tzinfo is not None
            assert period.end is None or period.end > period.start
        if service != "warning":
            assert event.end is not None, f"no end found for {event.title}"


# --- Fetching ----------------------------------------------------------------


FAILING = web.AppKey("failing", set[str])


@pytest.fixture
async def api() -> AsyncIterator[tuple[TestServer, list[str]]]:
    requested: list[str] = []
    failing: set[str] = set()

    async def roads(request: web.Request) -> web.Response:
        return web.json_response(load_fixture("autobahn_roads.json"))

    async def service(request: web.Request) -> web.Response:
        road, name = request.match_info["road"], request.match_info["service"]
        requested.append(f"{road}/{name}")
        if f"{road}/{name}" in failing:
            return web.Response(status=503)
        return web.json_response(load_fixture(f"autobahn_{road}_{name}.json"))

    app = web.Application()
    app.router.add_get("/", roads)
    app.router.add_get("/{road}/services/{service}", service)
    app[FAILING] = failing
    async with TestServer(app) as server:
        yield server, requested


@pytest.fixture
async def session() -> AsyncIterator[aiohttp.ClientSession]:
    async with aiohttp.ClientSession() as client_session:
        yield client_session


def area(*roads: str) -> ObservationArea:
    return ObservationArea("Test", 48.78, 9.18, 30, frozenset(roads))


async def test_fetch_queries_union_of_roads(api, session) -> None:
    server, requested = api
    provider = AutobahnProvider(session, str(server.make_url("/")))
    events = await provider.async_fetch([area("A8"), area("A8", "A81")])
    assert sorted(requested) == sorted(
        f"{r}/{s}" for r in ("A8", "A81") for s in SERVICES
    )
    assert {e.road for e in events} == {"A8", "A81"}
    assert len({e.id for e in events}) == len(events)


async def test_fetch_without_roads_makes_no_requests(api, session) -> None:
    server, requested = api
    provider = AutobahnProvider(session, str(server.make_url("/")))
    assert await provider.async_fetch([area()]) == []
    assert requested == []


async def test_one_failing_request_fails_the_fetch(api, session) -> None:
    server, _ = api
    server.app[FAILING].add("A81/closure")
    provider = AutobahnProvider(session, str(server.make_url("/")))
    with pytest.raises(ProviderError):
        await provider.async_fetch([area("A8", "A81")])


async def test_fetch_roads_sorted_naturally(api, session) -> None:
    server, _ = api
    roads = await AutobahnProvider(
        session, str(server.make_url("/"))
    ).async_fetch_roads()
    assert roads.index("A2") < roads.index("A10") < roads.index("A100")
    assert len(roads) == len(set(roads))
    assert all(r == r.strip() for r in roads)
