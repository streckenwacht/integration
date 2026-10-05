"""Provider for the Autobahn GmbH API (verkehr.autobahn.de).

The API has no spatial query: data is fetched per motorway and service. It also
has no end time field; start and end are parsed from the free-text description
(all known patterns: docs/ENTWICKLUNG.md, section 2).
"""

from __future__ import annotations

import asyncio
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

BASE_URL = "https://verkehr.autobahn.de/o/autobahn"
SERVICES = ("roadworks", "closure", "warning")
MAX_PARALLEL_REQUESTS = 4
# Upper bound for expanding recurring windows ("Jeden Tag zwischen ...").
MAX_RECURRING_DAYS = 400

_ACCIDENT = re.compile(r"\bUnf[aä]ll", re.IGNORECASE)

_D = r"(\d{2})\.(\d{2})\.(\d{2})"  # 05.10.26
_T = r"(\d{2}):(\d{2})"  # 08:30
_BEGIN = re.compile(rf"^Beginn: {_D} um {_T} Uhr$")
_END = re.compile(rf"^Ende: {_D} um {_T} Uhr$")
_RANGE = re.compile(rf"^{_D} {_T} bis zum {_D} {_T} Uhr\.?$")
_DAY = re.compile(rf"^{_D} von {_T} bis {_T} Uhr\.?$")
_RECURRING = re.compile(
    rf"^Jeden (?P<days>.+?) zwischen dem {_D} und dem {_D} von {_T} bis {_T} Uhr\.?$"
)
_EXCLUDED_HEADER = "Die Baustelle gilt nicht an folgenden Tagen:"
_DATE = re.compile(_D)

_WEEKDAYS = {
    "Montag": 0,
    "Dienstag": 1,
    "Mittwoch": 2,
    "Donnerstag": 3,
    "Freitag": 4,
    "Samstag": 5,
    "Sonntag": 6,
}


class AutobahnProvider(Provider):
    """Roadworks, closures and warnings (incl. traffic jams) on motorways."""

    source = Source.AUTOBAHN

    def __init__(
        self, session: aiohttp.ClientSession, base_url: str = BASE_URL
    ) -> None:
        super().__init__(session)
        self._base_url = base_url.rstrip("/")

    async def async_fetch_roads(self) -> list[str]:
        """Return all road ids the API knows, e.g. ["A1", "A2", ...]."""
        data = await self._get_json(f"{self._base_url}/")
        roads = data.get("roads") if isinstance(data, dict) else None
        if not isinstance(roads, list):
            raise ProviderError("Unexpected road list format")
        # The list contains junk such as "A60 " next to "A60": strip and dedupe.
        return sorted(
            {r.strip() for r in roads if isinstance(r, str) and r.strip()},
            key=_road_sort_key,
        )

    async def async_fetch(
        self, areas: Sequence[ObservationArea]
    ) -> list[StreckenwachtEvent]:
        """Fetch all services for every road any area watches.

        Fails as a whole if one request fails: a partial result would make
        events disappear and look like they ended.
        """
        roads = sorted(
            {road for area in areas for road in area.roads}, key=_road_sort_key
        )
        semaphore = asyncio.Semaphore(MAX_PARALLEL_REQUESTS)

        async def fetch(road: str, service: str) -> list[StreckenwachtEvent]:
            async with semaphore:
                data = await self._get_json(
                    f"{self._base_url}/{road}/services/{service}"
                )
            items = data.get(service) if isinstance(data, dict) else None
            if not isinstance(items, list):
                raise ProviderError(f"Unexpected format for {road}/{service}")
            return list(parse_items(items, road, service))

        results = await asyncio.gather(
            *(fetch(road, service) for road in roads for service in SERVICES)
        )
        events: dict[str, StreckenwachtEvent] = {}
        for result in results:
            for event in result:
                events.setdefault(event.id, event)
        return list(events.values())


def parse_items(
    items: Iterable[Any], road: str, service: str
) -> Iterable[StreckenwachtEvent]:
    """Parse API items, skipping (and logging) malformed ones."""
    for item in items:
        try:
            yield parse_item(item, road, service)
        except (AttributeError, KeyError, TypeError, ValueError) as err:
            _LOGGER.debug("Skipping malformed %s item on %s: %s", service, road, err)


def parse_item(item: dict[str, Any], road: str, service: str) -> StreckenwachtEvent:
    """Map one API item to a StreckenwachtEvent. Raises on missing essentials."""
    identifier = str(item["identifier"]).strip()
    if not identifier:
        raise ValueError("empty identifier")
    lines = [str(line) for line in item.get("description") or []]
    coordinate = item.get("coordinate") or {}
    traffic_type = item.get("abnormalTrafficType")
    upstream = item.get("source")

    return StreckenwachtEvent(
        id=f"{Source.AUTOBAHN}:{identifier}",
        source=Source.AUTOBAHN,
        event_type=_event_type(service, item, lines),
        title=str(item.get("title") or road).strip(),
        description=_join_description(lines),
        road=road,
        direction=_clean(item.get("subtitle")),
        latitude=_float(coordinate.get("lat")),
        longitude=_float(coordinate.get("long")),
        geometry=item.get("geometry")
        if isinstance(item.get("geometry"), dict)
        else None,
        periods=parse_periods(lines, item.get("startTimestamp")),
        impact=traffic_type.lower() if isinstance(traffic_type, str) else None,
        delay_minutes=_int(item.get("delayTimeValue")),
        upstream=upstream.strip().lower() if isinstance(upstream, str) else None,
    )


