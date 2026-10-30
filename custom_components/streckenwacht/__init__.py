"""The Streckenwacht integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_AREA_SOURCES,
    CONF_INCLUDE_INRIX,
    CONF_MERGE_DUPLICATES,
    CONF_SCAN_INTERVAL,
    CONF_SOURCES,
    DEFAULT_INCLUDE_INRIX,
    DEFAULT_MERGE_DUPLICATES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    Source,
)
from .coordinator import (
    StreckenwachtCoordinator,
    area_from_subentry,
    area_subentries,
    issue_id,
)
from .dedup import merge_duplicates
from .frontend_resource import async_register_card, async_unregister_card
from .known_events import KnownEvents
from .model import StreckenwachtEvent
from .providers import Provider
from .providers.autobahn import AutobahnProvider
from .providers.berlin import BerlinProvider
from .providers.brandenburg import BrandenburgProvider
from .providers.cities import (
    FreiburgProvider,
    IngolstadtProvider,
    KarlsruheProvider,
    KielProvider,
    RostockProvider,
)
from .providers.dortmund import DortmundProvider
from .providers.frankfurt import FrankfurtProvider
from .providers.koeln import KoelnProvider
from .providers.lms_bw import LmsBwProvider
from .providers.luxemburg import LuxemburgProvider
from .providers.mobidata_bw import MobiDataBWProvider
from .providers.muenchen import MuenchenProvider
from .providers.norddeutschland import NorddeutschlandProvider
from .providers.nrw import AachenProvider, DuisburgProvider, MuensterProvider
from .providers.rheinland_pfalz import RheinlandPfalzProvider
from .providers.sachsen import SachsenProvider
from .providers.sachsen_anhalt import SachsenAnhaltProvider
from .providers.stuttgart import StuttgartProvider
from .websocket import (
    FRONTEND_DIR,
    FRONTEND_URL,
    async_setup_websocket,
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CALENDAR,
    Platform.EVENT,
    Platform.GEO_LOCATION,
    Platform.SENSOR,
]

PROVIDERS: dict[Source, type[Provider]] = {
    Source.AUTOBAHN: AutobahnProvider,
    Source.MOBIDATA_BW: MobiDataBWProvider,
    Source.STUTTGART: StuttgartProvider,
    Source.NORDDEUTSCHLAND: NorddeutschlandProvider,
    Source.BERLIN: BerlinProvider,
    Source.BRANDENBURG: BrandenburgProvider,
    Source.SACHSEN_ANHALT: SachsenAnhaltProvider,
    Source.SACHSEN: SachsenProvider,
    Source.RHEINLAND_PFALZ: RheinlandPfalzProvider,
    Source.MUENCHEN: MuenchenProvider,
    Source.KOELN: KoelnProvider,
    Source.FRANKFURT: FrankfurtProvider,
    Source.DORTMUND: DortmundProvider,
    Source.AACHEN: AachenProvider,
    Source.DUISBURG: DuisburgProvider,
    Source.MUENSTER: MuensterProvider,
    Source.LUXEMBURG: LuxemburgProvider,
    Source.KARLSRUHE: KarlsruheProvider,
    Source.ROSTOCK: RostockProvider,
    Source.KIEL: KielProvider,
    Source.INGOLSTADT: IngolstadtProvider,
    Source.FREIBURG: FreiburgProvider,
    Source.LMS_BW: LmsBwProvider,
}


@dataclass
class StreckenwachtRuntimeData:
    """Runtime data of a config entry."""

    coordinators: dict[Source, StreckenwachtCoordinator]
    known_events: KnownEvents
    merge_duplicates: bool = DEFAULT_MERGE_DUPLICATES
    area_ids: tuple[str, ...] = ()
    # Per area: the coordinator data the events were built from, and the events.
    _area_events: dict[str, tuple[tuple[object, ...], list[StreckenwachtEvent]]] = (
        field(default_factory=dict, repr=False)
    )

    def area_events(self, subentry_id: str) -> list[StreckenwachtEvent]:
        """All known events of an area from every source, duplicates merged.

        Entities ask every minute; the merge only reruns after new data
        (normally ahead of them, see refresh_area_events).
        """
        token = tuple(c.data for c in self.coordinators.values())
        cached = self._area_events.get(subentry_id)
        if (
            cached is not None
            and len(cached[0]) == len(token)
            and all(a is b for a, b in zip(cached[0], token, strict=True))
        ):
            return cached[1]
        events: list[StreckenwachtEvent] = []
        for data in token:
            if data is not None:
                events.extend(data.by_area.get(subentry_id, ()))
        if self.merge_duplicates:
            events = merge_duplicates(events)
        self._area_events[subentry_id] = (token, events)
        return events

    @callback
    def refresh_area_events(self) -> None:
        """Merge the events of every area after new data, before entities read.

        Keeps the merge out of the entities' state writes: HA times those and
        warns about slow entities (0.4 s).
        """
        for subentry_id in self.area_ids:
            self.area_events(subentry_id)


type StreckenwachtConfigEntry = ConfigEntry[StreckenwachtRuntimeData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the map card and register its WebSocket command (not per entry)."""
    async_setup_websocket(hass)
    if getattr(hass, "http", None) is not None:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(FRONTEND_URL, str(FRONTEND_DIR), cache_headers=True)]
        )
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: StreckenwachtConfigEntry
) -> bool:
    """Set up Streckenwacht from a config entry."""
    session = async_get_clientsession(hass)
    areas = {
        subentry.subentry_id: area_from_subentry(subentry)
        for subentry in area_subentries(entry)
    }
    # Only the sources some area shows are polled.
    used = {s for area in areas.values() for s in (area.sources or {Source.AUTOBAHN})}
    sources = [source for source in Source if source in used]
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
        coordinators=coordinators,
        known_events=known_events,
        merge_duplicates=entry.options.get(
            CONF_MERGE_DUPLICATES, DEFAULT_MERGE_DUPLICATES
        ),
        area_ids=tuple(areas),
    )
    # Registered before the entities' listeners, so it runs first after a poll.
    runtime = entry.runtime_data
    runtime.refresh_area_events()
    for coordinator in coordinators.values():
        entry.async_on_unload(
            coordinator.async_add_listener(runtime.refresh_area_events)
        )
    # Options and subentry (area) changes both trigger a reload.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Here rather than in async_setup: after removing and adding the
    # integration again, async_setup does not run before the next restart.
    if getattr(hass, "http", None) is not None:
        await async_register_card(hass)
    return True


