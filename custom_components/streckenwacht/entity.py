"""Base entity: one device per observation area, fed by all coordinators."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    ATTRIBUTION,
    CONF_INCLUDE_INRIX,
    DEFAULT_INCLUDE_INRIX,
    DOMAIN,
    SOURCE_NAMES,
    UPSTREAM_ATTRIBUTION,
    UPSTREAM_INRIX,
    Source,
)
from .model import StreckenwachtEvent

if TYPE_CHECKING:
    from . import StreckenwachtConfigEntry
    from .coordinator import StreckenwachtCoordinator

# Periods start and end between polls (night closures at 22:00): time-dependent
# states are re-evaluated this often, independent of the poll interval.
TICK = timedelta(minutes=1)


class StreckenwachtEntity(Entity):
    """An entity of one observation area.

    It combines the events of all sources for its area. Entities stay
    available while a source fails and show its last known data; failing
    sources are listed in the "unavailable_sources" attribute.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, entry: StreckenwachtConfigEntry, subentry: ConfigSubentry, key: str
    ) -> None:
        self._entry = entry
        self._subentry_id = subentry.subentry_id
        self._subentry_data = subentry.data
        self._attr_unique_id = f"{subentry.subentry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=f"Streckenwacht {subentry.title}",
            manufacturer="Streckenwacht",
            entry_type=DeviceEntryType.SERVICE,
        )
        attributions = [ATTRIBUTION[source] for source in self._coordinators]
        if Source.AUTOBAHN in self._coordinators and entry.options.get(
            CONF_INCLUDE_INRIX, DEFAULT_INCLUDE_INRIX
        ):
            attributions.append(UPSTREAM_ATTRIBUTION[UPSTREAM_INRIX])
        self._attr_attribution = "; ".join(attributions)

    @property
    def _coordinators(self) -> dict[Source, StreckenwachtCoordinator]:
        return self._entry.runtime_data.coordinators

    @property
    def area_events(self) -> list[StreckenwachtEvent]:
        """All known events of this area, from every source (duplicates merged)."""
        return self._entry.runtime_data.area_events(self._subentry_id)

    @property
    def unavailable_sources(self) -> list[str]:
        """Names of sources whose last poll failed (their data may be stale)."""
        return [
            SOURCE_NAMES[source]
            for source, coordinator in self._coordinators.items()
            if not coordinator.last_update_success
        ]

    async def async_added_to_hass(self) -> None:
        """Follow every coordinator (this also starts their polling)."""
        await super().async_added_to_hass()
        for coordinator in self._coordinators.values():
            self.async_on_remove(
                coordinator.async_add_listener(self._handle_coordinator_update)
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()


class TimeDependentEntity(StreckenwachtEntity):
    """An entity whose state depends on the clock, not only on new data.

    HA reads the state and the attributes separately for one state write.
    During a write both see the same moment (`now`), and views needed by both
    (e.g. the active events) are computed only once (`_per_write`).
    """

    _write_now: datetime | None = None
    _write_cache: dict[str, Any] | None = None

    @property
    def now(self) -> datetime:
        """The moment the state is evaluated for: fixed during a state write."""
        return self._write_now or dt_util.utcnow()

    def _per_write[T](self, key: str, compute: Callable[[], T]) -> T:
        """Compute a value once per state write (every time outside a write)."""
        if self._write_cache is None:
            return compute()
        if key not in self._write_cache:
            self._write_cache[key] = compute()
        return self._write_cache[key]

    @callback
    def _async_write_ha_state(self) -> None:
        # The hook HA provides for customizing a state write; every write path
        # (ticks, new data, registry updates, update_entity) passes here.
        self._write_now = dt_util.utcnow()
        self._write_cache = {}
        try:
            super()._async_write_ha_state()
        finally:
            self._write_now = None
            self._write_cache = None

    async def async_added_to_hass(self) -> None:
        """Also re-evaluate the state every minute."""
        await super().async_added_to_hass()
        self.async_on_remove(async_track_time_interval(self.hass, self._tick, TICK))

    @callback
    def _tick(self, now: datetime) -> None:
        self.async_write_ha_state()