def _event_type(service: str, item: dict[str, Any], lines: list[str]) -> EventType:
    if service == "roadworks":
        return EventType.ROADWORKS
    if service == "closure":
        return EventType.CLOSURE
    # Warnings: accident keyword first (a jam caused by an accident is an accident).
    if _ACCIDENT.search(" ".join([str(item.get("title") or ""), *lines])):
        return EventType.ACCIDENT
    if item.get("display_type") == "CLOSURE":
        return EventType.CLOSURE
    # Any abnormal traffic type (QUEUING_, SLOW_, HEAVY_, UNSPECIFIED_ABNORMAL_
    # TRAFFIC, ...) or a travel time loss means congestion.
    if item.get("abnormalTrafficType") or (_int(item.get("delayTimeValue")) or 0) > 0:
        return EventType.TRAFFIC_JAM
    return EventType.WARNING


def parse_periods(lines: list[str], start_timestamp: Any = None) -> tuple[Period, ...]:
    """Parse validity periods from description lines.

    Explicit windows (ranges, single days, recurring days) win. Otherwise a
    "Beginn"/"Ende" phase or the startTimestamp field is used. Times in the text
    are local (Europe/Berlin). Returns () if nothing is known.
    """
    windows: list[Period] = []
    recurring: list[Period] = []
    excluded: set[date] = set()
    begin: datetime | None = None
    end: datetime | None = None
    expect_excluded = False

    for raw in lines:
        line = raw.strip()
        if expect_excluded:
            excluded.update(d for d in map(_date_from_match, _DATE.finditer(line)) if d)
            expect_excluded = False
            continue
        if line == _EXCLUDED_HEADER:
            expect_excluded = True
        elif m := _RANGE.match(line):
            start = _datetime(m.group(1, 2, 3), m.group(4, 5))
            stop = _datetime(m.group(6, 7, 8), m.group(9, 10))
            if start and stop and start < stop:
                windows.append(Period(start, stop))
        elif m := _DAY.match(line):
            day = _date(m.group(1, 2, 3))
            if day and (period := _day_window(day, m.group(4, 5), m.group(6, 7))):
                windows.append(period)
        elif m := _RECURRING.match(line):
            recurring.extend(_expand_recurring(m))
        elif m := _BEGIN.match(line):
            begin = _datetime(m.group(1, 2, 3), m.group(4, 5))
        elif m := _END.match(line):
            end = _datetime(m.group(1, 2, 3), m.group(4, 5))

    windows.extend(p for p in recurring if p.start and p.start.date() not in excluded)
    if windows:
        return tuple(sorted(set(windows), key=_sort_key))

    start = _iso(start_timestamp) or begin
    if start is None and end is None:
        return ()
    if start is not None and end is not None and end <= start:
        end = None
    return (Period(start, end),)


def _sort_key(period: Period) -> datetime:
    return period.start or datetime.min.replace(tzinfo=LOCAL_TZ)


def _expand_recurring(match: re.Match[str]) -> Iterable[Period]:
    days_text = match.group("days")
    if days_text.strip() == "Tag":
        weekdays = set(range(7))
    else:
        weekdays = {num for name, num in _WEEKDAYS.items() if name in days_text}
    first = _date(match.group(2, 3, 4))
    last = _date(match.group(5, 6, 7))
    if not (first and last and weekdays) or last < first:
        return
    day = first
    for _ in range(MAX_RECURRING_DAYS):
        if day > last:
            return
        if day.weekday() in weekdays and (
            period := _day_window(day, match.group(8, 9), match.group(10, 11))
        ):
            yield period
        day += timedelta(days=1)


def _day_window(
    day: date, start: tuple[str, str], stop: tuple[str, str]
) -> Period | None:
    """A window on one day; an end at or before the start means the next day."""
    start_time = _time(start)
    stop_time = _time(stop)
    if start_time is None or stop_time is None:
        return None
    begin = datetime.combine(day, start_time, LOCAL_TZ)
    end = datetime.combine(day, stop_time, LOCAL_TZ)
    if end <= begin:
        end += timedelta(days=1)
    return Period(begin, end)


def _date(parts: tuple[str, str, str]) -> date | None:
    day, month, year = parts
    try:
        return date(2000 + int(year), int(month), int(day))
    except ValueError:
        return None


def _date_from_match(match: re.Match[str]) -> date | None:
    return _date(match.group(1, 2, 3))


def _time(parts: tuple[str, str]) -> time | None:
    hour, minute = int(parts[0]), int(parts[1])
    if hour == 24 and minute == 0:
        hour = 0
    try:
        return time(hour, minute)
    except ValueError:
        return None


def _datetime(day: tuple[str, str, str], clock: tuple[str, str]) -> datetime | None:
    parsed_day = _date(day)
    parsed_time = _time(clock)
    if parsed_day is None or parsed_time is None:
        return None
    return datetime.combine(parsed_day, parsed_time, LOCAL_TZ)


def _iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=LOCAL_TZ)


def _join_description(lines: list[str]) -> str | None:
    """Join description lines, collapsing runs of blank lines."""
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(line.rstrip() for line in lines))
    return text.strip() or None


def _clean(value: Any) -> str | None:
    return value.strip() or None if isinstance(value, str) else None


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except TypeError, ValueError:
        return None


def _int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except TypeError, ValueError:
        return None


def _road_sort_key(road: str) -> tuple[str, int, str]:
    """Natural sort: A2 before A10."""
    m = re.match(r"([A-Za-z]*)(\d*)(.*)", road)
    prefix, number, rest = m.groups() if m else (road, "", "")
    return (prefix, int(number) if number else 0, rest)
