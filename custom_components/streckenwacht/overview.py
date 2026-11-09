"""Short overviews at the top of the settings forms: what an area (or the
whole entry) is set up with, and what is missing for messages to arrive.

Pure Python, no Home Assistant imports. The texts are built here in German
or English: the placeholders of a form are not translated.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .const import (
    CONF_AREA_SOURCES,
    CONF_DIRECTIONS,
    CONF_JAM_THRESHOLD,
    CONF_RADIUS,
    CONF_ROADS,
    CONF_TYPES,
    DEFAULT_JAM_THRESHOLD,
    DEFAULT_RADIUS,
    GERMANY,
    SOURCE_NAMES,
    Source,
)
from .geo import bounds_overlap, circle_bounds, haversine_km
from .model import EventType, sources_for_circle

# Automations named in an area's overview; more are counted.
MAX_AUTOMATIONS = 3

TEXTS: dict[str, dict[str, str]] = {
    "de": {
        "configured": "**Eingerichtet**",
        "missing": "**Was fehlt**",
        "centre": "Mittelpunkt: {place}, Radius {radius} km",
        "sources": "Quellen: {names}",
        "roads": "Autobahnen: {roads} ({details})",
        "all_directions": "alle Richtungen",
        "directions": "Richtung {names}",
        "jam": "Stau zählt ab {minutes} min",
        "types": "Meldungsarten: {names}",
        "all_types": "alle",
        "automations": "Automationen: {names}",
        "no_automations": (
            "Automationen: keine (Push-Nachrichten z. B. mit den Blueprints "
            "von Streckenwacht)"
        ),
        "more": "{names} und {count} weitere",
        "events_one": "Zurzeit 1 Meldung",
        "events": "Zurzeit {count} Meldungen",
        "nothing_covers": (
            "Keine gewählte Quelle deckt diesen Kreis ab – hier kommen keine Meldungen."
        ),
        "not_covering": "Kreis außerhalb ihres Gebiets, liefern hier nichts: {names}",
        "also_available": "Nicht gewählt, hier aber verfügbar: {names}",
        "inrix": (
            "Staus und Reisezeitverlust nur mit INRIX – in den Optionen von "
            "Streckenwacht einschalten."
        ),
        "unreachable": "Zurzeit nicht erreichbar: {names} (siehe Reparaturen)",
        "area": "{name}: Radius {radius} km, {sources}",
        "area_events": "{name}: Radius {radius} km, {sources}, {events}",
        "sources_one": "1 Quelle",
        "sources_count": "{count} Quellen",
        "events_short_one": "zurzeit 1 Meldung",
        "events_short": "zurzeit {count} Meldungen",
        "no_areas": (
            "Noch kein Beobachtungsbereich – ohne ihn keine Meldungen. Anlegen "
            "über „Beobachtungsbereich hinzufügen“ bei Streckenwacht."
        ),
    },
    "en": {
        "configured": "**Set up**",
        "missing": "**Missing**",
        "centre": "Centre: {place}, radius {radius} km",
        "sources": "Sources: {names}",
        "roads": "Motorways: {roads} ({details})",
        "all_directions": "all directions",
        "directions": "direction {names}",
        "jam": "jam counts from {minutes} min",
        "types": "Kinds of reports: {names}",
        "all_types": "all",
        "automations": "Automations: {names}",
        "no_automations": (
            "Automations: none (push notifications e.g. with the Streckenwacht "
            "blueprints)"
        ),
        "more": "{names} and {count} more",
        "events_one": "Currently 1 event",
        "events": "Currently {count} events",
        "nothing_covers": (
            "No selected source covers this circle – no events will arrive here."
        ),
        "not_covering": "Circle outside their region, nothing from them here: {names}",
        "also_available": "Not chosen, but available here: {names}",
        "inrix": (
            "Traffic jams and travel time loss need INRIX – switch it on in the "
            "Streckenwacht options."
        ),
        "unreachable": "Currently unreachable: {names} (see Repairs)",
        "area": "{name}: radius {radius} km, {sources}",
        "area_events": "{name}: radius {radius} km, {sources}, {events}",
        "sources_one": "1 source",
        "sources_count": "{count} sources",
        "events_short_one": "currently 1 event",
        "events_short": "currently {count} events",
        "no_areas": (
            "No observation area yet – no events without one. Add one with "
            "“Add observation area” on Streckenwacht."
        ),
    },
}

TYPE_NAMES: dict[str, dict[EventType, str]] = {
    "de": {
        EventType.ROADWORKS: "Baustellen",
        EventType.CLOSURE: "Sperrungen",
        EventType.TRAFFIC_JAM: "Staus",
        EventType.ACCIDENT: "Unfälle",
        EventType.WARNING: "Warnungen und Veranstaltungen",
    },
    "en": {
        EventType.ROADWORKS: "Roadworks",
        EventType.CLOSURE: "Closures",
        EventType.TRAFFIC_JAM: "Traffic jams",
        EventType.ACCIDENT: "Accidents",
        EventType.WARNING: "Warnings and events",
    },
}


@dataclass(frozen=True, slots=True)
class Zone:
    """A Home Assistant zone, to name an area's centre."""

    name: str
    latitude: float
    longitude: float
    radius_km: float


def place_name(lat: float, lon: float, zones: Sequence[Zone]) -> str | None:
    """The nearest zone the point lies in, e.g. "Home"; None outside all."""
    inside = [
        (distance, zone.name)
        for zone in zones
        if (distance := haversine_km(lat, lon, zone.latitude, zone.longitude))
        <= zone.radius_km
    ]
    return min(inside)[1] if inside else None


