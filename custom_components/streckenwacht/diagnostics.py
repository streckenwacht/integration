"""Diagnostics download (Settings > Devices & services > Streckenwacht > ⋮).

Diagnostics end up in public GitHub issues: area coordinates are redacted,
because the center of an area named "Home" is the user's address.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from . import StreckenwachtConfigEntry
from .const import VERSION
from .summary import event_attributes

TO_REDACT = {CONF_LATITUDE, CONF_LONGITUDE}
SAMPLE_EVENTS = 5


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: StreckenwachtConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for the config entry."""
    coordinators = entry.runtime_data.coordinators
    return {
        "version": VERSION,
        "options": dict(entry.options),
        "areas": {
            subentry_id: {
                "title": subentry.title,
                "data": async_redact_data(dict(subentry.data), TO_REDACT),
            }
            for subentry_id, subentry in entry.subentries.items()
        },
        "sources": {
            source.value: {
                "last_update_success": coordinator.last_update_success,
                "consecutive_failures": coordinator.failures,
                "last_exception": (
                    repr(coordinator.last_exception)
                    if coordinator.last_exception
                    else None
                ),
                "update_interval_seconds": (
                    coordinator.update_interval.total_seconds()
                    if coordinator.update_interval
                    else None
                ),
                "events_total": len(coordinator.data.events)
                if coordinator.data
                else None,
                "events_per_area": (
                    {
                        sid: len(events)
                        for sid, events in coordinator.data.by_area.items()
                    }
                    if coordinator.data
                    else None
                ),
                # A few raw-ish samples help to spot parsing problems.
                "sample_events": (
                    [
                        async_redact_data(event_attributes(event), TO_REDACT)
                        for event in coordinator.data.events[:SAMPLE_EVENTS]
                    ]
                    if coordinator.data
                    else []
                ),
            }
            for source, coordinator in coordinators.items()
        },
    }
