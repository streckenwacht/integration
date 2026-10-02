"""Data update coordinators: one per provider, shared by all observation areas."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_RADIUS,
    CONF_ROADS,
    DEFAULT_RADIUS,
    DOMAIN,
    FAILURES_BEFORE_ISSUE,
    SOURCE_NAMES,
    UPSTREAM_INRIX,
    Source,
)
from .model import ObservationArea, StreckenwachtEvent
from .providers import Provider, ProviderError

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ProviderData:
    """Result of one poll: all events plus the events per observation area."""

    events: tuple[StreckenwachtEvent, ...] = ()
    # subentry_id -> events inside that area
    by_area: dict[str, tuple[StreckenwachtEvent, ...]] = field(default_factory=dict)


def area_from_subentry(subentry: ConfigSubentry) -> ObservationArea:
    """Build the observation area stored in an "area" subentry."""
    data = subentry.data
    return ObservationArea(
        name=subentry.title,
        latitude=float(data[CONF_LATITUDE]),
        longitude=float(data[CONF_LONGITUDE]),
        radius_km=float(data.get(CONF_RADIUS, DEFAULT_RADIUS)) / 1000,
        roads=frozenset(data.get(CONF_ROADS, ())),
    )


def issue_id(source: Source) -> str:
    """Repair issue id for a failing provider."""
    return f"provider_failed_{source}"


class StreckenwachtCoordinator(DataUpdateCoordinator[ProviderData]):
    """Polls one provider for all observation areas and filters per area.

    Failures never affect other providers. After FAILURES_BEFORE_ISSUE failed
    polls in a row a repair issue is raised; it is removed on the next success.
    The last good data is kept while the provider fails.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        provider: Provider,
        areas: Mapping[str, ObservationArea],
        *,
        scan_interval: timedelta,
        include_inrix: bool,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {provider.source}",
            update_interval=scan_interval,
            always_update=False,
        )
        self.provider = provider
        self.areas = dict(areas)
        self.include_inrix = include_inrix
        self.failures = 0

    @property
    def source(self) -> Source:
        """The data source this coordinator polls."""
        return self.provider.source

    async def _async_update_data(self) -> ProviderData:
        try:
            events = await self.provider.async_fetch(list(self.areas.values()))
        except ProviderError as err:
            self._record_failure(str(err))
            raise UpdateFailed(f"{SOURCE_NAMES[self.source]}: {err}") from err
        except Exception as err:
            # A bug or an unexpected API change must not break anything else.
            _LOGGER.exception("Unexpected error polling %s", self.source)
            self._record_failure(repr(err))
            raise UpdateFailed(f"{SOURCE_NAMES[self.source]}: {err!r}") from err

        if self.failures:
            _LOGGER.info("%s is reachable again", SOURCE_NAMES[self.source])
        self.failures = 0
        ir.async_delete_issue(self.hass, DOMAIN, issue_id(self.source))

        if not self.include_inrix:
            events = [e for e in events if e.upstream != UPSTREAM_INRIX]
        return ProviderData(
            events=tuple(events),
            by_area={
                subentry_id: tuple(e for e in events if area.contains(e))
                for subentry_id, area in self.areas.items()
            },
        )

    def _record_failure(self, error: str) -> None:
        self.failures += 1
        if self.failures < FAILURES_BEFORE_ISSUE:
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id(self.source),
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="provider_failed",
            translation_placeholders={
                "source": SOURCE_NAMES[self.source],
                "failures": str(self.failures),
                "error": error,
            },
        )
