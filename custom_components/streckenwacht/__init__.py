"""The Streckenwacht integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_INCLUDE_INRIX,
    CONF_SCAN_INTERVAL,
    CONF_SOURCES,
    DEFAULT_INCLUDE_INRIX,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SUBENTRY_AREA,
    Source,
)
from .coordinator import StreckenwachtCoordinator, area_from_subentry, issue_id
from .known_events import KnownEvents
from .providers import Provider
from .providers.autobahn import AutobahnProvider
from .providers.mobidata_bw import MobiDataBWProvider
from .providers.stuttgart import StuttgartProvider

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CALENDAR,
    Platform.EVENT,
    Platform.SENSOR,
]

PROVIDERS: dict[Source, type[Provider]] = {
    Source.AUTOBAHN: AutobahnProvider,
    Source.MOBIDATA_BW: MobiDataBWProvider,
    Source.STUTTGART: StuttgartProvider,
}


@dataclass
class StreckenwachtRuntimeData:
    """Runtime data of a config entry."""

    coordinators: dict[Source, StreckenwachtCoordinator]
    known_events: KnownEvents


type StreckenwachtConfigEntry = ConfigEntry[StreckenwachtRuntimeData]


async def async_setup_entry(
    hass: HomeAssistant, entry: StreckenwachtConfigEntry
) -> bool:
    """Set up Streckenwacht from a config entry."""
    session = async_get_clientsession(hass)
    sources = [Source(s) for s in entry.options.get(CONF_SOURCES, [])]
    areas = {
        subentry.subentry_id: area_from_subentry(subentry)
        for subentry in entry.get_subentries_of_type(SUBENTRY_AREA)
    }
    scan_interval = timedelta(
        minutes=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )
    coordinators = {
        source: StreckenwachtCoordinator(
            hass,
            entry,
            PROVIDERS[source](session),
            areas,
            scan_interval=scan_interval,
            include_inrix=entry.options.get(CONF_INCLUDE_INRIX, DEFAULT_INCLUDE_INRIX),
        )
        for source in sources
    }

    # Issues of sources that were switched off are obsolete.
    for source in Source:
        if source not in coordinators:
            ir.async_delete_issue(hass, DOMAIN, issue_id(source))

    # Deliberately not async_config_entry_first_refresh(): one unreachable source
    # must not keep the whole integration (and the other sources) from loading.
    await asyncio.gather(*(c.async_refresh() for c in coordinators.values()))

    known_events = KnownEvents(hass, entry.entry_id)
    await known_events.async_load(keep=areas)

    entry.runtime_data = StreckenwachtRuntimeData(
        coordinators=coordinators, known_events=known_events
    )
    # Options and subentry (area) changes both trigger a reload.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: StreckenwachtConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(
    hass: HomeAssistant, entry: StreckenwachtConfigEntry
) -> None:
    """Remove repair issues and stored data when the integration is deleted."""
    for source in Source:
        ir.async_delete_issue(hass, DOMAIN, issue_id(source))
    await KnownEvents.async_remove(hass, entry.entry_id)


async def _async_update_listener(
    hass: HomeAssistant, entry: StreckenwachtConfigEntry
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
