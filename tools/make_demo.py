#!/usr/bin/env python3
"""Build the data of the demo (docs/demo/): made-up reports, real logic.

Usage (from the repo root):
    uv run tools/make_demo.py            # build from the cached road geometry
    uv run tools/make_demo.py --fetch    # first fetch missing road geometry

Every report below is invented. Only its position follows a real road: the
geometry comes once from OpenStreetMap (Overpass API, ODbL) and is cached in
tools/demo_geometry.json, so building needs no network. The reports then run
through the integration's own code (area filter, duplicate merge, map
features, sensor values, calendar), as in Home Assistant.

All times are relative to a demo Wednesday. The page offers four moments
(MOMENTS: rush hour, evening, night, Saturday evening), each with its own live
reports (jams, accidents); it moves the dates by whole weeks to the present
one. For each moment the files also hold the push notifications the three
blueprints would have sent with their default settings. coverage.json lists
the regions of the sources for "does it work where I live?".
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from custom_components.streckenwacht.const import (  # noqa: E402
    LOCAL_TZ,
    SOURCE_NAMES,
    SOURCE_REGIONS,
    VERSION,
    Source,
)
from custom_components.streckenwacht.dedup import merge_duplicates  # noqa: E402
from custom_components.streckenwacht.geo import circle_bounds  # noqa: E402
from custom_components.streckenwacht.model import (  # noqa: E402
    EventType,
    ObservationArea,
    Period,
    StreckenwachtEvent,
    sources_for_circle,
)
from custom_components.streckenwacht.summary import (  # noqa: E402
    active,
    calendar_items,
    current_or_next,
    disruptions,
    listed,
    map_features,
    max_delay,
    next_closure,
)

OUT = ROOT / "docs" / "demo" / "data"
CACHE = ROOT / "tools" / "demo_geometry.json"
# Main instance first; the mirror when it is busy.
OVERPASS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
USER_AGENT = f"Streckenwacht/{VERSION} (+https://github.com/streckenwacht/integration)"
ATTRIBUTION = "Erfundene Beispieldaten – nur zur Vorführung / made-up sample data"

NOW = datetime(2026, 11, 4, 7, 40, tzinfo=LOCAL_TZ)  # a Wednesday
MOMENTS = {
    "morning": NOW,
    "evening": NOW.replace(hour=17, minute=30),
    "night": NOW.replace(hour=22, minute=30),
    "weekend": (NOW + timedelta(days=3)).replace(hour=21, minute=0),
}

# Default settings of the blueprints (blueprints/automation/streckenwacht/).
JAM_THRESHOLD = 15
NEW_TYPES = (EventType.CLOSURE, EventType.ACCIDENT)
LEAD_TIME = timedelta(hours=12)
# Titles of the blueprints in both languages ("language" input); the demo
# shows the one of the page. "{head}" is "Streckenwacht · <area>" (only with
# several areas, otherwise "Streckenwacht"), "{when}"
# the start of the closure, formatted by the page after moving the dates.
NEW_TITLES = {
    "de": {
        EventType.CLOSURE: "Neue Sperrung",
        EventType.ACCIDENT: "Neuer Unfall",
        EventType.TRAFFIC_JAM: "Neuer Stau",
        EventType.ROADWORKS: "Neue Baustelle",
        EventType.WARNING: "Neue Warnung",
    },
    "en": {
        EventType.CLOSURE: "New closure",
        EventType.ACCIDENT: "New accident",
        EventType.TRAFFIC_JAM: "New traffic jam",
        EventType.ROADWORKS: "New roadworks",
        EventType.WARNING: "New warning",
    },
}
JAM_TITLE = {
    "de": "{head}: Stau +{delay} min",
    "en": "{head}: Traffic jam +{delay} min",
}
CLOSURE_TITLE = {
    "de": "{head}: Sperrung ab {{when}}",
    "en": "{head}: Closure from {{when}}",
}
# Integrations poll every 15 minutes: a report shows up a few minutes late.
POLL_DELAY = timedelta(minutes=4)

# key: (entity id slug, area)
AREAS = {
    "arbeitsweg": (
        "arbeitsweg",
        ObservationArea(
            name="Arbeitsweg",
            latitude=48.945,
            longitude=9.19,
            radius_km=14,
            roads=frozenset({"A81"}),
        ),
    ),
    "stuttgart": (
        "stuttgart",
        ObservationArea(
            name="Stuttgart",
            latitude=48.7758,
            longitude=9.1829,
            radius_km=10,
            roads=frozenset({"A8", "A81"}),
        ),
    ),
}

HN_S = "Heilbronn -> Stuttgart"
S_HN = "Stuttgart -> Heilbronn"


def at(day: int, clock: str) -> datetime:
    """Local time on the day relative to the demo moment."""
    hour, minute = map(int, clock.split(":"))
    return (NOW + timedelta(days=day)).replace(hour=hour, minute=minute)


@dataclass(frozen=True)
class Live:
    """A live report (no end) that began some minutes before the moment(s)."""

    minutes: int
    moments: tuple[str, ...]


def ago(minutes: int, *moments: str) -> Live:
    return Live(minutes, moments or ("morning",))


def span(
    first: int, last: int, start: str = "00:00", end: str = "23:59"
) -> tuple[Period, ...]:
    return (Period(at(first, start), at(last, end)),)


def every_day(first: int, last: int, start: str, end: str) -> tuple[Period, ...]:
    """A window each day; ends before the start mean the next morning."""
    periods = []
    for day in range(first, last + 1):
        begin = at(day, start)
        finish = at(day, end)
        if finish <= begin:
            finish = at(day + 1, end)
        periods.append(Period(begin, finish))
    return tuple(periods)


@dataclass(frozen=True)
class Spec:
    """One made-up report and where it lies: near anchor, on the road matched."""

    id: str
    source: Source
    type: EventType
    title: str
    description: str
    anchor: tuple[float, float]
    match: str  # Overpass tag filter of the road
    length_km: float  # 0: a point
    periods: tuple[Period, ...] | Live
    road: str | None = None
    direction: str | None = None
    delay: int | None = None
    # Lies where another report lies (no geometry of its own); as a point at
    # its middle if point is set.
    shape: str | None = None
    point: bool = False


A81 = '["ref"~"(^|;)A 81($|;)"]["highway"="motorway"]'
A8 = '["ref"~"(^|;)A 8($|;)"]["highway"="motorway"]'


def name(street: str) -> str:
    return f'["name"="{street}"]["highway"]'


def ref(road: str) -> str:
    return f'["ref"~"(^|;){road}($|;)"]["highway"~"^(trunk|primary|secondary)$"]'


ROADWORKS, CLOSURE, JAM, ACCIDENT, WARNING = (
    EventType.ROADWORKS,
    EventType.CLOSURE,
    EventType.TRAFFIC_JAM,
    EventType.ACCIDENT,
    EventType.WARNING,
)
AUTOBAHN, MOBIDATA, LMS, STUTTGART = (
    Source.AUTOBAHN,
    Source.MOBIDATA_BW,
    Source.LMS_BW,
    Source.STUTTGART,
)

SPECS = [
    # The commute: A81 north of Stuttgart and the roads around it.
    Spec(
        "a81-works",
        AUTOBAHN,
        ROADWORKS,
        "A81 | Ludwigsburg-Nord - Pleidelsheim",
        "Fahrbahnerneuerung. Zwei verengte Fahrstreifen je Richtung, Höchstgeschwindigkeit 80 km/h.",
        (48.935, 9.185),
        A81,
        3.0,
        span(-18, 38),
        "A81",
        S_HN,
    ),
    Spec(
        "a81-jam",
        AUTOBAHN,
        JAM,
        "A81 | Pleidelsheim - Ludwigsburg-Nord",
        "Stau vor der Baustelle, 4 km.",
        (48.947, 9.19),
        A81,
        2.5,
        ago(35),
        "A81",
        HN_S,
        18,
    ),
    Spec(
        "a81-ramp",
        AUTOBAHN,
        CLOSURE,
        "A81 | AS Pleidelsheim: Zufahrt Richtung Stuttgart gesperrt",
        "Nachts gesperrt für Markierungsarbeiten. Umleitung über U 12.",
        (48.958, 9.196),
        A81,
        0.6,
        every_day(-1, 3, "21:00", "05:00"),
        "A81",
        HN_S,
    ),
    Spec(
        "a81-accident",
        AUTOBAHN,
        ACCIDENT,
        "A81 | Ludwigsburg-Süd - Stuttgart-Zuffenhausen",
        "Unfall, linker Fahrstreifen blockiert.",
        (48.862, 9.162),
        A81,
        0,
        ago(20),
        "A81",
        HN_S,
    ),
    Spec(
        "a81-weekend",
        AUTOBAHN,
        CLOSURE,
        "A81 | Mundelsheim - Ilsfeld",
        "Vollsperrung Richtung Heilbronn am Wochenende für Brückenarbeiten. Umleitung ausgeschildert.",
        (49.02, 9.225),
        A81,
        4.0,
        (Period(at(3, "20:00"), at(5, "05:00")),),
        "A81",
        S_HN,
    ),
    Spec(
        "a81-object",
        AUTOBAHN,
        WARNING,
        "A81 | Pleidelsheim - Mundelsheim",
        "Gegenstand auf der Fahrbahn.",
        (48.98, 9.2),
        A81,
        0,
        ago(10),
        "A81",
        S_HN,
    ),
    Spec(
        "a81-median",
        AUTOBAHN,
        ROADWORKS,
        "A81 | Ilsfeld - Mundelsheim",
        "Arbeiten am Mittelstreifen, tagsüber ein Fahrstreifen gesperrt.",
        (49.04, 9.235),
        A81,
        1.5,
        every_day(0, 4, "08:00", "16:00"),
        "A81",
        HN_S,
    ),
    Spec(
        "a81-feuerbach",
        AUTOBAHN,
        ROADWORKS,
        "A81 | Stuttgart-Zuffenhausen - Stuttgart-Feuerbach",
        "Lärmschutzwand, Standstreifen gesperrt.",
        (48.832, 9.137),
        A81,
        2.0,
        span(-6, 20),
        "A81",
        HN_S,
    ),
    Spec(
        "b27-lb",
        MOBIDATA,
        ROADWORKS,
        "B27 Ludwigsburg: Kanalarbeiten",
        "Fahrstreifen verengt.",
        (48.895, 9.19),
        ref("B 27"),
        0.8,
        span(-10, 25),
        "B27",
    ),
    Spec(
        "b27-bietigheim",
        LMS,
        CLOSURE,
        "B27 Bietigheim-Bissingen: Vollsperrung",
        "Brückenarbeiten. Umleitung über die L 1110.",
        (48.965, 9.135),
        ref("B 27"),
        1.0,
        (Period(at(-3, "06:00"), at(4, "18:00")),),
        "B27",
    ),
    Spec(
        "l1100-marbach",
        MOBIDATA,
        ROADWORKS,
        "L1100 Marbach am Neckar: Fahrbahnerneuerung",
        "Halbseitige Sperrung mit Ampel.",
        (48.94, 9.255),
        ref("L 1100"),
        1.2,
        span(6, 20),
        "L1100",
    ),
    # The city.
    Spec(
        "b14-closure",
        LMS,
        CLOSURE,
        "Konrad-Adenauer-Straße: Vollsperrung stadtauswärts",
        "Nachts gesperrt, Umleitung über die Neckarstraße.",
        (48.7795, 9.1865),
        name("Konrad-Adenauer-Straße"),
        0.5,
        every_day(0, 4, "20:00", "05:00"),
        "B14",
    ),
    Spec(
        "b14-works",
        STUTTGART,
        ROADWORKS,
        "Konrad-Adenauer-Straße: Erneuerung der Fahrbahndecke",
        "Fahrstreifen verengt.",
        (48.7795, 9.1865),
        name("Konrad-Adenauer-Straße"),
        0.5,
        span(-5, 9),
        "B14",
    ),
    Spec(
        "hauptstaetter",
        STUTTGART,
        ROADWORKS,
        "Hauptstätter Straße: Leitungsarbeiten",
        "Ein Fahrstreifen stadteinwärts gesperrt.",
        (48.768, 9.176),
        name("Hauptstätter Straße"),
        0.4,
        span(-40, 60),
    ),
    Spec(
        "neckartal",
        STUTTGART,
        ROADWORKS,
        "Neckartalstraße: Sanierung der Ufermauer",
        "Fahrstreifen verengt.",
        (48.815, 9.215),
        name("Neckartalstraße"),
        0.8,
        span(-90, 120),
    ),
    Spec(
        "heilbronner",
        STUTTGART,
        ROADWORKS,
        "Heilbronner Straße: Gleisbau",
        "Abbiegen in die Nordbahnhofstraße nicht möglich.",
        (48.795, 9.183),
        name("Heilbronner Straße"),
        0.6,
        span(3, 30),
    ),
    Spec(
        "koenig-karl",
        LMS,
        CLOSURE,
        "König-Karl-Straße: Vollsperrung wegen Veranstaltung",
        "Umleitung über die Wilhelma.",
        (48.8045, 9.2155),
        name("König-Karl-Straße"),
        0.3,
        (Period(at(3, "08:00"), at(4, "20:00")),),
    ),
    Spec(
        "weinsteige",
        LMS,
        WARNING,
        "Neue Weinsteige: Ölspur",
        "Rutschgefahr, Feuerwehr vor Ort.",
        (48.758, 9.175),
        name("Neue Weinsteige"),
        0,
        ago(50),
        "B27",
    ),
    Spec(
        "rotebuehl",
        STUTTGART,
        ROADWORKS,
        "Rotebühlstraße: Kanalsanierung",
        "Fahrstreifen verengt.",
        (48.7735, 9.163),
        name("Rotebühlstraße"),
        0.4,
        span(-12, 16),
    ),
    Spec(
        "theodor-heuss",
        LMS,
        CLOSURE,
        "Theodor-Heuss-Straße: Vollsperrung am Abend",
        "Veranstaltung. Umleitung über die Friedrichstraße.",
        (48.778, 9.1735),
        name("Theodor-Heuss-Straße"),
        0.5,
        (Period(at(0, "18:00"), at(1, "01:00")),),
    ),
    Spec(
        "pragsattel",
        LMS,
        ACCIDENT,
        "Pragsattel: Unfall, ein Fahrstreifen gesperrt",
        "Unfall mit zwei Fahrzeugen.",
        (48.8105, 9.177),
        ref("B 10"),
        0,
        ago(15),
        "B10",
    ),
    Spec(
        "cannstatter",
        STUTTGART,
        ROADWORKS,
        "Cannstatter Straße: Neubau des Radwegs",
        "Rechter Fahrstreifen gesperrt.",
        (48.79, 9.195),
        name("Cannstatter Straße"),
        0.6,
        span(-30, 45),
    ),
    Spec(
        "schwab",
        STUTTGART,
        ROADWORKS,
        "Schwabstraße: Leitungsarbeiten",
        "Halbseitige Sperrung.",
        (48.771, 9.158),
        name("Schwabstraße"),
        0.3,
        span(-2, 5),
    ),
    Spec(
        "nordbahnhof",
        STUTTGART,
        ROADWORKS,
        "Nordbahnhofstraße: Gleisarbeiten",
        "Fahrstreifen verengt.",
        (48.796, 9.188),
        name("Nordbahnhofstraße"),
        0.5,
        span(-20, 8),
    ),
    Spec(
        "a8-degerloch",
        AUTOBAHN,
        ROADWORKS,
        "A8 | Stuttgart-Degerloch - Esslingen",
        "Fahrbahnsanierung, Fahrstreifen verengt.",
        (48.695, 9.205),
        A8,
        2.5,
        span(-25, 50),
        "A8",
        "Karlsruhe -> München",
    ),
    # Live reports of the other moments, where the ones above lie.
    Spec(
        "a81-jam-evening",
        AUTOBAHN,
        JAM,
        "A81 | Ludwigsburg-Nord - Pleidelsheim",
        "Stau im Feierabendverkehr, 5 km.",
        (48.935, 9.185),
        A81,
        3.0,
        ago(40, "evening"),
        "A81",
        S_HN,
        24,
        shape="a81-works",
    ),
    Spec(
        "heilbronner-accident",
        LMS,
        ACCIDENT,
        "Heilbronner Straße: Unfall, ein Fahrstreifen stadtauswärts gesperrt",
        "Auffahrunfall im Feierabendverkehr.",
        (48.795, 9.183),
        name("Heilbronner Straße"),
        0,
        ago(25, "evening"),
        shape="heilbronner",
        point=True,
    ),
    Spec(
        "a81-jam-weekend",
        AUTOBAHN,
        JAM,
        "A81 | Ludwigsburg-Nord - Pleidelsheim",
        "Stau wegen der Vollsperrung zwischen Mundelsheim und Ilsfeld.",
        (48.935, 9.185),
        A81,
        3.0,
        ago(55, "weekend"),
        "A81",
        S_HN,
        16,
        shape="a81-works",
    ),
]


# ---- Road geometry -----------------------------------------------------------


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Distance of two (lat, lon) points."""
    dlat = math.radians(b[0] - a[0])
    dlon = math.radians(b[1] - a[1]) * math.cos(math.radians((a[0] + b[0]) / 2))
    return 6371 * math.hypot(dlat, dlon)


