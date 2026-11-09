"""Button per observation area: a short report for a bug report, shown as a
notification (issue_report.py).

Areas give away where someone lives and works. The report therefore holds no
coordinates, area names, roads, directions or event texts, and no error
messages (their URLs name the chosen roads): areas appear by number and
shape, sources by key with the state of their last poll, the options by a
positive list.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import StreckenwachtConfigEntry
from .const import (
    CONF_AREA_SOURCES,
    CONF_DIRECTIONS,
    CONF_INCLUDE_INRIX,
    CONF_JAM_THRESHOLD,
    CONF_MERGE_DUPLICATES,
    CONF_RADIUS,
    CONF_ROADS,
    CONF_SCAN_INTERVAL,
    CONF_TYPES,
    DEFAULT_INCLUDE_INRIX,
    DEFAULT_JAM_THRESHOLD,
    DEFAULT_MERGE_DUPLICATES,
    DEFAULT_RADIUS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    VERSION,
)
from .coordinator import StreckenwachtCoordinator, area_subentries
from .entity import StreckenwachtEntity
from .frontend_resource import card_status
from .issue_report import Lines, build, show, text

NAME = "Streckenwacht"

INTRO = {
    "de": (
        "Zum Kopieren für eine Fehlermeldung auf GitHub. Der Bericht enthält "
        "keine Koordinaten, Namen der Bereiche, Straßen, Meldungstexte oder "
        "Entity-IDs. Die Datenquellen verraten aber die grobe Region (bei einer "
        "Stadtquelle die Stadt) – lies ihn vor dem Teilen und lösche, was du "
        "nicht zeigen willst."
    ),
    "en": (
        "To copy into a bug report on GitHub. The report holds no coordinates, "
        "area names, roads, event texts or entity ids. The data sources do "
        "give away the rough region (the city, for a city source) - read it "
        "before you share it and delete what you would rather not show."
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StreckenwachtConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """One button per observation area; each reports the whole entry."""
    for subentry in area_subentries(entry):
        async_add_entities(
            [IssueReport(entry, subentry, "issue_report")],
            config_subentry_id=subentry.subentry_id,
        )


class IssueReport(StreckenwachtEntity, ButtonEntity):
    """A short report to copy into a bug report, as a notification: what an
    issue needs without the diagnostics download (issue_report.py)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "issue_report"

    @callback
    def _handle_coordinator_update(self) -> None:
        """A button has no state that follows the data."""

    async def async_press(self) -> None:
        entry = self._entry
        report = build(
            self.hass,
            DOMAIN,
            NAME,
            VERSION,
            entry,
            extra=self._entry_lines(),
            more=[("areas", self._area_lines())],
            endpoints=[
                (source.value, coordinator_line(coordinator, dt_util.utcnow()))
                for source, coordinator in entry.runtime_data.coordinators.items()
            ],
            setting_lines=settings_lines(entry.options),
            # A single entry: every issue of the domain is its own.
            all_domain_issues=True,
        )
        show(self.hass, DOMAIN, NAME, entry, report, intro=INTRO)

    def _entry_lines(self) -> Lines:
        runtime = self._entry.runtime_data
        ids = [s.subentry_id for s in area_subentries(self._entry)]
        # Every event once, even if it lies in several areas.
        events = {e.id: e for sid in ids for e in runtime.area_events(sid)}
        by_type = Counter(e.event_type.value for e in events.values())
        return [
            ("areas", str(len(ids))),
            (
                "report from area",
                str(ids.index(self._subentry_id) + 1)
                if self._subentry_id in ids
                else "-",
            ),
            ("sources polled", str(len(runtime.coordinators))),
            (
                "events in the areas",
                ", ".join(f"{t} {n}" for t, n in by_type.most_common()) or "none",
            ),
            ("map card", card_status(self.hass)),
        ]

    def _area_lines(self) -> Lines:
        runtime = self._entry.runtime_data
        return [
            (
                f"area {number}",
                area_line(
                    subentry.data, len(runtime.area_events(subentry.subentry_id))
                ),
            )
            for number, subentry in enumerate(area_subentries(self._entry), start=1)
        ]


def settings_lines(options: Mapping[str, Any]) -> Lines:
    """The options from a positive list, defaults filled in: an option added
    later shows up only once it is listed here."""
    return [
        (
            CONF_SCAN_INTERVAL,
            f"{options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)} min",
        ),
        (
            CONF_INCLUDE_INRIX,
            text(options.get(CONF_INCLUDE_INRIX, DEFAULT_INCLUDE_INRIX)),
        ),
        (
            CONF_MERGE_DUPLICATES,
            text(options.get(CONF_MERGE_DUPLICATES, DEFAULT_MERGE_DUPLICATES)),
        ),
    ]


def area_line(data: Mapping[str, Any], events: int) -> str:
    """An area by its shape: the radius in km as in the settings overview
    (below 10 km with one decimal), how many sources, roads and directions,
    which types, the jam threshold and how many events it has. Never its
    centre, name, roads or directions themselves."""
    radius_km = float(data.get(CONF_RADIUS, DEFAULT_RADIUS)) / 1000
    radius = (
        f"{radius_km:.0f}" if radius_km >= 10 else f"{radius_km:.1f}".removesuffix(".0")
    )
    sources = data.get(CONF_AREA_SOURCES)
    roads = data.get(CONF_ROADS) or ()
    directions = data.get(CONF_DIRECTIONS) or ()
    types = data.get(CONF_TYPES)
    parts = [
        f"radius {radius} km",
        f"sources {len(sources) if sources is not None else 'not set'}",
        f"roads {len(roads)}",
    ]
    if roads:
        parts += [
            f"directions {len(directions) or 'all'}",
            f"jam threshold {data.get(CONF_JAM_THRESHOLD, DEFAULT_JAM_THRESHOLD)} min",
        ]
    parts += [
        f"types {'/'.join(sorted(types)) if types else 'all'}",
        f"events {events}",
    ]
    return ", ".join(parts)


def coordinator_line(coordinator: StreckenwachtCoordinator, now: datetime) -> str:
    """The state of a source's last poll, without its error message."""
    data = coordinator.data
    return source_line(
        success=coordinator.last_update_success,
        failures=coordinator.failures,
        failure=coordinator.last_failure,
        since=now - coordinator.last_success if coordinator.last_success else None,
        fetched=len(data.events) if data else None,
        in_areas=(
            len({e.id for events in data.by_area.values() for e in events})
            if data
            else None
        ),
    )


def source_line(
    *,
    success: bool,
    failures: int,
    failure: str | None,
    since: timedelta | None,
    fetched: int | None,
    in_areas: int | None,
) -> str:
    """E.g. "ok, 3 min ago, 1520 fetched, 12 in the areas" or "failed 3x
    (timeout), last success 2 h ago, 12 in the areas kept"."""
    last = f"{_ago(since)} ago" if since is not None else "never"
    if success:
        parts = ["ok", last]
    else:
        parts = [f"failed {failures}x ({failure or 'unknown'})", f"last success {last}"]
    if fetched is None:
        parts.append("no data")
    else:
        kept = "" if success else " kept"
        parts += [f"{fetched} fetched", f"{in_areas} in the areas{kept}"]
    return ", ".join(parts)


def _ago(delta: timedelta) -> str:
    minutes = max(0, int(delta.total_seconds() // 60))
    if minutes < 120:
        return f"{minutes} min"
    if minutes < 48 * 60:
        return f"{minutes // 60} h"
    return f"{minutes // (24 * 60)} d"
