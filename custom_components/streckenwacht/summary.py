"""Time-dependent views on events for the entities. Pure Python, no HA imports."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from .model import EventType, StreckenwachtEvent

# Types that turn "disruption active" on. Plain roadworks do not: many run for
# years (S21 in Stuttgart: 2014-2029) and would keep the sensor on permanently.
DISRUPTION_TYPES = frozenset(
    {EventType.CLOSURE, EventType.ACCIDENT, EventType.TRAFFIC_JAM}
)

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


def active(
    events: Iterable[StreckenwachtEvent], now: datetime
) -> list[StreckenwachtEvent]:
    """Events that apply right now, most severe first."""
    return sorted(
        (e for e in events if e.is_active(now)),
        key=lambda e: (_SEVERITY[e.event_type], e.title),
    )


def disruptions(
    events: Iterable[StreckenwachtEvent], now: datetime
) -> list[StreckenwachtEvent]:
    """Active closures, accidents and traffic jams."""
    return [e for e in active(events, now) if e.event_type in DISRUPTION_TYPES]


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
    }


def listed(events: list[StreckenwachtEvent]) -> list[dict[str, Any]]:
    """Attributes for at most MAX_LISTED_EVENTS events."""
    return [event_attributes(e) for e in events[:MAX_LISTED_EVENTS]]


@dataclass(frozen=True, slots=True)
class CalendarItem:
    """One calendar entry: an event period clipped to a time window."""

    event: StreckenwachtEvent
    start: datetime
    end: datetime
    uid: str


def calendar_items(
    events: Iterable[StreckenwachtEvent], start: datetime, end: datetime
) -> list[CalendarItem]:
    """Calendar entries overlapping [start, end), one per event period.

    Open ends ("until further notice", unknown start) are clipped to the
    window: such an event is shown across the whole visible range.
    """
    items: list[CalendarItem] = []
    for event in events:
        periods = event.periods or (None,)
        for index, period in enumerate(periods):
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
                end = period.end if period and period.end else now + _OPEN_END
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
