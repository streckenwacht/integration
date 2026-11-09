"""City sources in North Rhine-Westphalia: Aachen, Duisburg.

NRW has no open statewide roadworks data; these cities publish their own
(Dortmund has a module of its own; Köln's traffic calendar and Münster's
roadworks WFS were removed in 2026-11 after their services stopped answering). Bochum's data is not under an
open licence and is left out. See docs/ENTWICKLUNG.md, section 2.
"""

from __future__ import annotations

import re
from typing import Any, ClassVar

from ..const import AACHEN, DUISBURG, Source
from ..model import EventType, Period, StreckenwachtEvent
from .wfs import (
    GeoJsonProvider,
    Layer,
    WfsProvider,
    closes_road,
    first_position,
    german_period,
    iso_date,
    text,
    unglue,
)

# Restrictions only on footpaths or parking spaces are left out.
_TRAFFIC = re.compile(
    r"Fahrbahn|Fahrstreifen|Vollsperrung|Straße|Einbahn|Umleitung|Verkehr|Kreuzung",
    re.IGNORECASE,
)


def _event(
    feature: dict[str, Any],
    source: Source,
    *,
    event_type: EventType,
    title: str,
    description: str | None,
    road: str | None,
    period: Period | None,
) -> StreckenwachtEvent:
    lat, lon = first_position(feature.get("geometry"))
    return StreckenwachtEvent(
        id="",  # set by parse_layer
        source=source,
        event_type=event_type,
        title=title,
        description=description,
        road=road,
        latitude=lat,
        longitude=lon,
        geometry=feature.get("geometry"),
        periods=(period,) if period and (period.start or period.end) else (),
    )


def _lines(*parts: str | None) -> str | None:
    return "\n".join(p for p in parts if p) or None


# --- Aachen (WFS, Baustelleninformationssystem BSIS) ------------------------


def parse_aachen(feature: dict[str, Any]) -> tuple[str, StreckenwachtEvent] | None:
    """Roadworks; "symbol" holds severity and state ("Vollsperrung - aktuell")."""
    props = feature["properties"]
    severity, _, state = (text(props.get("symbol")) or "").partition(" - ")
    if state == "abgelaufen":
        return None
    restriction = unglue(text(props.get("einschraen")))
    if restriction and not _TRAFFIC.search(restriction):
        return None  # footpath or parking only
    street = text(props.get("strassen"))
    what = text(props.get("name")) or text(props.get("art")) or "Baustelle"
    start = iso_date((text(props.get("von")) or "").removesuffix("Z"))
    end = iso_date((text(props.get("bis")) or "").removesuffix("Z"), end=True)
    event = _event(
        feature,
        Source.AACHEN,
        event_type=EventType.CLOSURE
        if severity == "Vollsperrung"
        else EventType.ROADWORKS,
        title=f"{street}: {what}" if street else what,
        description=_lines(
            severity or None,
            text(props.get("bereich")),
            restriction.replace("\r\n", " ").replace("\n", " ")
            if restriction
            else None,
        ),
        road=street,
        period=Period(start, end) if start or end else None,
    )
    return str(props.get("sdatenid") or props.get("gid")), event


class AachenProvider(WfsProvider):
    """Roadworks in Aachen (~50 KB gzipped, fetched whole)."""

    source = Source.AACHEN
    url = "https://bsis.aachen.de/geoserver/ows"
    output_format = "application/json"
    filter_by_bbox = False
    layers = (Layer("BSIS:PUNKTE_ALLE", AACHEN, parse_aachen),)


# --- Duisburg (ArcGIS REST, Verkehrsportal) ---------------------------------

_SHORT_YEAR = re.compile(r"\b(\d{1,2}\.\d{1,2}\.)(\d{2})\b")


def parse_duisburg(feature: dict[str, Any]) -> tuple[str, StreckenwachtEvent] | None:
    """Roadworks; the meaning of SYMBOL_ID is not documented, so closures are
    only recognised from the text."""
    props = feature["properties"]
    street = text(props.get("BEZEICHNUNG_BM_MP"))
    section = text(props.get("BEZEICHNUNG_AB_MP"))
    tip = text(props.get("TIPP"))
    diversion = text(props.get("UMLEITUNG"))
    # "12.10.26 - 30.10.26": two-digit years
    duration = _SHORT_YEAR.sub(r"\g<1>20\2", text(props.get("BAUZEIT_AB")) or "")
    event = _event(
        feature,
        Source.DUISBURG,
        event_type=EventType.CLOSURE
        if closes_road(" ".join(p for p in (section, tip) if p))
        else EventType.ROADWORKS,
        title=f"{street}: {section}" if street and section else street or "Baustelle",
        description=_lines(
            section,
            tip,
            f"Umleitung: {diversion}" if diversion else None,
        ),
        road=street,
        period=german_period(duration.replace(" - ", " bis ")),
    )
    return str(props["OBJECTID"]), event


class DuisburgProvider(GeoJsonProvider):
    """Current roadworks in Duisburg (~15 KB gzipped, with ETag)."""

    source = Source.DUISBURG
    urls = (
        "https://geoportal2.duisburg.de/arcgisserver/rest/services/Masterportal/"
        "MP_Verkehrsportal/MapServer/2/query",
    )
    params: ClassVar[dict[str, str]] = {
        "where": "1=1",
        "outFields": "*",
        "f": "geojson",
        "outSR": "4326",
    }
    region = DUISBURG
    layer = Layer("duisburg", DUISBURG, parse_duisburg)
