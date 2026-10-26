"""Time-dependent views on events for the entities. Pure Python, no HA imports."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from .geo import haversine_km
from .model import (
    EventType,
    ObservationArea,
    StreckenwachtEvent,
    is_route_direction,
)

# Types that turn "disruption active" on. Plain roadworks do not: many run for
# years (S21 in Stuttgart: 2014-2029) and would keep the sensor on permanently.
DISRUPTION_TYPES = frozenset(
    {EventType.CLOSURE, EventType.ACCIDENT, EventType.TRAFFIC_JAM}
)

# Long-running closures are the new normal on the road (a bridge closed for
# years, a street closed for months, many of them in big cities): they turn
# "disruption active" on only during their first days. Closures whose current
# time window is short count throughout - nightly closures of a long project
# included, as every night is a window of its own.
LONG_CLOSURE = timedelta(days=30)
NEW_CLOSURE = timedelta(days=7)

# Order for attribute lists: most severe first.
_SEVERITY = {
    EventType.ACCIDENT: 0,
    EventType.CLOSURE: 1,
    EventType.TRAFFIC_JAM: 2,
    EventType.WARNING: 3,
    EventType.ROADWORKS: 4,
}

# State attributes must stay small (HA warns above 16 KB).
MAX_LISTED_EVENTS = 20

# Nominal length for open-ended periods in the calendar's current event.
_OPEN_END = timedelta(days=1)

# Live events (jams, accidents, warnings) have no end in the data. In the
# calendar they last until shortly after now instead of filling the whole
# visible range; the entry moves along with the clock while the event lasts.
LIVE_TYPES = frozenset({EventType.TRAFFIC_JAM, EventType.ACCIDENT, EventType.WARNING})
LIVE_SPAN = timedelta(minutes=30)


def active(
    events: Iterable[StreckenwachtEvent], now: datetime
) -> list[StreckenwachtEvent]:
    """Events that apply right now, most severe first."""
    return sorted(
        (e for e in events if e.is_active(now)),
        key=lambda e: (_SEVERITY[e.event_type], e.title),
    )


def disruptions(
    events: Iterable[StreckenwachtEvent], now: datetime, jam_threshold: int = 0
) -> list[StreckenwachtEvent]:
    """Active closures, accidents and traffic jams.

    Traffic jams only count from jam_threshold minutes of travel time loss on;
    with a threshold above 0, jams without a known loss do not count.
    Long-running closures only count while they are new (see LONG_CLOSURE).
    """
    return [
        e
        for e in active(events, now)
        if e.event_type in DISRUPTION_TYPES
        and (
            e.event_type is not EventType.TRAFFIC_JAM
            or jam_threshold <= 0
            or (e.delay_minutes or 0) >= jam_threshold
        )
        and (e.event_type is not EventType.CLOSURE or _closure_counts(e, now))
    ]


def _closure_counts(event: StreckenwachtEvent, now: datetime) -> bool:
    """Short or new closures; long-running ones are ignored after a few days."""
    if not event.periods:
        return True  # no times at all: the source lists it as current
    window = next((p for p in event.periods if p.contains(now)), None)
    if window is None or window.start is None:
        return False  # began at an unknown time: treated as long-running
    if now - window.start <= NEW_CLOSURE:
        return True
    return window.end is not None and window.end - window.start <= LONG_CLOSURE


# How far ahead "next closure" looks.
NEXT_CLOSURE_HORIZON = timedelta(days=14)


@dataclass(frozen=True, slots=True)
class Upcoming:
    """The next time window of a planned event."""

    event: StreckenwachtEvent
    start: datetime
    end: datetime | None


def next_closure(
    events: Iterable[StreckenwachtEvent],
    now: datetime,
    horizon: timedelta = NEXT_CLOSURE_HORIZON,
) -> Upcoming | None:
    """The closure window starting next (after now, within the horizon)."""
    best: Upcoming | None = None
    for event in events:
        if event.event_type is not EventType.CLOSURE:
            continue
        for period in event.periods:
            start = period.start
            if start is None or not now < start <= now + horizon:
                continue
            if best is None or (start, event.title) < (best.start, best.event.title):
                best = Upcoming(event, start, period.end)
    return best


def max_delay(
    events: Iterable[StreckenwachtEvent], now: datetime
) -> tuple[int, StreckenwachtEvent | None]:
    """Largest current travel time loss in minutes (0 if none) and its event.

    The maximum, not the sum: an area usually contains both directions.
    """
    best: tuple[int, StreckenwachtEvent | None] = (0, None)
    for event in active(events, now):
        if event.delay_minutes and event.delay_minutes > best[0]:
            best = (event.delay_minutes, event)
    return best


def delays_by_direction(
    events: Iterable[StreckenwachtEvent], now: datetime
) -> dict[str, int]:
    """Largest current travel time loss per route direction, largest first.

    An area usually contains both carriageways; this lets an automation pick
    the one it drives on ("Karlsruhe -> Heidelberg"). Only route directions
    count, as in the direction filter of an area: ramps and events without a
    direction cannot be assigned to a carriageway and are not listed.
    """
    delays: dict[str, int] = {}
    for event in active(events, now):
        if not is_route_direction(event.direction):
            continue
        if event.delay_minutes and event.delay_minutes > 0:
            known = delays.get(event.direction, 0)
            delays[event.direction] = max(known, event.delay_minutes)
    return dict(sorted(delays.items(), key=lambda item: (-item[1], item[0])))


def event_attributes(event: StreckenwachtEvent) -> dict[str, Any]:
    """Compact, JSON-friendly description of an event (no geometry)."""
    return {
        "id": event.id,
        "title": event.title,
        "type": event.event_type.value,
        "source": event.source.value,
        "road": event.road,
        "direction": event.direction,
        "start": event.start.isoformat() if event.start else None,
        "end": event.end.isoformat() if event.end else None,
        "delay_minutes": event.delay_minutes,
        "latitude": event.latitude,
        "longitude": event.longitude,
        "also_reported_by": [source.value for source in event.merged_sources],
    }


def listed(events: list[StreckenwachtEvent]) -> list[dict[str, Any]]:
    """Attributes for at most MAX_LISTED_EVENTS events."""
    return [event_attributes(e) for e in events[:MAX_LISTED_EVENTS]]


def map_features(
    events: Iterable[StreckenwachtEvent],
    now: datetime,
    horizon: timedelta = NEXT_CLOSURE_HORIZON,
) -> list[dict[str, Any]]:
    """GeoJSON features for the map card: active events and those starting soon.

    Planned ones first and the most severe last, so they are drawn on top.
    """
    found: list[tuple[bool, int, dict[str, Any]]] = []
    for event in events:
        is_active = event.is_active(now)
        if not is_active:
            starts = [p.start for p in event.periods if p.start and p.start > now]
            if not starts or min(starts) > now + horizon:
                continue
        geometry = event.geometry
        if not geometry and event.latitude is not None and event.longitude is not None:
            geometry = {
                "type": "Point",
                "coordinates": [event.longitude, event.latitude],
            }
        if not geometry:
            continue
        properties = event_attributes(event) | {
            "description": event.description,
            "active": is_active,
            "attribution": event.attribution,
        }
        feature = {"type": "Feature", "geometry": geometry, "properties": properties}
        found.append((is_active, -_SEVERITY[event.event_type], feature))
    found.sort(key=lambda f: (f[0], f[1], f[2]["properties"]["id"]))
    return [f[2] for f in found]


@dataclass(frozen=True, slots=True)
class CalendarItem:
    """One calendar entry: an event period clipped to a time window."""

    event: StreckenwachtEvent
    start: datetime
    end: datetime
    uid: str


def calendar_items(
    events: Iterable[StreckenwachtEvent],
    start: datetime,
    end: datetime,
    now: datetime,
) -> list[CalendarItem]:
    """Calendar entries overlapping [start, end), one per event period.

    Open ends of roadworks and closures ("until further notice") are clipped
    to the window. Live events without an end last until now + LIVE_SPAN.
    """
    items: list[CalendarItem] = []
    for event in events:
        periods = event.periods or (None,)
        live = event.event_type in LIVE_TYPES
        for index, period in enumerate(periods):
            if live and not (period and period.end):
                item_start = period.start if period and period.start else now
                item_end = max(item_start, now) + LIVE_SPAN
            else:
                item_start = period.start if period and period.start else start
                item_end = period.end if period and period.end else end
            if item_start < end and item_end > start and item_start < item_end:
                items.append(
                    CalendarItem(event, item_start, item_end, f"{event.id}#{index}")
                )
    items.sort(key=lambda item: (item.start, item.event.title))
    return items


def current_or_next(
    events: Iterable[StreckenwachtEvent], now: datetime
) -> CalendarItem | None:
    """The calendar's "current event": the most severe active one, else the next.

    For events with several windows the relevant window is used, not the first.
    Open ends get a nominal day so the calendar state stays well-defined; the
    entity recomputes this regularly.
    """
    events = list(events)
    for event in active(events, now):
        for index, period in enumerate(event.periods or (None,)):
            if period is None or period.contains(now):
                start = period.start if period and period.start else now
                open_end = LIVE_SPAN if event.event_type in LIVE_TYPES else _OPEN_END
                end = period.end if period and period.end else now + open_end
                return CalendarItem(event, start, end, f"{event.id}#{index}")
    best: CalendarItem | None = None
    for event in events:
        for index, period in enumerate(event.periods):
            if (
                period.start
                and period.start > now
                and (best is None or period.start < best.start)
            ):
                end = period.end or period.start + _OPEN_END
                best = CalendarItem(event, period.start, end, f"{event.id}#{index}")
    return best


# geo_location entities are cheap but not free (state machine, recorder):
# more than this many markers would only clutter the map anyway.
MAX_MAP_EVENTS = 150


@dataclass(frozen=True, slots=True)
class MapEvent:
    """An active event for the map, with the areas it belongs to."""

    event: StreckenwachtEvent
    distance_km: float | None
    areas: tuple[str, ...]


def map_events(
    by_area: dict[str, Iterable[StreckenwachtEvent]],
    areas: dict[str, ObservationArea],
    now: datetime,
    limit: int = MAX_MAP_EVENTS,
) -> list[MapEvent]:
    """Active events with a position, once each, most severe and nearest first.

    The distance is measured to the centre of the nearest area containing it.
    """
    found: dict[str, tuple[StreckenwachtEvent, list[str], float | None]] = {}
    for area_id, events in by_area.items():
        area = areas.get(area_id)
        if area is None:
            continue
        for event in active(events, now):
            if event.latitude is None or event.longitude is None:
                continue
            distance = haversine_km(
                area.latitude, area.longitude, event.latitude, event.longitude
            )
            known = found.get(event.id)
            if known is None:
                found[event.id] = (event, [area.name], distance)
            else:
                known[1].append(area.name)
                if known[2] is None or distance < known[2]:
                    found[event.id] = (event, known[1], distance)
    ordered = sorted(
        found.values(),
        key=lambda f: (_SEVERITY[f[0].event_type], f[2] or 0.0, f[0].id),
    )
    return [
        MapEvent(
            event, round(distance, 1) if distance is not None else None, tuple(names)
        )
        for event, names, distance in ordered[:limit]
    ]
