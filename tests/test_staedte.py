"""Tests for the city providers: München, Frankfurt, Dortmund."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from custom_components.streckenwacht.const import LOCAL_TZ, Source
from custom_components.streckenwacht.model import EventType, ObservationArea, Period
from custom_components.streckenwacht.providers import (
    dortmund,
    frankfurt,
    muenchen,
)
from custom_components.streckenwacht.providers.dortmund import DortmundProvider
from custom_components.streckenwacht.providers.muenchen import MuenchenProvider
from custom_components.streckenwacht.providers.wfs import parse_layer

from .conftest import load_fixture


def local(*args: int) -> datetime:
    return datetime(*args, tzinfo=LOCAL_TZ)


def feature(geometry: dict, fid: object = None, **props: object) -> dict:
    return {"type": "Feature", "id": fid, "geometry": geometry, "properties": props}


def polygon(x: float, y: float) -> dict:
    ring = [[x, y], [x + 0.001, y], [x + 0.001, y + 0.001], [x, y]]
    return {"type": "Polygon", "coordinates": [ring]}


# --- München ----------------------------------------------------------------

MUC = {
    "strasse_hausnr": "Dietlindenstraße 12 - 35",
    "betroffene_bereiche": "Gehweg,Radweg,Fahrbahn",
    "beschreibung": "Arbeiten am Fernwärmenetz",
    "beeintraechtigung": "Straßensperrung, Parkplätze entfallen",
    "art": "Baumaßnahme",
    "beginn_datum_kombiniert": "06.07.2026",
    "ende_datum_kombiniert": "09.11.2026 23:59",
}


def test_muenchen() -> None:
    key, event = muenchen.parse_feature(feature(polygon(11.6, 48.17), **MUC))
    assert event.source is Source.MUENCHEN
    assert event.event_type is EventType.CLOSURE
    assert event.title == "Dietlindenstraße 12 - 35: Arbeiten am Fernwärmenetz"
    assert event.description == (
        "Arbeiten am Fernwärmenetz\n"
        "Beeinträchtigung: Straßensperrung, Parkplätze entfallen\n"
        "Betroffen: Gehweg, Radweg, Fahrbahn"
    )
    assert event.periods == (Period(local(2026, 7, 6), local(2026, 11, 9, 23, 59)),)
    assert "Dietlindenstraße" in key


def test_muenchen_half_closure_and_open_start() -> None:
    props = MUC | {
        "beeintraechtigung": "halbseitige Straßensperrung",
        "beginn_datum_kombiniert": "Beginn vor mehr als einem Jahr",
    }
    _, event = muenchen.parse_feature(feature(polygon(11.6, 48.17), **props))
    assert event.event_type is EventType.ROADWORKS
    assert event.periods == (Period(None, local(2026, 11, 9, 23, 59)),)


@pytest.mark.parametrize(
    ("impact", "kept"),
    [
        ("Parkplätze entfallen", False),
        ("Haltverbot", False),
        ("Fahrbahn eingeengt, Parkplätze entfallen", True),
        ("Keine Einfahrt in den Petueltunnel möglich", True),
        (None, True),
    ],
)
def test_muenchen_parking_only_is_skipped(impact: str | None, kept: bool) -> None:
    props = MUC | {"beeintraechtigung": impact}
    assert (
        muenchen.parse_feature(feature(polygon(11.6, 48.17), **props)) is not None
    ) is kept


def test_muenchen_polygons_of_one_site_are_merged() -> None:
    merged = muenchen.merge_sites(
        [feature(polygon(11.6, 48.17), **MUC), feature(polygon(11.61, 48.17), **MUC)]
    )
    assert len(merged) == 1
    assert merged[0]["geometry"]["type"] == "GeometryCollection"


def test_muenchen_fixture() -> None:
    features = load_fixture("muenchen_innenstadt.geojson.json")["features"]
    layer = MuenchenProvider.layers[0]
    events = parse_layer(Source.MUENCHEN, layer, layer.prepare(features))
    assert events
    assert len({e.id for e in events}) == len(events)
    assert all(48.1 < e.latitude < 48.2 for e in events)


# --- Frankfurt --------------------------------------------------------------

LINE_FFM = {"type": "MultiLineString", "coordinates": [[[8.68, 50.11], [8.69, 50.11]]]}


def test_frankfurt_roadworks() -> None:
    key, event = frankfurt.parse_roadworks(
        feature(
            LINE_FFM,
            startevent="2026-02-08T23:00:00Z",
            endevent="2026-12-21T22:59:59Z",
            name="Adalbertstraße 3",
            textlong=(
                "Bockenheim, Adalbertstraße 3, aufgrund von Kran-, Hebe- und "
                "Hubsteigerarbeiten Teilsperrung der Fahrbahn in Richtung Ost."
            ),
            baustellennummer="B-2025-01717",
            sperrung=0,
            meldung="Baustelle",
        )
    )
    assert key == "B-2025-01717"
    assert event.event_type is EventType.ROADWORKS
    assert event.title == "Adalbertstraße 3: Kran-, Hebe- und Hubsteigerarbeiten"
    assert event.periods == (
        Period(
            datetime(2026, 2, 8, 23, 0, tzinfo=UTC),
            datetime(2026, 12, 21, 22, 59, tzinfo=UTC),
        ),
    )


def test_frankfurt_closure_flag_and_message() -> None:
    _, closure = frankfurt.parse_roadworks(
        feature(
            LINE_FFM, name="A661 Ausfahrt", textlong="", sperrung=1, meldung="Baustelle"
        )
    )
    assert closure.event_type is EventType.CLOSURE
    assert closure.title == "A661 Ausfahrt: Baustelle"
    _, message = frankfurt.parse_message(
        feature(
            LINE_FFM,
            name="Schaumainkai - Flohmarkt",
            textlong="Sachsenhausen, Flohmarkt, Vollsperrung des Schaumainkai",
            meldung="wegen Veranstaltung gesperrt",
            meldung2="Veranstaltung",
            startevent="2026-10-17T04:00:00Z",
            endevent="2099-12-31T11:00:00Z",
        )
    )
    assert message.event_type is EventType.CLOSURE
    assert message.title == "Schaumainkai - Flohmarkt: wegen Veranstaltung gesperrt"
    assert message.periods == (Period(datetime(2026, 10, 17, 4, 0, tzinfo=UTC), None),)


@pytest.mark.parametrize(
    ("name", "parse"),
    [
        ("baustellen", frankfurt.parse_roadworks),
        ("verkehrsmeldungen", frankfurt.parse_message),
    ],
)
def test_frankfurt_fixtures(name: str, parse) -> None:
    features = load_fixture(f"frankfurt_{name}.geojson.json")["features"]
    layer = next(
        layer for layer in frankfurt.FrankfurtProvider.layers if layer.parse is parse
    )
    events = parse_layer(Source.FRANKFURT, layer, features)
    assert len({e.id for e in events}) == len(events)


# --- Dortmund ---------------------------------------------------------------

POINT_DO = {"type": "Point", "coordinates": [7.465, 51.514]}


def do(**props: object) -> dict:
    return feature(
        POINT_DO,
        **{
            "art_der_baumassnahme": "Kaiserstraße - Masterneuerung // Vollsperrung",
            "auftraggeber": "Stadt Dortmund",
            "von": "2026-10-05",
            "bis": "2026-10-16",
            "stadtbezirk": "Innenstadt-Ost",
        }
        | props,
    )


def test_dortmund() -> None:
    _, event = dortmund.parse_feature(do())
    assert event.source is Source.DORTMUND
    assert event.event_type is EventType.CLOSURE
    assert event.title == "Kaiserstraße - Masterneuerung"
    assert event.road == "Kaiserstraße"
    assert event.description == (
        "Vollsperrung\nStadtbezirk Innenstadt-Ost\nAuftraggeber: Stadt Dortmund"
    )
    assert event.periods == (Period(local(2026, 10, 5), local(2026, 10, 17)),)


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        (
            "Weg - Glasfaser // halbseitige Sperrung bzw. Vollsperrung",
            EventType.ROADWORKS,
        ),
        ("Weg - Glasfaser // u.a. Vollsperrung", EventType.CLOSURE),
        ("B 236 Vollsperrung - Tangente FR Schwerte", EventType.CLOSURE),
        ("Leopoldstraße", EventType.ROADWORKS),
    ],
)
def test_dortmund_closure_detection(title: str, expected: EventType) -> None:
    _, event = dortmund.parse_feature(do(art_der_baumassnahme=title))
    assert event.event_type is expected


def test_dortmund_far_future_end_is_open() -> None:
    _, event = dortmund.parse_feature(do(bis="2099-12-31"))
    assert event.periods == (Period(local(2026, 10, 5), None),)


@pytest.mark.parametrize("name", ["baustellen-tagesaktuell", "baustellen-geplant"])
def test_dortmund_fixtures(name: str) -> None:
    features = load_fixture(f"dortmund_{name}.geojson.json")["features"]
    events = parse_layer(Source.DORTMUND, dortmund.LAYER, features)
    assert events
    assert len({e.id for e in events}) == len(events)


# --- Fetching ---------------------------------------------------------------


@pytest.fixture
async def session(socket_enabled: None) -> AsyncIterator[aiohttp.ClientSession]:
    async with aiohttp.ClientSession() as client_session:
        yield client_session


@pytest.fixture
async def server(socket_enabled: None) -> AsyncIterator[TestServer]:
    seen: list[str] = []

    async def dortmund_export(request: web.Request) -> web.Response:
        seen.append(request.match_info["name"])
        return web.json_response({"type": "FeatureCollection", "features": [do()]})

    app = web.Application()
    app.router.add_get("/do/{name}", dortmund_export)
    async with TestServer(app) as test_server:
        test_server.seen = seen  # type: ignore[attr-defined]
        yield test_server


async def test_fetch_dortmund_both_files(server: TestServer, session) -> None:
    base = str(server.make_url("/do")) + "/{}"
    provider = DortmundProvider(session, base)
    events = await provider.async_fetch([ObservationArea("DO", 51.51, 7.46, 5)])
    # The same site in both files counts once.
    assert len(events) == 1
    assert sorted(server.seen) == sorted(dortmund.DATASETS)
