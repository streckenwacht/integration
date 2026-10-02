"""Config flow: one entry (sources, options) plus one subentry per observation area."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    BW_BOUNDS,
    CONF_AREA_SOURCES,
    CONF_DIRECTIONS,
    CONF_INCLUDE_INRIX,
    CONF_LOCATION,
    CONF_RADIUS,
    CONF_ROADS,
    CONF_SCAN_INTERVAL,
    CONF_SOURCES,
    DEFAULT_INCLUDE_INRIX,
    DEFAULT_RADIUS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_RADIUS,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    SUBENTRY_AREA,
    Source,
)
from .model import ObservationArea, is_route_direction
from .providers import ProviderError
from .providers.autobahn import AutobahnProvider


def _options_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_SOURCES, default=defaults[CONF_SOURCES]): (
                selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[s.value for s in Source],
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                        translation_key=CONF_SOURCES,
                    )
                )
            ),
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
        }
    )


def _clean_options(user_input: dict[str, Any]) -> dict[str, Any]:
    return {
        CONF_SOURCES: list(user_input[CONF_SOURCES]),
        CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
        CONF_INCLUDE_INRIX: bool(user_input[CONF_INCLUDE_INRIX]),
    }


class StreckenwachtConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up the single Streckenwacht entry (manifest: single_config_entry)."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the data sources."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input[CONF_SOURCES]:
                errors["base"] = "no_sources"
            else:
                return self.async_create_entry(
                    title="Streckenwacht", data={}, options=_clean_options(user_input)
                )

        defaults = {
            CONF_SOURCES: self._default_sources(),
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_INCLUDE_INRIX: DEFAULT_INCLUDE_INRIX,
        }
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                _options_schema(defaults), user_input
            ),
            errors=errors,
        )

    def _default_sources(self) -> list[str]:
        """All sources if home is in Baden-Württemberg, else only the Autobahn."""
        lat, lon = self.hass.config.latitude, self.hass.config.longitude
        in_bw = (
            BW_BOUNDS["lat"][0] <= lat <= BW_BOUNDS["lat"][1]
            and BW_BOUNDS["lon"][0] <= lon <= BW_BOUNDS["lon"][1]
        )
        return [s.value for s in Source] if in_bw else [Source.AUTOBAHN.value]

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Options: sources, poll interval, INRIX data."""
        return StreckenwachtOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Observation areas are subentries."""
        return {SUBENTRY_AREA: AreaSubentryFlow}


class StreckenwachtOptionsFlow(OptionsFlow):
    """Change sources, poll interval and INRIX data (the entry reloads)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options form."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input[CONF_SOURCES]:
                errors["base"] = "no_sources"
            else:
                return self.async_create_entry(data=_clean_options(user_input))

        current = self.config_entry.options
        defaults = {
            CONF_SOURCES: current.get(CONF_SOURCES, [Source.AUTOBAHN.value]),
            CONF_SCAN_INTERVAL: current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            CONF_INCLUDE_INRIX: current.get(CONF_INCLUDE_INRIX, DEFAULT_INCLUDE_INRIX),
        }
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                _options_schema(defaults), user_input
            ),
            errors=errors,
        )


class AreaSubentryFlow(ConfigSubentryFlow):
    """Add or change an observation area, as a short wizard.

    1. name, circle on a map, data sources
    2. motorways   - only if the Autobahn source is used
    3. directions  - only if motorways were selected
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

    def _enabled_sources(self) -> list[Source]:
        enabled = self._get_entry().options.get(CONF_SOURCES, [])
        return [source for source in Source if source.value in enabled]

    def _stored(self, key: str, default: Any) -> Any:
        """Value of the subentry being reconfigured, else the default."""
        if self.source == SOURCE_RECONFIGURE:
            return self._get_reconfigure_subentry().data.get(key, default)
        return default

    async def _async_area_step(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> SubentryFlowResult:
        enabled = self._enabled_sources()
        choose_sources = len(enabled) > 1
        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            location = user_input[CONF_LOCATION]
            radius = float(location.get(CONF_RADIUS) or DEFAULT_RADIUS)
            sources = user_input.get(CONF_AREA_SOURCES) if choose_sources else None
            if not name:
                errors[CONF_NAME] = "name_required"
            elif radius > MAX_RADIUS:
                errors[CONF_LOCATION] = "radius_too_large"
            elif choose_sources and not sources:
                errors[CONF_AREA_SOURCES] = "no_sources"
            else:
                self._title = name
                self._data = {
                    CONF_LATITUDE: float(location[CONF_LATITUDE]),
                    CONF_LONGITUDE: float(location[CONF_LONGITUDE]),
                    CONF_RADIUS: radius,
                    # None: all sources configured for the integration
                    CONF_AREA_SOURCES: sorted(sources) if sources else None,
                    CONF_ROADS: [],
                    CONF_DIRECTIONS: [],
                }
                shown = sources if sources else [s.value for s in enabled]
                if Source.AUTOBAHN.value in shown:
                    return await self.async_step_roads()
                return self._async_finish()

        schema: dict[Any, Any] = {
            vol.Required(CONF_NAME): selector.TextSelector(),
            vol.Required(CONF_LOCATION): selector.LocationSelector(
                selector.LocationSelectorConfig(radius=True, icon="mdi:road-variant")
            ),
        }
        if choose_sources:
            schema[vol.Required(CONF_AREA_SOURCES)] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[source.value for source in enabled],
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                    translation_key=CONF_SOURCES,
                )
            )
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(schema), user_input or self._area_defaults(enabled)
            ),
            errors=errors,
        )

    def _area_defaults(self, enabled: list[Source]) -> dict[str, Any]:
        all_enabled = [source.value for source in enabled]
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
                CONF_AREA_SOURCES: data.get(CONF_AREA_SOURCES) or all_enabled,
            }
        return {
            CONF_NAME: "",
            CONF_LOCATION: {
                CONF_LATITUDE: self.hass.config.latitude,
                CONF_LONGITUDE: self.hass.config.longitude,
                CONF_RADIUS: DEFAULT_RADIUS,
            },
            CONF_AREA_SOURCES: all_enabled,
        }

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
                return await self.async_step_directions()
            errors[CONF_ROADS] = "no_roads"

        try:
            roads_available = await AutobahnProvider(
                async_get_clientsession(self.hass)
            ).async_fetch_roads()
        except ProviderError:
            return self.async_abort(reason="cannot_connect")
        schema = vol.Schema(
            {
                vol.Required(CONF_ROADS): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=roads_available,
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        sort=False,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="roads",
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input or {CONF_ROADS: list(self._stored(CONF_ROADS, []))}
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