async def async_migrate_entry(
    hass: HomeAssistant, entry: StreckenwachtConfigEntry
) -> bool:
    """Move the entry's source list into the areas (minor version 1 -> 2).

    Up to 0.2.0 the entry held the enabled sources and an area without its own
    list showed all of them. Now every area lists its sources.
    """
    if entry.version > 1:
        return False  # downgrade from a future version
    if entry.minor_version < 2:
        legacy = sorted(entry.options.get(CONF_SOURCES) or [Source.AUTOBAHN.value])
        for subentry in area_subentries(entry):
            if subentry.data.get(CONF_AREA_SOURCES) is None:
                hass.config_entries.async_update_subentry(
                    entry,
                    subentry,
                    data={**subentry.data, CONF_AREA_SOURCES: legacy},
                )
        options = {k: v for k, v in entry.options.items() if k != CONF_SOURCES}
        hass.config_entries.async_update_entry(entry, options=options, minor_version=2)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: StreckenwachtConfigEntry
) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        # Saved at most hourly: write now, the reload reads the file again.
        await entry.runtime_data.known_events.async_flush()
    return unloaded


async def async_remove_entry(
    hass: HomeAssistant, entry: StreckenwachtConfigEntry
) -> None:
    """Remove repair issues, stored data and the card resource."""
    for source in Source:
        ir.async_delete_issue(hass, DOMAIN, issue_id(source))
    await KnownEvents.async_remove(hass, entry.entry_id)
    await async_unregister_card(hass)


async def _async_update_listener(
    hass: HomeAssistant, entry: StreckenwachtConfigEntry
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
