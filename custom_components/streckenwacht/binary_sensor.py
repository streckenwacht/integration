"""Binary sensor per observation area: a disruption is active."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import StreckenwachtConfigEntry
from .const import CONF_JAM_THRESHOLD, DEFAULT_JAM_THRESHOLD
from .coordinator import area_subentries
from .entity import TimeDependentEntity
from .model import StreckenwachtEvent
from .summary import disruptions, listed


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StreckenwachtConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """One sensor per observation area."""
    for subentry in area_subentries(entry):
        async_add_entities(
            [DisruptionBinarySensor(entry, subentry, "disruption")],
            config_subentry_id=subentry.subentry_id,
        )


class DisruptionBinarySensor(TimeDependentEntity, BinarySensorEntity):
    """On while a closure, accident or traffic jam is active in the area.

    Plain roadworks do not count (many run for years); they are in the
    calendar and the events sensor.
    """

    # No device class "problem": HA would show "Problem/OK" instead of "On/Off";
    # the warning icon comes from icons.json.
    _attr_translation_key = "disruption"

    @property
    def is_on(self) -> bool:
        """Return True if a disruption is active."""
        return bool(self._active())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Active disruptions, most severe first."""
        active = self._active()
        return {
            "count": len(active),
            "disruptions": listed(active),
            "unavailable_sources": self.unavailable_sources,
        }

    def _active(self) -> list[StreckenwachtEvent]:
        threshold = self._subentry_data.get(CONF_JAM_THRESHOLD, DEFAULT_JAM_THRESHOLD)
        return disruptions(self.area_events, dt_util.utcnow(), int(threshold))
