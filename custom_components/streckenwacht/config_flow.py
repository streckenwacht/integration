"""Config flow: one entry (poll interval, INRIX) plus one subentry per observation area.

Data sources are chosen per area; the integration loads what any area uses.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.automation import (
    automations_with_device,
    automations_with_entity,
)
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_AREA_SOURCES,
    CONF_DIRECTIONS,
    CONF_INCLUDE_INRIX,
    CONF_JAM_THRESHOLD,
    CONF_LOCATION,
    CONF_MERGE_DUPLICATES,
    CONF_RADIUS,
    CONF_ROADS,
    CONF_SCAN_INTERVAL,
    CONF_SOURCES,
    CONF_TYPES,
    DEFAULT_INCLUDE_INRIX,
    DEFAULT_JAM_THRESHOLD,
    DEFAULT_MERGE_DUPLICATES,
    DEFAULT_RADIUS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    FAILURES_BEFORE_ISSUE,
    MAX_RADIUS,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    SUBENTRY_AREA,
    Source,
)
from .coordinator import area_subentries
from .model import EventType, ObservationArea, is_route_direction, sources_for_circle
from .overview import Zone, area_overview, entry_overview, place_name
from .providers import ProviderError
from .providers.autobahn import AutobahnProvider


def _setup_schema() -> vol.Schema:
    """Setup asks only for INRIX (a choice about commercial data); the poll
    interval and merging duplicates keep their defaults until changed in the
    options."""
    return vol.Schema(
        {
            vol.Required(
                CONF_INCLUDE_INRIX, default=DEFAULT_INCLUDE_INRIX
            ): selector.BooleanSelector(),
        }
    )


def _options_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_SCAN_INTERVAL, default=defaults[CONF_SCAN_INTERVAL]
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL,
                    max=MAX_SCAN_INTERVAL,
                    step=5,
                    unit_of_measurement="min",
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
            vol.Required(
                CONF_INCLUDE_INRIX, default=defaults[CONF_INCLUDE_INRIX]
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_MERGE_DUPLICATES, default=defaults[CONF_MERGE_DUPLICATES]
            ): selector.BooleanSelector(),
        }
    )


def _clean_options(user_input: dict[str, Any]) -> dict[str, Any]:
    return {
        CONF_SCAN_INTERVAL: int(
            user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        ),
        CONF_INCLUDE_INRIX: bool(
            user_input.get(CONF_INCLUDE_INRIX, DEFAULT_INCLUDE_INRIX)
        ),
        CONF_MERGE_DUPLICATES: bool(
            user_input.get(CONF_MERGE_DUPLICATES, DEFAULT_MERGE_DUPLICATES)
        ),
    }


def _language(hass: HomeAssistant) -> str:
    return "de" if (hass.config.language or "").startswith("de") else "en"


def _runtime(entry: ConfigEntry) -> Any:
    """The entry's runtime data while it is loaded, else None."""
    if entry.state is not ConfigEntryState.LOADED:
        return None
    return getattr(entry, "runtime_data", None)


def _unreachable(runtime: Any) -> set[Source]:
    """Sources failing long enough to have a repair issue."""
    if runtime is None:
        return set()
    return {
        source
        for source, coordinator in runtime.coordinators.items()
        if coordinator.failures >= FAILURES_BEFORE_ISSUE
    }


def _zones(hass: HomeAssistant) -> list[Zone]:
    zones = []
    for state in hass.states.async_all("zone"):
        attrs = state.attributes
        try:
            zones.append(
                Zone(
                    state.name,
                    float(attrs["latitude"]),
                    float(attrs["longitude"]),
                    float(attrs.get("radius") or 0) / 1000,
                )
            )
        except KeyError, TypeError, ValueError:
            continue
    return zones


def _area_automations(
    hass: HomeAssistant, entry: ConfigEntry, subentry_id: str
) -> list[str]:
    """Names of the automations using an entity or the device of an area."""
    found: set[str] = set()
    for entity in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id):
        if entity.config_subentry_id == subentry_id:
            found.update(automations_with_entity(hass, entity.entity_id))
    for device in dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id):
        if subentry_id in device.config_entries_subentries.get(entry.entry_id, ()):
            found.update(automations_with_device(hass, device.id))
    return sorted(
        state.name if (state := hass.states.get(entity_id)) else entity_id
        for entity_id in found
    )


class StreckenwachtConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up the single Streckenwacht entry (manifest: single_config_entry)."""

    VERSION = 1
    # 2: data sources per area instead of one list for the whole entry.
    # 3: removed sources (Köln) dropped from the areas.
    MINOR_VERSION = 3

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Only INRIX; sources are chosen per observation area."""
        if user_input is not None:
            return self.async_create_entry(
                title="Streckenwacht", data={}, options=_clean_options(user_input)
            )
        return self.async_show_form(step_id="user", data_schema=_setup_schema())

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Options: poll interval, INRIX data."""
        return StreckenwachtOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Observation areas are subentries."""
        return {SUBENTRY_AREA: AreaSubentryFlow}


