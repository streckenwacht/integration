"""Provider for MobiData BW roadworks (Baden-Württemberg, GeoJSON, WGS84).

One statewide file per poll (~2.6 MB) covers all observation areas.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any

import aiohttp

from ..const import Source
from ..model import EventType, ObservationArea, Period, StreckenwachtEvent
from . import Provider, ProviderError

_LOGGER = logging.getLogger(__name__)

URL = "https://api.mobidata-bw.de/datasets/traffic/roadworks/roadworks_geojson.json"

TYPES = {
    "CONSTRUCTION": EventType.ROADWORKS,
    "ROAD_CLOSED": EventType.CLOSURE,
}
# Direction is source data, kept in the source's language like Autobahn subtitles.
DIRECTIONS = {
    "BOTH_DIRECTIONS": "beide Richtungen",
    "ONE_DIRECTION": "eine Richtung",
}

_ROAD_NUMBER = re.compile(r"^[ABLK]\d+[a-z]?$")
_NO_DESCRIPTION = re.compile(r"^keine Beschreibung vorhanden\s*", re.IGNORECASE)
# Plausible WGS84 ranges for Germany, used to repair swapped coordinates.
_LAT_RANGE = (47.0, 56.0)
_LON_RANGE = (5.0, 16.0)


class MobiDataBWProvider(Provider):
    """Roadworks and closures on federal, state and district roads in BW."""

    source = Source.MOBIDATA_BW

    def __init__(self, session: aiohttp.ClientSession, url: str = URL) -> None:
        super().__init__(session)
        self._url = url

    async def async_fetch(
        self, areas: Sequence[ObservationArea]
    ) -> list[StreckenwachtEvent]:
        """Fetch the statewide file (only if at least one area exists)."""
        if not areas:
            return []
        data = await self._get_json(self._url)
        features = data.get("features") if isinstance(data, dict) else None
        if not isinstance(features, list):
            raise ProviderError("Unexpected MobiData BW format")
        events: dict[str, StreckenwachtEvent] = {}
        for event in parse_features(features):
            events.setdefault(event.id, event)
        return list(events.values())


def parse_features(features: Iterable[Any]) -> Iterable[StreckenwachtEvent]:
    """Parse GeoJSON features, skipping (and logging) malformed ones."""
    for feature in features:
        try:
            yield parse_feature(feature)
        except (AttributeError, KeyError, TypeError, ValueError) as err:
            _LOGGER.debug("Skipping malformed MobiData BW feature: %s", err)


def parse_feature(feature: dict[str, Any]) -> StreckenwachtEvent:
    """Map one GeoJSON feature to a StreckenwachtEvent."""
    props = feature["properties"]
    identifier = str(props["id"]).strip()
    if not identifier:
        raise ValueError("empty id")
    street = _text(props.get("street"))
    description = _NO_DESCRIPTION.sub("", _text(props.get("description")) or "") or None
    road = _road(street)
    geometry = _repair_geometry(feature.get("geometry"))
    lat, lon = _first_position(geometry)
    start = _iso(props.get("starttime"))
    end = _iso(props.get("endtime"))
    if start and end and end <= start:
        end = None

    return StreckenwachtEvent(
        id=f"{Source.MOBIDATA_BW}:{identifier}",
        source=Source.MOBIDATA_BW,
        event_type=TYPES.get(str(props.get("type")), EventType.WARNING),
        title=_title(street, road, description),
        description=street,
        road=road,
        direction=DIRECTIONS.get(str(props.get("direction"))),
        latitude=lat,
        longitude=lon,
        geometry=geometry,
        periods=(Period(start, end),) if start or end else (),
    )


def _title(street: str | None, road: str | None, description: str | None) -> str:
    """Build a readable title.

    "B38 Tunnelwartung Saukopftunnel"            -> description as is
    "Bauphase" on "L171 Hüfingen-Bonndorf ..."   -> "L171 Hüfingen-Bonndorf ...: Bauphase"
    "Bauphase" on "Gemeindestraße"               -> "Gemeindestraße: Bauphase"
    """
    if not description:
        return street or "Baustelle"
    if not street or road is None or description.startswith(road):
        return description
    return f"{street}: {description}"


def _road(street: str | None) -> str | None:
    """Road number ("K1077") from "K1077 Böblingen-Gärtringen", else the street."""
    if not street:
        return None
    first = street.split(" ", 1)[0]
    return first if _ROAD_NUMBER.match(first) else street


def _repair_geometry(geometry: Any) -> dict[str, Any] | None:
    """Swap positions given as [lat, lon] (seen on Point features)."""
    if not isinstance(geometry, dict):
        return None
    coords = geometry.get("coordinates")
    if coords is None:
        return geometry
    return {**geometry, "coordinates": _repair_coords(coords)}


def _repair_coords(coords: Any) -> Any:
    if _is_position(coords):
        first, second = coords[0], coords[1]
        if _in(first, _LAT_RANGE) and _in(second, _LON_RANGE):
            return [second, first, *coords[2:]]
        return coords
    if isinstance(coords, list):
        return [_repair_coords(c) for c in coords]
    return coords


def _first_position(
    geometry: dict[str, Any] | None,
) -> tuple[float | None, float | None]:
    """Representative point: the first position of the geometry."""
    coords = geometry.get("coordinates") if geometry else None
    while isinstance(coords, list) and coords and not _is_position(coords):
        coords = coords[0]
    if _is_position(coords):
        return float(coords[1]), float(coords[0])
    return None, None


def _is_position(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) >= 2
        and all(isinstance(v, (int, float)) for v in value[:2])
    )


def _in(value: float, bounds: tuple[float, float]) -> bool:
    return bounds[0] <= value <= bounds[1]


def _iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None


def _text(value: Any) -> str | None:
    return value.strip() or None if isinstance(value, str) else None
