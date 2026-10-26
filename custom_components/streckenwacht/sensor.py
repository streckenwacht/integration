"""Sensors per observation area: active events, travel time loss, next closure."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import StreckenwachtConfigEntry
from .const import CONF_INCLUDE_INRIX, DEFAULT_INCLUDE_INRIX, Source
from .coordinator import area_subentries
from .entity import TimeDependentEntity
from .model import EventType
from .summary import active, delays_by_direction, listed, max_delay, next_closure


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StreckenwachtConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Events sensor per area; travel time loss only if jam data is used."""
    with_delay = (
        Source.AUTOBAHN in entry.runtime_data.coordinators
        and entry.options.get(CONF_INCLUDE_INRIX, DEFAULT_INCLUDE_INRIX)
    )
    for subentry in area_subentries(entry):
        entities: list[SensorEntity] = [
            EventsSensor(entry, subentry, "events"),
            NextClosureSensor(entry, subentry, "next_closure"),
        ]
        if with_delay:
            entities.append(TravelTimeLossSensor(entry, subentry, "travel_time_loss"))
        async_add_entities(entities, config_subentry_id=subentry.subentry_id)


class EventsSensor(TimeDependentEntity, SensorEntity):
    """Number of currently active events (all types)."""

    _attr_translation_key = "events"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        """Return the number of active events."""
        return len(active(self.area_events, dt_util.utcnow()))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Counts per type and the active events, most severe first."""
        events = active(self.area_events, dt_util.utcnow())
        counts = Counter(e.event_type for e in events)
        return {
            **{event_type.value: counts[event_type] for event_type in EventType},
            "by_source": dict(Counter(e.source.value for e in events)),
            "events": listed(events),
            "unavailable_sources": self.unavailable_sources,
        }


class TravelTimeLossSensor(TimeDependentEntity, SensorEntity):
    """Largest current travel time loss in the area (0 without traffic jams)."""

    _attr_translation_key = "travel_time_loss"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        """Return the largest delay in minutes."""
        return max_delay(self.area_events, dt_util.utcnow())[0]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The event causing the delay, and the largest delay per direction."""
        now = dt_util.utcnow()
        _, event = max_delay(self.area_events, now)
        return {
            "title": event.title if event else None,
            "road": event.road if event else None,
            "direction": event.direction if event else None,
            "by_direction": delays_by_direction(self.area_events, now),
            "unavailable_sources": self.unavailable_sources,
        }


class NextClosureSensor(TimeDependentEntity, SensorEntity):
    """Start of the next planned closure in the area (within two weeks).

    A timestamp, so automations can use it with a time trigger and an offset,
    e.g. a warning the evening before.
    """

    _attr_translation_key = "next_closure"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        """Return the start of the next closure, if any."""
        upcoming = next_closure(self.area_events, dt_util.utcnow())
        return upcoming.start if upcoming else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """What closes, and until when."""
        upcoming = next_closure(self.area_events, dt_util.utcnow())
        event = upcoming.event if upcoming else None
        return {
            "title": event.title if event else None,
            "road": event.road if event else None,
            "direction": event.direction if event else None,
            "end": upcoming.end.isoformat() if upcoming and upcoming.end else None,
            "source": event.source.value if event else None,
            "id": event.id if event else None,
            "unavailable_sources": self.unavailable_sources,
        }