def _ways(spec: Spec, radius: int) -> list[dict[str, Any]]:
    """The ways matching the spec within radius metres of its anchor."""
    lat, lon = spec.anchor
    query = f"[out:json][timeout:25];way(around:{radius},{lat},{lon}){spec.match};out body geom;"
    data = urllib.parse.urlencode({"data": query}).encode()
    for attempt in range(6):
        request = urllib.request.Request(
            OVERPASS[attempt % len(OVERPASS)],
            data=data,
            headers={"User-Agent": USER_AGENT},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                elements = json.load(response)["elements"]
            break
        except (urllib.error.HTTPError, TimeoutError) as err:  # busy: 429, 502, 504
            if attempt == 5 or getattr(err, "code", 504) not in (429, 502, 503, 504):
                raise
            time.sleep(5 * (attempt + 1))
    return [w for w in elements if w["type"] == "way"]


def fetch_road(spec: Spec) -> list[list[float]]:
    """Coordinates ([lon, lat]) of the road around the anchor, length_km long."""
    radius = int(max(1500, spec.length_km * 1000))
    ways = _ways(spec, radius)
    while not ways and radius < 6000:  # anchor a bit off the road: look further
        radius *= 2
        ways = _ways(spec, radius)
    if not ways:
        raise SystemExit(f"{spec.id}: no road matches {spec.match} near {spec.anchor}")

    def points(way: dict[str, Any]) -> list[tuple[int, tuple[float, float]]]:
        return [
            (n, (g["lat"], g["lon"]))
            for n, g in zip(way["nodes"], way["geometry"], strict=True)
        ]

    nearest = min(ways, key=lambda w: min(_km(spec.anchor, p) for _, p in points(w)))
    line = points(nearest)
    used = {nearest["id"]}

    def extend(forward: bool) -> bool:
        end = line[-1][0] if forward else line[0][0]
        for way in ways:
            if way["id"] in used:
                continue
            pts = points(way)
            if pts[0][0] == end or pts[-1][0] == end:
                if (pts[0][0] == end) != forward:
                    pts.reverse()
                used.add(way["id"])
                if forward:
                    line.extend(pts[1:])
                else:
                    line[:0] = pts[:-1]
                return True
        return False

    def length() -> float:
        return sum(_km(a[1], b[1]) for a, b in pairwise(line))

    while length() < spec.length_km * 2 and (extend(True) or extend(False)):
        pass

    coords = [p for _, p in line]
    centre = min(range(len(coords)), key=lambda i: _km(spec.anchor, coords[i]))
    if spec.length_km == 0:
        return [[round(coords[centre][1], 6), round(coords[centre][0], 6)]]
    first = last = centre
    half = spec.length_km / 2
    while first > 0 and _km(coords[first], coords[centre]) < half:
        first -= 1
    while last < len(coords) - 1 and _km(coords[last], coords[centre]) < half:
        last += 1
    return [[round(lo, 6), round(la, 6)] for la, lo in coords[first : last + 1]]


def geometry_cache(fetch: bool) -> dict[str, list[list[float]]]:
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    own = [s for s in SPECS if s.shape is None]
    missing = [s for s in own if s.id not in cache]
    if missing and not fetch:
        raise SystemExit(f"No geometry for {[s.id for s in missing]}: run with --fetch")
    known = {s.id for s in own}

    def save() -> None:
        kept = {k: v for k, v in sorted(cache.items()) if k in known}
        CACHE.write_text(json.dumps(kept, indent=1) + "\n", encoding="utf-8")

    for spec in missing:
        cache[spec.id] = fetch_road(spec)
        print(f"fetched {spec.id}: {len(cache[spec.id])} points")
        save()  # keep what we have if a later request fails
        time.sleep(2)  # Overpass etiquette
    save()
    return {k: v for k, v in cache.items() if k in known}


# ---- Events --------------------------------------------------------------------


def build_events(
    cache: dict[str, list[list[float]]], moment: str
) -> list[StreckenwachtEvent]:
    """The reports known at the moment: the planned ones and its live ones."""
    events = []
    for spec in SPECS:
        if isinstance(spec.periods, Live):
            if moment not in spec.periods.moments:
                continue
            start = MOMENTS[moment] - timedelta(minutes=spec.periods.minutes)
            periods: tuple[Period, ...] = (Period(start, None),)
        else:
            periods = spec.periods
        coords = cache[spec.shape or spec.id]
        lon, lat = coords[len(coords) // 2]
        if spec.point:
            coords = [[lon, lat]]
        events.append(
            StreckenwachtEvent(
                id=f"{spec.source.value}:demo-{spec.id}",
                source=spec.source,
                event_type=spec.type,
                title=spec.title,
                description=spec.description,
                road=spec.road,
                direction=spec.direction,
                latitude=lat,
                longitude=lon,
                geometry={"type": "LineString", "coordinates": coords}
                if len(coords) > 1
                else None,
                periods=periods,
                delay_minutes=spec.delay,
            )
        )
    return events


def entities(events: list[StreckenwachtEvent], now: datetime) -> dict[str, Any]:
    """States of the area's entities, as sensor.py and friends compute them."""
    current = active(events, now)
    counts = Counter(e.event_type for e in current)
    delay, delayed = max_delay(current)
    upcoming = next_closure(events, now)
    item = current_or_next(events, now)
    return {
        "events": {
            "state": len(current),
            "attributes": {t.value: counts[t] for t in EventType}
            | {"events": listed(current)},
        },
        "travel_time_loss": {
            "state": delay,
            "attributes": {
                "title": delayed.title if delayed else None,
                "direction": delayed.direction if delayed else None,
            },
        },
        "next_closure": {
            "state": upcoming.start.isoformat() if upcoming else None,
            "attributes": {
                "title": upcoming.event.title if upcoming else None,
                "end": upcoming.end.isoformat() if upcoming and upcoming.end else None,
            },
        },
        "disruption_active": {"state": "on" if disruptions(events, now) else "off"},
        "calendar": {
            "state": "on" if item and item.start <= now < item.end else "off",
            "attributes": {"message": item.event.title if item else None},
        },
    }


def calendar(events: list[StreckenwachtEvent], now: datetime) -> list[dict[str, Any]]:
    """Calendar entries of the moment's day and the next seven days."""
    day = now.replace(hour=0, minute=0)
    return [
        {
            "start": i.start.isoformat(),
            "end": i.end.isoformat(),
            "summary": i.event.title,
            "type": i.event.event_type.value,
        }
        for i in calendar_items(events, day, day + timedelta(days=8), now)
    ]


def _where(event: StreckenwachtEvent) -> str:
    """The blueprints' "(…)" after the title: direction, else road."""
    where = event.direction or event.road
    return f" ({where})" if where else ""


def notifications(
    events: list[StreckenwachtEvent], now: datetime, area: str
) -> list[dict[str, Any]]:
    """What the three blueprints (default settings) sent in the day up to now.

    Same texts as their templates, the title in German and English, with the
    area (the device "Streckenwacht <area>") when there are several. "when"
    (warning ahead of a closure) stays a timestamp: the page formats it after
    moving the dates.
    """
    head = f"Streckenwacht · {area}" if len(AREAS) > 1 else "Streckenwacht"
    sent: list[dict[str, Any]] = []
    since = now - timedelta(hours=24)
    for event in events:
        live = event.start if event.periods and event.end is None else None
        # Neue oder beendete Meldung: live reports appear when they start.
        if event.event_type in NEW_TYPES and live and since < live <= now:
            sent.append(
                {
                    "blueprint": "neue_meldung",
                    "at": live + POLL_DELAY,
                    "title": {
                        lang: f"{head}: {titles[event.event_type]}"
                        for lang, titles in NEW_TITLES.items()
                    },
                    "message": event.title + _where(event),
                }
            )
        # Vorwarnung: lead time before the start the sensor shows.
        if event.event_type is not EventType.CLOSURE:
            continue
        for period in event.periods:
            if period.start is None:
                continue
            fire = period.start - LEAD_TIME
            upcoming = next_closure(events, fire - timedelta(seconds=1))
            if since < fire <= now and upcoming and upcoming.start == period.start:
                sent.append(
                    {
                        "blueprint": "vorwarnung_sperrung",
                        "at": fire,
                        "when": period.start.isoformat(),
                        "title": {
                            lang: title.format(head=head)
                            for lang, title in CLOSURE_TITLE.items()
                        },
                        "message": upcoming.event.title + _where(upcoming.event),
                    }
                )
    # Stau-Benachrichtigung: the travel time loss crossed the threshold.
    delay, delayed = max_delay(active(events, now))
    if delayed and delay >= JAM_THRESHOLD and delayed.start:
        sent.append(
            {
                "blueprint": "stau_benachrichtigung",
                "at": delayed.start + POLL_DELAY,
                "title": {
                    lang: title.format(head=head, delay=delay)
                    for lang, title in JAM_TITLE.items()
                },
                "message": delayed.title + _where(delayed),
            }
        )
    sent = sorted((n for n in sent if n["at"] <= now), key=lambda n: n["at"])
    return [n | {"at": n["at"].isoformat()} for n in reversed(sent)]


def coverage() -> dict[str, Any]:
    """Regions of the sources, for the page's "does it work where I live?".

    The page repeats model.sources_for_circle: the circle's bounding box
    (geo.circle_bounds) must overlap a region of the source. The examples let
    it check that it gets the same answers.
    """
    south, _, north, _ = circle_bounds(50.0, 10.0, 100.0)
    examples = []
    for lat, lon, radius in (
        (48.7758, 9.1829, 15),
        (52.52, 13.405, 20),
        (50.94, 6.96, 10),
        (53.55, 10.0, 30),
        (51.34, 12.37, 25),
        (49.61, 6.13, 15),
        (50.11, 8.68, 40),
        (47.99, 7.85, 5),
    ):
        found = sources_for_circle(lat, lon, radius)
        examples.append([lat, lon, radius, [s.value for s in found]])
    return {
        "km_per_degree": 200.0 / (north - south),
        "sources": [
            {
                "id": source.value,
                "name": SOURCE_NAMES[source],
                "regions": [list(r) for r in SOURCE_REGIONS[source]]
                if source in SOURCE_REGIONS
                else None,
            }
            for source in Source
        ],
        "examples": examples,
    }


def _write(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--fetch", action="store_true", help="fetch missing road geometry"
    )
    cache = geometry_cache(parser.parse_args().fetch)
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.json"):
        if old.stem not in AREAS and old.stem != "coverage":
            old.unlink()
    for key, (slug, area) in AREAS.items():
        result: dict[str, Any] = {
            "slug": slug,
            "area": {
                "name": area.name,
                "latitude": area.latitude,
                "longitude": area.longitude,
                "radius_km": area.radius_km,
            },
            "moments": {},
        }
        for moment, now in MOMENTS.items():
            events = build_events(cache, moment)
            inside = merge_duplicates([e for e in events if area.contains(e)])
            features = map_features(inside, now)
            for feature in features:
                merged = len(feature["properties"]["also_reported_by"])
                feature["properties"]["attribution"] = ATTRIBUTION + (
                    f" ({merged + 1} Quellen zusammengeführt)" if merged else ""
                )
            view = {
                "now": now.isoformat(),
                "features": features,
                "entities": entities(inside, now),
                "calendar": calendar(inside, now),
                "notifications": notifications(inside, now, area.name),
            }
            result["moments"][moment] = view
            states = {k: v["state"] for k, v in view["entities"].items()}
            print(
                f"{key} {moment}: {len(inside)} events, {len(features)} on the map, "
                f"{[n['blueprint'] for n in view['notifications']]}, {states}"
            )
        _write(OUT / f"{key}.json", result)
    _write(OUT / "coverage.json", coverage())
    for path in sorted(OUT.glob("*.json")):
        print(f"{path.name}: {path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
