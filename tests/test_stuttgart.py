"""Tests for the Stuttgart provider."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date, datetime

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from custom_components.streckenwacht.const import LOCAL_TZ, Source
from custom_components.streckenwacht.model import EventType, ObservationArea, Period
from custom_components.streckenwacht.providers import ProviderError
from custom_components.streckenwacht.providers.stuttgart import (
    LAYERS,
    StuttgartProvider,
    parse_date,
    parse_feature,
    parse_features,
    parse_period,
)

from .conftest import load_fixture

FEATURE = {
    "type": "Feature",
    "id": "A66_BAUM_BAUSTELLEN_DATE_im_Bau_EPSG25832.65523",
    "geometry": {"type": "Point", "coordinates": [9.1567, 48.8456]},
    "properties": {
        "VERKEHRSAUSWIRKUNG": "Vollsperrung in mehreren Bauabschnitten.",
        "DETAILS_STANDORT": "zwischen Marco-Polo-Weg und Johanneskirche",
        "VERKEHRSAUSWIRKUNG2": None,
        "STADTTEIL": "Stammheim",
        "ANFANG": "18.05.2026",
        "ENDE_UHRZEIT": None,
        "STRASSENNAME": "Korntaler Straße",
        "BAUSTELLENNUMMER": "7374/2026",
        "ZUSAETZL_INFO": None,
        "ENDE": "Ende Dez. 2026",
        "ZEITL_REGELUNG": "durchgehend",
        "ART_ARBEIT": "Kanalbauarbeiten",
        "BEGINN_UHRZEIT": None,
        "STATUS": "im Bau",
        "VERKEHRSAUSWIRKUNG_GESAMT": (
            "Vollsperrung in mehreren Bauabschnitten. Eine Umleitung ist ausgeschildert"
        ),
    },
}


def with_props(**changes: object) -> dict:
    return FEATURE | {"properties": FEATURE["properties"] | changes}


def local(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=LOCAL_TZ)


def test_parse_feature() -> None:
    event = parse_feature(FEATURE)
    assert event.id == "stuttgart:7374/2026"
    assert event.source is Source.STUTTGART
    assert event.event_type is EventType.CLOSURE
    assert event.title == "Korntaler Straße: Kanalbauarbeiten"
    assert event.road == "Korntaler Straße"
    assert (event.latitude, event.longitude) == (48.8456, 9.1567)
    assert event.periods == (Period(local(2026, 5, 18), local(2027, 1, 1)),)
    assert event.description == (
        "Vollsperrung in mehreren Bauabschnitten. Eine Umleitung ist ausgeschildert\n"
        "zwischen Marco-Polo-Weg und Johanneskirche, Stammheim"
    )
    assert "CC BY 4.0" in event.attribution


@pytest.mark.parametrize(
    ("impact", "expected"),
    [
        ("Vollsperrung", EventType.CLOSURE),
        ("Halbseitige Sperrung / Vollsperrung je nach Bauphase.", EventType.CLOSURE),
        ("Ampelgeregelte Engstelle.", EventType.ROADWORKS),
        ("Fahrbahnreduzierung in beide Richtungen.", EventType.ROADWORKS),
        (None, EventType.ROADWORKS),
    ],
)
def test_event_type(impact: str | None, expected: EventType) -> None:
    feature = with_props(VERKEHRSAUSWIRKUNG_GESAMT=impact, VERKEHRSAUSWIRKUNG=impact)
    assert parse_feature(feature).event_type is expected


def test_feature_id_as_fallback() -> None:
    event = parse_feature(with_props(BAUSTELLENNUMMER=None))
    assert event.id == "stuttgart:A66_BAUM_BAUSTELLEN_DATE_im_Bau_EPSG25832.65523"


def test_working_days_noted_in_description() -> None:
    event = parse_feature(with_props(ZEITL_REGELUNG="werktags"))
    assert event.description is not None
    assert "Zeitliche Regelung: werktags" in event.description


@pytest.mark.parametrize(
    ("text", "end_of_range", "expected"),
    [
        ("18.05.2026", False, date(2026, 5, 18)),
        ("8.5.2026", False, date(2026, 5, 8)),
        ("18.05.26", False, date(2026, 5, 18)),
        ("Ende Dez. 2026", True, date(2026, 12, 31)),
        ("Mitte Okt. 2026", True, date(2026, 10, 15)),
        ("Anfang April 2027", True, date(2027, 4, 1)),
        ("Ende Feb. 2028", True, date(2028, 2, 29)),  # leap year
        ("Ende März 2027", True, date(2027, 3, 31)),
        ("Mitte Sept. 2027", True, date(2027, 9, 15)),
        ("Juni 2027", True, date(2027, 6, 30)),  # bare month: whole month
        ("Juni 2027", False, date(2027, 6, 1)),
        ("31.02.2026", True, None),
        ("Frühjahr 2027", True, None),
        ("bis auf Weiteres", True, None),
        ("", True, None),
        (None, True, None),
    ],
)
def test_parse_date(
    text: str | None, end_of_range: bool, expected: date | None
) -> None:
    assert parse_date(text, end_of_range=end_of_range) == expected


def test_period_with_times() -> None:
    assert parse_period("05.10.2026", "22:30", "07.10.2026", "05:00") == (
        Period(local(2026, 10, 5, 22, 30), local(2026, 10, 7, 5)),
    )


def test_period_same_day_with_times() -> None:
    assert parse_period("13.10.2026", "08:00", "13.10.2026", "15:00") == (
        Period(local(2026, 10, 13, 8), local(2026, 10, 13, 15)),
    )


def test_period_whole_days() -> None:
    assert parse_period("05.10.2026", None, "05.10.2026", None) == (
        Period(local(2026, 10, 5), local(2026, 10, 6)),
    )


def test_unparseable_end_keeps_event() -> None:
    event = parse_feature(with_props(ENDE="bis auf Weiteres"))
    assert event.periods == (Period(local(2026, 5, 18), None),)


def test_no_dates_at_all() -> None:
    assert parse_feature(with_props(ANFANG=None, ENDE=None)).periods == ()


def test_malformed_features_are_skipped() -> None:
    features = [
        FEATURE,
        {"type": "Feature"},
        "not a dict",
        {"properties": {"BAUSTELLENNUMMER": None}},
    ]
    assert len(list(parse_features(features))) == 1


@pytest.mark.parametrize("name", ["im_bau", "geplant"])
def test_fixture_invariants(name: str) -> None:
    features = load_fixture(f"stuttgart_{name}.geojson.json")["features"]
    events = list(parse_features(features))
    assert len(events) == len(features), "every real feature must parse"
    assert len({e.id for e in events}) == len(events)
    for event in events:
        assert event.latitude is not None and event.longitude is not None
        # Stuttgart plus a margin ("außerhalb der Gemarkungsgrenze" exists)
        assert 48.6 < event.latitude < 48.95 and 9.0 < event.longitude < 9.35
        assert event.start is not None and event.end is not None, event.title


@pytest.fixture
async def session() -> AsyncIterator[aiohttp.ClientSession]:
    async with aiohttp.ClientSession() as client_session:
        yield client_session


@pytest.fixture
async def server() -> AsyncIterator[TestServer]:
    async def wfs(request: web.Request) -> web.Response:
        query = request.query
        assert query["outputFormat"] == "application/json"
        assert query["srsName"] == "EPSG:4326"
        if query["typeNames"] == LAYERS[0]:  # in progress
            return web.json_response({"features": [FEATURE]})
        planned = with_props(STATUS="geplant", STRASSENNAME="Andere Straße")
        return web.json_response(
            {"features": [planned, with_props(BAUSTELLENNUMMER="1")]}
        )

    async def broken(request: web.Request) -> web.Response:
        return web.Response(text="<ServiceExceptionReport/>", content_type="text/xml")

    app = web.Application()
    app.router.add_get("/wfs", wfs)
    app.router.add_get("/broken", broken)
    async with TestServer(app) as test_server:
        yield test_server


AREA = ObservationArea("Stuttgart", 48.78, 9.18, 15)


async def test_fetch_both_layers_in_progress_wins(server: TestServer, session) -> None:
    provider = StuttgartProvider(session, str(server.make_url("/wfs")))
    events = {e.id: e for e in await provider.async_fetch([AREA])}
    assert set(events) == {"stuttgart:7374/2026", "stuttgart:1"}
    # same number in both layers: the in-progress version is kept
    assert events["stuttgart:7374/2026"].road == "Korntaler Straße"


async def test_fetch_without_areas_skips_download(session) -> None:
    provider = StuttgartProvider(session, "http://127.0.0.1:1/never")
    assert await provider.async_fetch([]) == []


async def test_wfs_error_response(server: TestServer, session) -> None:
    provider = StuttgartProvider(session, str(server.make_url("/broken")))
    with pytest.raises(ProviderError):
        await provider.async_fetch([AREA])
