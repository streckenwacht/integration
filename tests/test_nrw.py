"""Tests for the NRW city providers: Aachen, Duisburg."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from custom_components.streckenwacht.const import LOCAL_TZ, Source
from custom_components.streckenwacht.model import EventType, ObservationArea, Period
from custom_components.streckenwacht.providers.nrw import (
    AachenProvider,
    DuisburgProvider,
    parse_aachen,
    parse_duisburg,
)
from custom_components.streckenwacht.providers.wfs import parse_layer

from .conftest import load_fixture

POINT = {"type": "Point", "coordinates": [6.084, 50.776]}


def local(*args: int) -> datetime:
    return datetime(*args, tzinfo=LOCAL_TZ)


def feature(**props: object) -> dict:
    return {"type": "Feature", "geometry": POINT, "properties": props}


# --- Aachen -----------------------------------------------------------------

AC = {
    "sdatenid": "110555",
    "name": "Leitungsverlegungsarbeiten",
    "bereich": "Hausnummer 5",
    "strassen": "Jülicher Straße",
    "art": "Strassenbau",
    "symbol": "Vollsperrung - aktuell",
    "einschraen": "Sperrung der Fahrbahn.\r\nEinrichtung eines Notgehweges.",
    "von": "2026-10-05Z",
    "bis": "2026-10-16Z",
}


def test_aachen() -> None:
    key, event = parse_aachen(feature(**AC))
    assert key == "110555"
    assert event.source is Source.AACHEN
    assert event.event_type is EventType.CLOSURE
    assert event.title == "Jülicher Straße: Leitungsverlegungsarbeiten"
    assert event.description == (
        "Vollsperrung\nHausnummer 5\nSperrung der Fahrbahn. Einrichtung eines Notgehweges."
    )
    assert event.periods == (Period(local(2026, 10, 5), local(2026, 10, 17)),)


@pytest.mark.parametrize(
    ("changes", "kept"),
    [
        ({"symbol": "Verkehrsbehinderung - abgelaufen"}, False),
        ({"einschraen": "Einengung des Gehweges."}, False),
        ({"einschraen": "Die Arbeiten finden auf dem Gehweg statt."}, False),
        ({"einschraen": "Einengung der Fahrbahn."}, True),
        ({"symbol": "Verkehrsbehinderung - zukünftig"}, True),
    ],
)
def test_aachen_skips_expired_and_footpath_only(changes: dict, kept: bool) -> None:
    assert (parse_aachen(feature(**(AC | changes))) is not None) is kept


def test_aachen_traffic_hindrance_is_roadworks() -> None:
    _, event = parse_aachen(
        feature(**(AC | {"symbol": "starke Verkehrsbehinderung - aktuell"}))
    )
    assert event.event_type is EventType.ROADWORKS


# --- Duisburg ---------------------------------------------------------------

DU = {
    "OBJECTID": 51645,
    "BEZEICHNUNG_BM_MP": "Ruhrdeich (-)",
    "BEZEICHNUNG_AB_MP": "zwischen Dörnerhofstraße und Werthacker Straße",
    "SYMBOL_ID": 2,
    "BAUZEIT_AB": "18.09.26 - 23.11.26",
    "UMLEITUNG": "Eine Umleitung wird über die Carl-Benz-Straße eingerichtet.",
    "TIPP": None,
}


def test_duisburg() -> None:
    key, event = parse_duisburg(feature(**DU))
    assert key == "51645"
    assert event.source is Source.DUISBURG
    # The meaning of SYMBOL_ID is undocumented: no closure without a hint in the text.
    assert event.event_type is EventType.ROADWORKS
    assert (
        event.title == "Ruhrdeich (-): zwischen Dörnerhofstraße und Werthacker Straße"
    )
    assert event.description.endswith(
        "Umleitung: Eine Umleitung wird über die Carl-Benz-Straße eingerichtet."
    )
    # Two-digit years
    assert event.periods == (Period(local(2026, 9, 18), local(2026, 11, 24)),)


def test_duisburg_closure_from_text() -> None:
    _, event = parse_duisburg(
        feature(**(DU | {"TIPP": "Die Straße ist voll gesperrt."}))
    )
    assert event.event_type is EventType.CLOSURE


# --- Fixtures ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "provider"),
    [
        ("aachen_innenstadt", AachenProvider),
        ("duisburg_baustellen", DuisburgProvider),
    ],
)
def test_fixture_invariants(name: str, provider) -> None:
    features = load_fixture(f"{name}.geojson.json")["features"]
    layer = provider.layers[0] if hasattr(provider, "layers") else provider.layer
    events = parse_layer(provider.source, layer, features)
    assert events
    assert len({e.id for e in events}) == len(events)
    assert all(e.title and 50.6 < e.latitude < 52.1 for e in events)


# --- Fetching ---------------------------------------------------------------


@pytest.fixture
async def session(socket_enabled: None) -> AsyncIterator[aiohttp.ClientSession]:
    async with aiohttp.ClientSession() as client_session:
        yield client_session


@pytest.fixture
async def server(socket_enabled: None) -> AsyncIterator[TestServer]:
    queries: list[dict[str, str]] = []

    async def geojson(request: web.Request) -> web.Response:
        queries.append(dict(request.query))
        return web.json_response(
            {"type": "FeatureCollection", "features": [feature(**DU)]}
        )

    app = web.Application()
    app.router.add_get("/du", geojson)
    async with TestServer(app) as test_server:
        test_server.queries = queries  # type: ignore[attr-defined]
        yield test_server


async def test_fetch_duisburg_only_for_areas_nearby(
    server: TestServer, session
) -> None:
    provider = DuisburgProvider(session, (str(server.make_url("/du")),))
    elsewhere = ObservationArea("Stuttgart", 48.78, 9.18, 10)
    assert await provider.async_fetch([elsewhere]) == []
    assert server.queries == []

    events = await provider.async_fetch([ObservationArea("DU", 51.43, 6.76, 5)])
    assert len(events) == 1
    (query,) = server.queries
    assert query["f"] == "geojson" and query["outSR"] == "4326"
