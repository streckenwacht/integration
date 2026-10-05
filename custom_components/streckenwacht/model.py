"""Common data model shared by all providers. Pure Python, no Home Assistant imports."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from .const import ATTRIBUTION, UPSTREAM_ATTRIBUTION, Source
from .geo import distance_to_geometry_km, haversine_km


class EventType(StrEnum):
    """Normalized event categories."""

    ROADWORKS = "roadworks"
    CLOSURE = "closure"
    TRAFFIC_JAM = "traffic_jam"
    ACCIDENT = "accident"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class Period:
    """A time window in which an event applies.

    None means open-ended: no start = already running, no end = until further notice.
    The end is exclusive. Datetimes must be timezone-aware.
    """

    start: datetime | None = None
    end: datetime | None = None

    def contains(self, moment: datetime) -> bool:
        """Return True if the moment lies within this period."""
        if self.start is not None and moment < self.start:
            return False
        return self.end is None or moment < self.end


@dataclass(frozen=True, slots=True)
class StreckenwachtEvent:
    """A roadworks site, closure, traffic jam, accident or other warning."""

    id: str  # globally unique: "<source>:<provider id>"
    source: Source
    event_type: EventType
    title: str
    description: str | None = None
    # Road name or number. For Autobahn events always the API road id ("A8"),
    # which the observation area filter relies on.
    road: str | None = None
    direction: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    # GeoJSON geometry. Can be large: never expose it as a state attribute.
    geometry: dict[str, Any] | None = field(default=None, repr=False, compare=False)
    # Empty if the source gives no (parseable) times; the event then counts as active
    # because the source lists it as current.
    periods: tuple[Period, ...] = ()
    impact: str | None = None
    delay_minutes: int | None = None
    # Original data supplier if it differs from the source, e.g. "inrix" for
    # traffic jams in the Autobahn API; can be switched off (docs/ENTWICKLUNG.md 4).
    upstream: str | None = None

    @property
    def attribution(self) -> str:
        """Attribution text required by the source license."""
        upstream = UPSTREAM_ATTRIBUTION.get(self.upstream or "")
        if upstream:
            return f"{ATTRIBUTION[self.source]}; {upstream}"
        return ATTRIBUTION[self.source]

    @property
    def start(self) -> datetime | None:
        """Earliest known start, or None if no start is known."""
        starts = [p.start for p in self.periods if p.start is not None]
        return min(starts, default=None)

    @property
    def end(self) -> datetime | None:
        """Latest end, or None if unknown or open-ended."""
        ends = [p.end for p in self.periods]
        if not ends or None in ends:
            return None
        return max(e for e in ends if e is not None)

    def is_active(self, now: datetime) -> bool:
        """Return True if the event applies at the given moment."""
        if not self.periods:
            return True
        return any(p.contains(now) for p in self.periods)


_ROUTE_DIRECTION = re.compile(r"^[^>]+ -> [^>]+$")


def is_route_direction(direction: str | None) -> bool:
    """True for "Start -> Destination" directions of the Autobahn API.

    Ramps ("AS Böblingen-Hulb (aus Richtung Ehningen)") and empty directions
    cannot be assigned to a carriageway and are never filtered out.
    """
    return bool(direction and _ROUTE_DIRECTION.match(direction))


@dataclass(frozen=True, slots=True)
class ObservationArea:
    """A user-defined area to watch: a circle plus the motorways to query."""

    name: str
    latitude: float
    longitude: float
    radius_km: float
    # Autobahn road ids to query ("A8", "A81"). The Autobahn API has no spatial
    # query, so motorway events are only considered for the roads listed here.
    roads: frozenset[str] = frozenset()
    # Sources shown in this area; None means all configured sources.
    sources: frozenset[Source] | None = None
    # Autobahn directions to keep ("Singen -> Stuttgart"); empty means all.
    directions: frozenset[str] = frozenset()

    def uses(self, source: Source) -> bool:
        """Return True if events of this source are shown in the area."""
        return self.sources is None or source in self.sources

    def contains(self, event: StreckenwachtEvent) -> bool:
        """Return True if the event lies within this area."""
        if not self.uses(event.source):
            return False
        if event.source is Source.AUTOBAHN:
            if event.road not in self.roads:
                return False
            if (
                self.directions
                and is_route_direction(event.direction)
                and event.direction not in self.directions
            ):
                return False
        distance = distance_to_geometry_km(
            self.latitude, self.longitude, event.geometry
        )
        if distance is None:
            if event.latitude is None or event.longitude is None:
                return False
            distance = haversine_km(
                self.latitude, self.longitude, event.latitude, event.longitude
            )
        return distance <= self.radius_km
