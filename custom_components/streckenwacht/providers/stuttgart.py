"""Provider for the Stuttgart roadworks calendar (Tiefbauamt, WFS on GeoServer).

The GeoServer converts to GeoJSON in WGS84 on request (outputFormat/srsName),
so neither GML parsing nor reprojection is needed. Dates are free text
("18.05.2026", "Ende Dez. 2026"); unparseable dates keep the event.
"""

from __future__ import annotations

import asyncio
import calendar
import logging
import re
from collections.abc import Iterable, Sequence
from datetime import date, datetime, time, timedelta
from typing import Any

import aiohttp

from ..const import LOCAL_TZ, Source
from ..model import EventType, ObservationArea, Period, StreckenwachtEvent
from . import Provider, ProviderError

_LOGGER = logging.getLogger(__name__)

WFS_URL = "https://geoserver.stuttgart.de/geoserver/wfs"
# Order matters: on duplicates (status changed between layers) the first wins.
LAYERS = (
    "GEOLINE_FLEX:A66_BAUM_BAUSTELLEN_DATE_im_Bau_EPSG25832",
    "GEOLINE_FLEX:A66_BAUM_BAUSTELLEN_DATE_geplant_EPSG25832",
)

_FULL_DATE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{2}|\d{4})$")
_FUZZY_DATE = re.compile(
    r"^(?:(?P<part>Anfang|Mitte|Ende)\s+)?(?P<month>[A-Za-zÄÖÜäöü]+)\.?\s+(?P<year>\d{4})$"
)
_TIME = re.compile(r"^(\d{1,2})[:.](\d{2})(?:\s*Uhr)?$")
_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mär": 3,
    "mar": 3,
    "apr": 4,
    "mai": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "okt": 10,
    "nov": 11,
    "dez": 12,
}


class StuttgartProvider(Provider):
    """Roadworks on Stuttgart's main road network (Vorbehaltsstraßennetz)."""

    source = Source.STUTTGART

    def __init__(self, session: aiohttp.ClientSession, url: str = WFS_URL) -> None:
        super().__init__(session)
        self._url = url

    async def async_fetch(
        self, areas: Sequence[ObservationArea]
    ) -> list[StreckenwachtEvent]:
        """Fetch both layers (in progress and planned)."""
        if not areas:
            return []
        results = await asyncio.gather(*(self._fetch_layer(layer) for layer in LAYERS))
        events: dict[str, StreckenwachtEvent] = {}
        for result in results:
            for event in result:
                events.setdefault(event.id, event)
        return list(events.values())

    async def _fetch_layer(self, layer: str) -> list[StreckenwachtEvent]:
        data = await self._get_json(
            self._url,
            params={
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": layer,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
            },
        )
        features = data.get("features") if isinstance(data, dict) else None
        if not isinstance(features, list):
            raise ProviderError(f"Unexpected Stuttgart WFS format for {layer}")
        return list(parse_features(features))


def parse_features(features: Iterable[Any]) -> Iterable[StreckenwachtEvent]:
    """Parse GeoJSON features, skipping (and logging) malformed ones."""
    for feature in features:
        try:
            yield parse_feature(feature)
        except (AttributeError, KeyError, TypeError, ValueError) as err:
            _LOGGER.debug("Skipping malformed Stuttgart feature: %s", err)


def parse_feature(feature: dict[str, Any]) -> StreckenwachtEvent:
    """Map one GeoJSON feature to a StreckenwachtEvent."""
    props = feature["properties"]
    # BAUSTELLENNUMMER ("7374/2026") is stable; the GeoServer feature id may not be.
    identifier = _text(props.get("BAUSTELLENNUMMER")) or _text(feature.get("id"))
    if not identifier:
        raise ValueError("no id")
    street = _text(props.get("STRASSENNAME"))
    work = _text(props.get("ART_ARBEIT"))
    impact = _text(props.get("VERKEHRSAUSWIRKUNG_GESAMT")) or _text(
        props.get("VERKEHRSAUSWIRKUNG")
    )
    geometry = (
        feature.get("geometry") if isinstance(feature.get("geometry"), dict) else None
    )
    lat, lon = _point(geometry)

    return StreckenwachtEvent(
        id=f"{Source.STUTTGART}:{identifier}",
        source=Source.STUTTGART,
        event_type=(
            EventType.CLOSURE
            if impact and "vollsperrung" in impact.lower()
            else EventType.ROADWORKS
        ),
        title=": ".join(part for part in (street, work) if part) or "Baustelle",
        description=_description(props, impact),
        road=street,
        direction=_text(props.get("VERKEHRSAUSWIRKUNG2")),
        latitude=lat,
        longitude=lon,
        geometry=geometry,
        periods=parse_period(
            props.get("ANFANG"),
            props.get("BEGINN_UHRZEIT"),
            props.get("ENDE"),
            props.get("ENDE_UHRZEIT"),
        ),
        impact=impact,
    )