def area_overview(
    data: Mapping[str, Any],
    *,
    language: str,
    include_inrix: bool,
    place: str | None = None,
    events: int | None = None,
    automations: Sequence[str] = (),
    unreachable: Collection[Source] = (),
) -> str:
    """Markdown overview of an area: centre, sources (and those available
    here but not chosen), motorways, kinds of reports, automations, current
    events, then what is missing (if anything).

    `events` is None while the entry is not loaded; `unreachable` are the
    sources failing right now (any, only the area's are named).
    """
    t = TEXTS[language]
    lat, lon = float(data["latitude"]), float(data["longitude"])
    radius_km = float(data.get(CONF_RADIUS) or DEFAULT_RADIUS) / 1000
    chosen = _sources(data)
    roads = list(data.get(CONF_ROADS) or ())
    types = data.get(CONF_TYPES)

    lines = [
        t["centre"].format(
            place=place or f"{lat:.2f}, {lon:.2f}", radius=_km(radius_km, language)
        ),
        t["sources"].format(names=_names(chosen) or "–"),
    ]
    covering = _covering(lat, lon, radius_km)
    # Those the sources step offers and that would deliver something here:
    # named next to the sources, not as missing (often left out on purpose).
    if extra := [s for s in Source if s in covering and s not in chosen]:
        lines.append(t["also_available"].format(names=_names(extra)))
    if Source.AUTOBAHN in chosen and roads:
        directions = list(data.get(CONF_DIRECTIONS) or ())
        details = [
            t["directions"].format(names="; ".join(directions))
            if directions
            else t["all_directions"]
        ]
        if include_inrix:
            minutes = data.get(CONF_JAM_THRESHOLD, DEFAULT_JAM_THRESHOLD)
            details.append(t["jam"].format(minutes=minutes))
        lines.append(
            t["roads"].format(roads=", ".join(roads), details=", ".join(details))
        )
    lines.append(
        t["types"].format(
            names=", ".join(
                TYPE_NAMES[language][kind] for kind in EventType if kind in types
            )
            if types
            else t["all_types"]
        )
    )
    if automations:
        named = ", ".join(automations[:MAX_AUTOMATIONS])
        if len(automations) > MAX_AUTOMATIONS:
            named = t["more"].format(
                names=named, count=len(automations) - MAX_AUTOMATIONS
            )
        lines.append(t["automations"].format(names=named))
    else:
        lines.append(t["no_automations"])
    if events is not None:
        lines.append(
            t["events_one"] if events == 1 else t["events"].format(count=events)
        )

    missing: list[str] = []
    outside = [s for s in chosen if s not in covering]
    if chosen and len(outside) == len(chosen):
        missing.append(t["nothing_covers"])
    elif outside:
        missing.append(t["not_covering"].format(names=_names(outside)))
    if (
        not include_inrix
        and Source.AUTOBAHN in chosen
        and (not types or EventType.TRAFFIC_JAM in types)
    ):
        missing.append(t["inrix"])
    if failing := [s for s in chosen if s in unreachable]:
        missing.append(t["unreachable"].format(names=_names(failing)))
    return _markdown(t, lines, missing)


def entry_overview(
    areas: Sequence[tuple[str, Mapping[str, Any], int | None]],
    *,
    language: str,
    unreachable: Collection[Source] = (),
) -> str:
    """Markdown overview of the whole entry: one line per area (name, radius,
    number of sources, current events if loaded), then what is missing."""
    t = TEXTS[language]
    lines = []
    for name, data, events in areas:
        count = len(_sources(data))
        values = {
            "name": name,
            "radius": _km(
                float(data.get(CONF_RADIUS) or DEFAULT_RADIUS) / 1000, language
            ),
            "sources": t["sources_one"]
            if count == 1
            else t["sources_count"].format(count=count),
        }
        if events is None:
            lines.append(t["area"].format(**values))
        else:
            values["events"] = (
                t["events_short_one"]
                if events == 1
                else t["events_short"].format(count=events)
            )
            lines.append(t["area_events"].format(**values))
    missing = [] if areas else [t["no_areas"]]
    used = {s for _, data, _ in areas for s in _sources(data)}
    if failing := [s for s in Source if s in unreachable and s in used]:
        missing.append(t["unreachable"].format(names=_names(failing)))
    return _markdown(t, lines, missing)


def _sources(data: Mapping[str, Any]) -> list[Source]:
    """The area's sources in their usual order (removed ones skipped); areas
    without a list (before 0.2.1) show the Autobahn."""
    stored = data.get(CONF_AREA_SOURCES)
    if stored is None:
        return [Source.AUTOBAHN]
    return [s for s in Source if s.value in stored]


def _covering(lat: float, lon: float, radius_km: float) -> set[Source]:
    """Sources whose region the circle touches; the Autobahn in Germany."""
    covering = set(sources_for_circle(lat, lon, radius_km))
    if not bounds_overlap(circle_bounds(lat, lon, radius_km), GERMANY):
        covering.discard(Source.AUTOBAHN)
    return covering


def _names(sources: Sequence[Source]) -> str:
    return ", ".join(SOURCE_NAMES[s] for s in sources)


def _km(radius_km: float, language: str) -> str:
    """Whole km, below 10 km with one decimal (no trailing .0); German comma."""
    text = (
        f"{radius_km:.0f}" if radius_km >= 10 else f"{radius_km:.1f}".removesuffix(".0")
    )
    return text.replace(".", ",") if language == "de" else text


def _markdown(t: Mapping[str, str], lines: list[str], missing: list[str]) -> str:
    blocks = [
        "\n".join([t[heading], *(f"- {line}" for line in items)])
        for heading, items in (("configured", lines), ("missing", missing))
        if items
    ]
    return "\n\n".join(blocks)
