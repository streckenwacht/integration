"""Sensors per observation area: active events and travel time loss."""

from __future__ import annotations

from collections import Counter
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
from .const import CONF_INCLUDE_INRIX, DEFAULT_INCLUDE_INRIX, SUBENTRY_AREA, Source
from .entity import TimeDependentEntity
from .model import EventType
from .summary import active, listed, max_delay


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
    for subentry in entry.get_subentries_of_type(SUBENTRY_AREA):
        entities: list[SensorEntity] = [EventsSensor(entry, subentry, "events")]
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
        """The event causing the delay."""
        _, event = max_delay(self.area_events, dt_util.utcnow())
        return {
            "title": event.title if event else None,
            "road": event.road if event else None,
            "direction": event.direction if event else None,
            "unavailable_sources": self.unavailable_sources,
        }