class StreckenwachtOptionsFlow(OptionsFlow):
    """Change poll interval and INRIX data (the entry reloads)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options form."""
        if user_input is not None:
            return self.async_create_entry(data=_clean_options(user_input))

        current = self.config_entry.options
        defaults = {
            CONF_SCAN_INTERVAL: current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            CONF_INCLUDE_INRIX: current.get(CONF_INCLUDE_INRIX, DEFAULT_INCLUDE_INRIX),
            CONF_MERGE_DUPLICATES: current.get(
                CONF_MERGE_DUPLICATES, DEFAULT_MERGE_DUPLICATES
            ),
        }
        entry = self.config_entry
        runtime = _runtime(entry)
        overview = entry_overview(
            [
                (
                    subentry.title,
                    subentry.data,
                    len(runtime.area_events(subentry.subentry_id))
                    if runtime is not None
                    else None,
                )
                for subentry in area_subentries(entry)
            ],
            language=_language(self.hass),
            unreachable=_unreachable(runtime),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(defaults),
            description_placeholders={"overview": overview},
        )


class AreaSubentryFlow(ConfigSubentryFlow):
    """Add or change an observation area, as a short wizard.

    1. name and circle on a map
    2. data sources - those whose region the circle touches; skipped if only
       the Autobahn is available
    3. motorways   - only if the Autobahn source is used
    4. directions  - only if motorways were selected
    HA forms cannot hide fields depending on other fields, hence the steps.
    """

    _title: str = ""
    _data: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a new observation area."""
        return await self._async_area_step("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Change an existing observation area."""
        return await self._async_area_step("reconfigure", user_input)

    def _inrix(self) -> bool:
        """Traffic jams (and their threshold) only exist with INRIX data."""
        return bool(
            self._get_entry().options.get(CONF_INCLUDE_INRIX, DEFAULT_INCLUDE_INRIX)
        )

    def _stored(self, key: str, default: Any) -> Any:
        """Value of the subentry being reconfigured, else the default."""
        if self.source == SOURCE_RECONFIGURE:
            return self._get_reconfigure_subentry().data.get(key, default)
        return default

    async def _async_area_step(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            location = user_input[CONF_LOCATION]
            radius = float(location.get(CONF_RADIUS) or DEFAULT_RADIUS)
            types = sorted(user_input.get(CONF_TYPES, []))
            if not name:
                errors[CONF_NAME] = "name_required"
            elif radius > MAX_RADIUS:
                errors[CONF_LOCATION] = "radius_too_large"
            elif not types:
                errors[CONF_TYPES] = "no_types"
            else:
                self._title = name
                self._data = {
                    CONF_LATITUDE: float(location[CONF_LATITUDE]),
                    CONF_LONGITUDE: float(location[CONF_LONGITUDE]),
                    CONF_RADIUS: radius,
                    CONF_AREA_SOURCES: [],
                    CONF_ROADS: [],
                    CONF_DIRECTIONS: [],
                    # None: all kinds, including ones added in later versions
                    CONF_TYPES: None if len(types) == len(EventType) else types,
                }
                return await self.async_step_sources()

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): selector.TextSelector(),
                vol.Required(CONF_LOCATION): selector.LocationSelector(
                    selector.LocationSelectorConfig(
                        radius=True, icon="mdi:road-variant"
                    )
                ),
                vol.Required(CONF_TYPES): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[t.value for t in EventType],
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                        translation_key=CONF_TYPES,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input or self._area_defaults()
            ),
            errors=errors,
            description_placeholders=(
                {"overview": self._overview()}
                if self.source == SOURCE_RECONFIGURE
                else None
            ),
        )

    def _overview(self) -> str:
        """What the area being changed is set up with (as stored)."""
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        data = subentry.data
        runtime = _runtime(entry)
        return area_overview(
            data,
            language=_language(self.hass),
            include_inrix=self._inrix(),
            place=place_name(
                float(data[CONF_LATITUDE]),
                float(data[CONF_LONGITUDE]),
                _zones(self.hass),
            ),
            events=(
                len(runtime.area_events(subentry.subentry_id))
                if runtime is not None
                else None
            ),
            automations=_area_automations(self.hass, entry, subentry.subentry_id),
            unreachable=_unreachable(runtime),
        )

    def _area_defaults(self) -> dict[str, Any]:
        if self.source == SOURCE_RECONFIGURE:
            subentry = self._get_reconfigure_subentry()
            data = subentry.data
            return {
                CONF_NAME: subentry.title,
                CONF_LOCATION: {
                    CONF_LATITUDE: data[CONF_LATITUDE],
                    CONF_LONGITUDE: data[CONF_LONGITUDE],
                    CONF_RADIUS: data.get(CONF_RADIUS, DEFAULT_RADIUS),
                },
                CONF_TYPES: data.get(CONF_TYPES) or [t.value for t in EventType],
            }
        return {
            CONF_NAME: "",
            CONF_LOCATION: {
                CONF_LATITUDE: self.hass.config.latitude,
                CONF_LONGITUDE: self.hass.config.longitude,
                CONF_RADIUS: DEFAULT_RADIUS,
            },
            CONF_TYPES: [t.value for t in EventType],
        }

    async def async_step_sources(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Choose among the sources covering the circle (all preselected)."""
        assert self._data is not None
        available = {
            source.value
            for source in sources_for_circle(
                self._data[CONF_LATITUDE],
                self._data[CONF_LONGITUDE],
                self._data[CONF_RADIUS] / 1000,
            )
        }
        stored = list(self._stored(CONF_AREA_SOURCES, None) or [])
        # Sources stored earlier stay selectable, so they can be deselected.
        offered = [s.value for s in Source if s.value in available or s.value in stored]
        errors: dict[str, str] = {}
        if user_input is None and len(offered) == 1:
            user_input = {CONF_AREA_SOURCES: offered}  # nothing to choose
        if user_input is not None:
            sources = sorted(user_input.get(CONF_AREA_SOURCES, []))
            if sources:
                self._data[CONF_AREA_SOURCES] = sources
                if Source.AUTOBAHN.value in sources:
                    return await self.async_step_roads()
                return self._async_finish()
            errors[CONF_AREA_SOURCES] = "no_sources"

        default = [s for s in offered if s in stored] if stored else offered
        schema = vol.Schema(
            {
                vol.Required(CONF_AREA_SOURCES): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=offered,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                        translation_key=CONF_SOURCES,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="sources",
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input or {CONF_AREA_SOURCES: default}
            ),
            errors=errors,
        )

    async def async_step_roads(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Choose the motorways (the Autobahn API cannot search by area)."""
        assert self._data is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            roads = sorted(user_input.get(CONF_ROADS, []))
            if roads:
                self._data[CONF_ROADS] = roads
                # An emptied field falls back to the default; without INRIX
                # the field is hidden and the stored value stays.
                fallback = (
                    DEFAULT_JAM_THRESHOLD
                    if self._inrix()
                    else self._stored(CONF_JAM_THRESHOLD, DEFAULT_JAM_THRESHOLD)
                )
                self._data[CONF_JAM_THRESHOLD] = int(
                    user_input.get(CONF_JAM_THRESHOLD, fallback)
                )
                return await self.async_step_directions()
            errors[CONF_ROADS] = "no_roads"

        try:
            roads_available = await AutobahnProvider(
                async_get_clientsession(self.hass)
            ).async_fetch_roads()
        except ProviderError:
            return self.async_abort(reason="cannot_connect")
        fields: dict[Any, Any] = {
            vol.Required(CONF_ROADS): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=roads_available,
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    sort=False,
                )
            )
        }
        if self._inrix():
            # Optional: an emptied field falls back to the default.
            fields[vol.Optional(CONF_JAM_THRESHOLD)] = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=60,
                    step=1,
                    unit_of_measurement="min",
                    mode=selector.NumberSelectorMode.BOX,
                )
            )
        defaults = {
            CONF_ROADS: list(self._stored(CONF_ROADS, [])),
            CONF_JAM_THRESHOLD: self._stored(CONF_JAM_THRESHOLD, DEFAULT_JAM_THRESHOLD),
        }
        return self.async_show_form(
            step_id="roads",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(fields), user_input or defaults
            ),
            errors=errors,
        )

    async def async_step_directions(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Choose the directions of travel; none selected means all."""
        assert self._data is not None
        if user_input is not None:
            self._data[CONF_DIRECTIONS] = sorted(user_input.get(CONF_DIRECTIONS, []))
            return self._async_finish()

        current = list(self._stored(CONF_DIRECTIONS, []))
        try:
            options = await self._async_route_directions(self._data[CONF_ROADS])
        except ProviderError:
            return self.async_abort(reason="cannot_connect")
        schema = vol.Schema(
            {
                vol.Optional(CONF_DIRECTIONS): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=sorted(set(options) | set(current)),
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="directions",
            data_schema=self.add_suggested_values_to_schema(
                schema, {CONF_DIRECTIONS: current}
            ),
        )

    async def _async_route_directions(self, roads: list[str]) -> list[str]:
        """Directions ("Singen -> Stuttgart") currently used on these roads."""
        provider = AutobahnProvider(async_get_clientsession(self.hass))
        events = await provider.async_fetch(
            [ObservationArea("", 0, 0, 0, roads=frozenset(roads))]
        )
        return sorted(
            {
                event.direction
                for event in events
                if event.direction and is_route_direction(event.direction)
            }
        )

    def _async_finish(self) -> SubentryFlowResult:
        assert self._data is not None
        if self.source == SOURCE_RECONFIGURE:
            return self.async_update_and_abort(
                self._get_entry(),
                self._get_reconfigure_subentry(),
                title=self._title,
                data=self._data,
            )
        return self.async_create_entry(title=self._title, data=self._data)
