"""Config flow: one entry (sources, options) plus one subentry per observation area."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
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
    """Add or change an observation area: name, circle on a map, motorways."""

    _roads: list[str] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a new observation area."""
        return await self._async_area_step("user", user_input, None)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Change an existing observation area."""
        subentry = self._get_reconfigure_subentry()
        current = {
            CONF_NAME: subentry.title,
            CONF_LOCATION: {
                CONF_LATITUDE: subentry.data[CONF_LATITUDE],
                CONF_LONGITUDE: subentry.data[CONF_LONGITUDE],
                CONF_RADIUS: subentry.data.get(CONF_RADIUS, DEFAULT_RADIUS),
            },
            CONF_ROADS: list(subentry.data.get(CONF_ROADS, [])),
        }
        return await self._async_area_step("reconfigure", user_input, current)

    async def _async_area_step(
        self,
        step_id: str,
        user_input: dict[str, Any] | None,
        current: dict[str, Any] | None,
    ) -> SubentryFlowResult:
        entry = self._get_entry()
        uses_autobahn = Source.AUTOBAHN.value in entry.options.get(CONF_SOURCES, [])
        if uses_autobahn and self._roads is None:
            try:
                self._roads = await AutobahnProvider(
                    async_get_clientsession(self.hass)
                ).async_fetch_roads()
            except ProviderError:
                return self.async_abort(reason="cannot_connect")

        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            location = user_input[CONF_LOCATION]
            radius = float(location.get(CONF_RADIUS) or DEFAULT_RADIUS)
            if not name:
                errors[CONF_NAME] = "name_required"
            elif radius > MAX_RADIUS:
                errors[CONF_LOCATION] = "radius_too_large"
            else:
                data = {
                    CONF_LATITUDE: float(location[CONF_LATITUDE]),
                    CONF_LONGITUDE: float(location[CONF_LONGITUDE]),
                    CONF_RADIUS: radius,
                    CONF_ROADS: sorted(user_input.get(CONF_ROADS, [])),
                }
                if step_id == "reconfigure":
                    return self.async_update_and_abort(
                        entry, self._get_reconfigure_subentry(), title=name, data=data
                    )
                return self.async_create_entry(title=name, data=data)

        defaults = current or {
            CONF_NAME: "",
            CONF_LOCATION: {
                CONF_LATITUDE: self.hass.config.latitude,
                CONF_LONGITUDE: self.hass.config.longitude,
                CONF_RADIUS: DEFAULT_RADIUS,
            },
            CONF_ROADS: [],
        }
        schema: dict[Any, Any] = {
            vol.Required(CONF_NAME): selector.TextSelector(),
            vol.Required(CONF_LOCATION): selector.LocationSelector(
                selector.LocationSelectorConfig(radius=True, icon="mdi:road-variant")
            ),
        }
        if uses_autobahn:
            schema[vol.Optional(CONF_ROADS)] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=self._roads or [],
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    sort=False,
                )
            )
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(schema), user_input or defaults
            ),
            errors=errors,
        )