def parse_period(
    start_text: Any, start_time: Any, end_text: Any, end_time: Any
) -> tuple[Period, ...]:
    """Build the period from the free-text date and optional time fields.

    Without a time the start is the beginning and the end the end of the day.
    Fuzzy dates map Anfang/Mitte/Ende to the 1st/15th/last day of the month;
    a bare month spans the whole month.
    """
    start_day = parse_date(start_text, end_of_range=False)
    end_day = parse_date(end_text, end_of_range=True)
    start = _combine(start_day, _parse_time(start_time), end_of_day=False)
    end = _combine(end_day, _parse_time(end_time), end_of_day=True)
    if start and end and end <= start:
        end = None
    if start is None and end is None:
        return ()
    return (Period(start, end),)


def parse_date(value: Any, *, end_of_range: bool) -> date | None:
    """Parse "18.05.2026", "18.05.26", "Ende Dez. 2026", "Juni 2027" etc."""
    text = _text(value)
    if not text:
        return None
    if m := _FULL_DATE.match(text):
        day, month, year = (int(g) for g in m.groups())
        try:
            return date(year if year > 99 else 2000 + year, month, day)
        except ValueError:
            return None
    if m := _FUZZY_DATE.match(text):
        month = _MONTHS.get(m.group("month")[:3].lower())
        if month is None:
            return None
        year = int(m.group("year"))
        last = calendar.monthrange(year, month)[1]
        part = m.group("part")
        if part == "Anfang":
            return date(year, month, 1)
        if part == "Mitte":
            return date(year, month, 15)
        if part == "Ende":
            return date(year, month, last)
        return date(year, month, last if end_of_range else 1)
    return None


def _parse_time(value: Any) -> time | None:
    text = _text(value)
    if not text or not (m := _TIME.match(text)):
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
    if hour == 24 and minute == 0:
        return None  # same as end of day
    try:
        return time(hour, minute)
    except ValueError:
        return None


def _combine(
    day: date | None, clock: time | None, *, end_of_day: bool
) -> datetime | None:
    if day is None:
        return None
    if clock is not None:
        return datetime.combine(day, clock, LOCAL_TZ)
    if end_of_day:
        return datetime.combine(day + timedelta(days=1), time(), LOCAL_TZ)
    return datetime.combine(day, time(), LOCAL_TZ)


def _description(props: dict[str, Any], impact: str | None) -> str | None:
    district = _text(props.get("STADTTEIL"))
    location = _text(props.get("DETAILS_STANDORT"))
    regulation = _text(props.get("ZEITL_REGELUNG"))
    extra = _text(props.get("ZUSAETZL_INFO"))
    lines = [
        impact,
        ", ".join(part for part in (location, district) if part) or None,
        # e.g. "werktags": kept as text, not expanded into weekday windows
        # (unclear whether "werktags 22:30-05:00" means every night).
        f"Zeitliche Regelung: {regulation}"
        if regulation and regulation.lower() != "durchgehend"
        else None,
        extra if extra and extra != "." and extra not in (impact or "") else None,
    ]
    return "\n".join(line for line in lines if line) or None


def _point(geometry: dict[str, Any] | None) -> tuple[float | None, float | None]:
    if not geometry or geometry.get("type") != "Point":
        return None, None
    coords = geometry.get("coordinates")
    if (
        isinstance(coords, list)
        and len(coords) >= 2
        and all(isinstance(v, (int, float)) for v in coords[:2])
    ):
        return float(coords[1]), float(coords[0])
    return None, None


def _text(value: Any) -> str | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value = str(value)
    return value.strip() or None if isinstance(value, str) else None
