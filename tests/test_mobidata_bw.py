"""Tests for the MobiData BW provider."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from custom_components.streckenwacht.const import Source
from custom_components.streckenwacht.model import EventType, ObservationArea
from custom_components.streckenwacht.providers import ProviderError
from custom_components.streckenwacht.providers.mobidata_bw import (
    MobiDataBWProvider,
    parse_feature,
    parse_features,
)

from .conftest import load_fixture

CEST = timezone(timedelta(hours=2))
CET = timezone(timedelta(hours=1))

FEATURE = {
    "type": "Feature",
    "geometry": {
        "type": "LineString",
        "coordinates": [[8.961428, 48.665755], [8.961231, 48.665646]],
    },
    "properties": {
        "id": "2454613-14973690-14973691-14973706.001",
        "type": "CONSTRUCTION",
        "subtype": "",
        "description": "K1077 Erdlager DEGES",
        "reference": "MobiData BW",
        "street": "K1077 Böblingen-Gärtringen",
        "direction": "ONE_DIRECTION",
        "starttime": "2024-07-14T00:00:00.000+02:00",
        "endtime": "2026-12-31T23:59:00.000+01:00",
    },
}


def with_props(**changes: object) -> dict:
    return FEATURE | {"properties": FEATURE["properties"] | changes}


def test_parse_feature() -> None:
    event = parse_feature(FEATURE)
    assert event.id == "mobidata_bw:2454613-14973690-14973691-14973706.001"
    assert event.source is Source.MOBIDATA_BW
    assert event.event_type is EventType.ROADWORKS
    assert event.title == "K1077 Erdlager DEGES"
    assert event.description == "K1077 Böblingen-Gärtringen"
    assert event.road == "K1077"
    assert event.direction == "eine Richtung"
    assert (event.latitude, event.longitude) == (48.665755, 8.961428)
    assert event.start == datetime(2024, 7, 14, tzinfo=CEST)
    assert event.end == datetime(2026, 12, 31, 23, 59, tzinfo=CET)
    assert "MobiData BW" in event.attribution


@pytest.mark.parametrize(
    ("changes", "title", "road"),
    [
        # generic description: prefix the street
        (
            {
                "street": "L171 Hüfingen-Bonndorf im Schwarzwald",
                "description": "Bauphase",
            },
            "L171 Hüfingen-Bonndorf im Schwarzwald: Bauphase",
            "L171",
        ),
        # municipal road: no road number
        (
            {"street": "Gemeindestraße", "description": "Leibnizstraße BA 3"},
            "Gemeindestraße: Leibnizstraße BA 3",
            "Gemeindestraße",
        ),
        # placeholder text is removed
        (
            {
                "street": "Gemeindestraße",
                "description": "keine Beschreibung vorhanden Straßenneubau IBM Straße",
            },
            "Gemeindestraße: Straßenneubau IBM Straße",
            "Gemeindestraße",
        ),
        (
            {"street": "B10 Stuttgart-Ulm", "description": ""},
            "B10 Stuttgart-Ulm",
            "B10",
        ),
        ({"street": "", "description": ""}, "Baustelle", None),
    ],
)
def test_title_and_road(changes: dict, title: str, road: str | None) -> None:
    event = parse_feature(with_props(**changes))
    assert event.title == title
    assert event.road == road


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("CONSTRUCTION", EventType.ROADWORKS),
        ("ROAD_CLOSED", EventType.CLOSURE),
        ("SOMETHING_NEW", EventType.WARNING),
    ],
)
def test_types(value: str, expected: EventType) -> None:
    assert parse_feature(with_props(type=value)).event_type is expected


def test_swapped_point_is_repaired() -> None:
    # Real case: B535 near Heidelberg, delivered as [lat, lon].
    feature = FEATURE | {
        "geometry": {"type": "Point", "coordinates": [49.40012, 8.557258]}
    }
    event = parse_feature(feature)
    assert event.geometry == {"type": "Point", "coordinates": [8.557258, 49.40012]}
    assert (event.latitude, event.longitude) == (49.40012, 8.557258)


def test_correct_line_is_untouched() -> None:
    assert parse_feature(FEATURE).geometry == FEATURE["geometry"]


@pytest.mark.parametrize(
    ("changes", "has_end"),
    [
        ({"endtime": "2020-01-01T00:00:00+01:00"}, False),  # end before start
        ({"endtime": "kaputt"}, False),
        ({"endtime": "2026-12-31T23:59:00"}, False),  # no timezone
    ],
)
def test_bad_end_times(changes: dict, has_end: bool) -> None:
    event = parse_feature(with_props(**changes))
    assert (event.end is not None) is has_end
    assert event.start is not None


def test_no_times_means_no_periods() -> None:
    assert parse_feature(with_props(starttime=None, endtime=None)).periods == ()


def test_malformed_features_are_skipped() -> None:
    features = [
        FEATURE,
        {"type": "Feature"},
        "not a dict",
        with_props(id=" "),
        {"properties": None},
    ]
    assert len(list(parse_features(features))) == 1


def test_fixture_invariants() -> None:
    features = load_fixture("mobidata_bw_roadworks.geojson.json")["features"]
    events = list(parse_features(features))
    assert len(events) == len(features), "every real feature must parse"
    assert len({e.id for e in events}) == len(events)
    for event in events:
        assert event.title
        assert event.latitude is not None and event.longitude is not None
        # all of Baden-Württemberg, generously
        assert 47 < event.latitude < 50.5 and 7 < event.longitude < 11, event.title
        assert event.periods and event.start is not None


@pytest.fixture
async def session() -> AsyncIterator[aiohttp.ClientSession]:
    async with aiohttp.ClientSession() as client_session:
        yield client_session


@pytest.fixture
async def server() -> AsyncIterator[TestServer]:
    async def data(request: web.Request) -> web.Response:
        return web.json_response(
            {"type": "FeatureCollection", "features": [FEATURE, FEATURE]}
        )

    async def broken(request: web.Request) -> web.Response:
        return web.json_response({"unexpected": True})

    app = web.Application()
    app.router.add_get("/data.json", data)
    app.router.add_get("/broken.json", broken)
    async with TestServer(app) as test_server:
        yield test_server


AREA = ObservationArea("Böblingen", 48.68, 9.01, 10)


async def test_fetch_dedupes(server: TestServer, session) -> None:
    provider = MobiDataBWProvider(session, str(server.make_url("/data.json")))
    events = await provider.async_fetch([AREA])
    assert len(events) == 1
    assert AREA.contains(events[0])


async def test_fetch_without_areas_skips_download(session) -> None:
    provider = MobiDataBWProvider(session, "http://127.0.0.1:1/never")
    assert await provider.async_fetch([]) == []


async def test_unexpected_format(server: TestServer, session) -> None:
    provider = MobiDataBWProvider(session, str(server.make_url("/broken.json")))
    with pytest.raises(ProviderError):
        await provider.async_fetch([AREA])
