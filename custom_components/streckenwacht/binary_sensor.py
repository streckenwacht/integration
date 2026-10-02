"""Binary sensor per observation area: a disruption is active."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import StreckenwachtConfigEntry
from .const import SUBENTRY_AREA
from .entity import TimeDependentEntity
from .summary import disruptions, listed


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StreckenwachtConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """One sensor per observation area."""
    for subentry in entry.get_subentries_of_type(SUBENTRY_AREA):
        async_add_entities(
            [DisruptionBinarySensor(entry, subentry, "disruption")],
            config_subentry_id=subentry.subentry_id,
        )


class DisruptionBinarySensor(TimeDependentEntity, BinarySensorEntity):
    """On while a closure, accident or traffic jam is active in the area.

    Plain roadworks do not count (many run for years); they are in the
    calendar and the events sensor.
    """

    _attr_translation_key = "disruption"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        """Return True if a disruption is active."""
        return bool(disruptions(self.area_events, dt_util.utcnow()))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Active disruptions, most severe first."""
        active = disruptions(self.area_events, dt_util.utcnow())
        return {
            "count": len(active),
            "disruptions": listed(active),
            "unavailable_sources": self.unavailable_sources,
        }
