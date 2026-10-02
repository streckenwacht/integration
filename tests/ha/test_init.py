"""Tests for setup, coordinators, repair issues and the INRIX option."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.streckenwacht.const import (
    CONF_INCLUDE_INRIX,
    CONF_RADIUS,
    CONF_ROADS,
    CONF_SCAN_INTERVAL,
    CONF_SOURCES,
    DOMAIN,
    FAILURES_BEFORE_ISSUE,
    SUBENTRY_AREA,
    Source,
)
from custom_components.streckenwacht.model import EventType, StreckenwachtEvent
from custom_components.streckenwacht.providers import ProviderError

INSIDE = StreckenwachtEvent(
    id="autobahn:1",
    source=Source.AUTOBAHN,
    event_type=EventType.ROADWORKS,
    title="A8 | Inside",
    road="A8",
    latitude=48.78,
    longitude=9.18,
)
JAM = StreckenwachtEvent(
    id="autobahn:2",
    source=Source.AUTOBAHN,
    event_type=EventType.TRAFFIC_JAM,
    title="A8 | Stau",
    road="A8",
    latitude=48.79,
    longitude=9.18,
    upstream="inrix",
)
FAR_AWAY = StreckenwachtEvent(
    id="autobahn:3",
    source=Source.AUTOBAHN,
    event_type=EventType.ROADWORKS,
    title="A8 | München",
    road="A8",
    latitude=48.14,
    longitude=11.58,
)
BW_EVENT = StreckenwachtEvent(
    id="mobidata_bw:1",
    source=Source.MOBIDATA_BW,
    event_type=EventType.CLOSURE,
    title="K1077",
    latitude=48.78,
    longitude=9.19,
)

AREA = ConfigSubentryData(
    data={"latitude": 48.78, "longitude": 9.18, CONF_RADIUS: 10000, CONF_ROADS: ["A8"]},
    subentry_type=SUBENTRY_AREA,
    title="Arbeitsweg",
    unique_id=None,
)


def make_entry(**options: object) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Streckenwacht",
        options={
            CONF_SOURCES: ["autobahn", "mobidata_bw"],
            CONF_SCAN_INTERVAL: 15,
            CONF_INCLUDE_INRIX: True,
        }
        | options,
        subentries_data=[AREA],
    )


@pytest.fixture
def autobahn() -> Iterator[AsyncMock]:
    with patch(
        "custom_components.streckenwacht.providers.autobahn.AutobahnProvider.async_fetch",
        return_value=[INSIDE, JAM, FAR_AWAY],
    ) as mock:
        yield mock


@pytest.fixture
def mobidata() -> Iterator[AsyncMock]:
    with patch(
        "custom_components.streckenwacht.providers.mobidata_bw.MobiDataBWProvider.async_fetch",
        return_value=[BW_EVENT],
    ) as mock:
        yield mock


async def setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_filters_per_area(
    hass: HomeAssistant, autobahn: AsyncMock, mobidata: AsyncMock
) -> None:
    entry = make_entry()
    await setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    coordinators = entry.runtime_data.coordinators
    assert set(coordinators) == {Source.AUTOBAHN, Source.MOBIDATA_BW}
    (subentry_id,) = entry.subentries

    autobahn_data = coordinators[Source.AUTOBAHN].data
    assert len(autobahn_data.events) == 3
    assert [e.id for e in autobahn_data.by_area[subentry_id]] == [
        "autobahn:1",
        "autobahn:2",
    ]
    assert [
        e.id for e in coordinators[Source.MOBIDATA_BW].data.by_area[subentry_id]
    ] == ["mobidata_bw:1"]

    # the provider got the area with its motorways
    (areas,) = autobahn.await_args.args
    assert areas[0].roads == frozenset({"A8"})
    assert areas[0].radius_km == 10

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_inrix_can_be_switched_off(
    hass: HomeAssistant, autobahn: AsyncMock, mobidata: AsyncMock
) -> None:
    entry = make_entry(**{CONF_INCLUDE_INRIX: False})
    await setup(hass, entry)
    events = entry.runtime_data.coordinators[Source.AUTOBAHN].data.events
    assert [e.id for e in events] == ["autobahn:1", "autobahn:3"]


async def test_failing_provider_does_not_block_others(
    hass: HomeAssistant, mobidata: AsyncMock
) -> None:
    entry = make_entry()
    with patch(
        "custom_components.streckenwacht.providers.autobahn.AutobahnProvider.async_fetch",
        side_effect=ProviderError("Autobahn down"),
    ):
        await setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    coordinators = entry.runtime_data.coordinators
    assert not coordinators[Source.AUTOBAHN].last_update_success
    assert coordinators[Source.MOBIDATA_BW].last_update_success
    assert len(coordinators[Source.MOBIDATA_BW].data.events) == 1


@pytest.mark.parametrize("error", [ProviderError("down"), RuntimeError("bug")])
async def test_repair_issue_after_repeated_failures(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mobidata: AsyncMock,
    error: Exception,
) -> None:
    entry = make_entry()
    with patch(
        "custom_components.streckenwacht.providers.autobahn.AutobahnProvider.async_fetch",
        side_effect=error,
    ):
        await setup(hass, entry)  # failure 1
        coordinator = entry.runtime_data.coordinators[Source.AUTOBAHN]
        for _ in range(FAILURES_BEFORE_ISSUE - 2):
            await coordinator.async_refresh()
        assert (
            issue_registry.async_get_issue(DOMAIN, "provider_failed_autobahn") is None
        )

        await coordinator.async_refresh()  # failure 3
        issue = issue_registry.async_get_issue(DOMAIN, "provider_failed_autobahn")
        assert issue is not None
        assert issue.translation_key == "provider_failed"
        assert issue.translation_placeholders["source"] == "Autobahn GmbH"

    # recovery removes the issue
    with patch(
        "custom_components.streckenwacht.providers.autobahn.AutobahnProvider.async_fetch",
        return_value=[INSIDE],
    ):
        await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert issue_registry.async_get_issue(DOMAIN, "provider_failed_autobahn") is None


async def test_removing_a_source_clears_its_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    autobahn: AsyncMock,
    mobidata: AsyncMock,
) -> None:
    ir.async_create_issue(
        hass,
        DOMAIN,
        "provider_failed_stuttgart",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="provider_failed",
    )
    await setup(hass, make_entry())  # Stuttgart is not enabled
    assert issue_registry.async_get_issue(DOMAIN, "provider_failed_stuttgart") is None


async def test_options_change_reloads(
    hass: HomeAssistant, autobahn: AsyncMock, mobidata: AsyncMock
) -> None:
    entry = make_entry()
    await setup(hass, entry)
    hass.config_entries.async_update_entry(
        entry, options=dict(entry.options) | {CONF_SOURCES: ["autobahn"]}
    )
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert set(entry.runtime_data.coordinators) == {Source.AUTOBAHN}


async def test_area_without_source_is_not_queried(
    hass: HomeAssistant, autobahn: AsyncMock, mobidata: AsyncMock
) -> None:
    city_only = ConfigSubentryData(
        data=dict(AREA["data"]) | {"sources": ["mobidata_bw"]},
        subentry_type=SUBENTRY_AREA,
        title="Stadt",
        unique_id=None,
    )
    entry = make_entry()
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Streckenwacht",
        options=dict(entry.options),
        subentries_data=[city_only],
    )
    await setup(hass, entry)
    (areas,) = autobahn.await_args.args
    assert areas == []  # the only area does not show motorway events
    (subentry_id,) = entry.subentries
    coordinators = entry.runtime_data.coordinators
    assert coordinators[Source.AUTOBAHN].data.by_area[subentry_id] == ()
    assert len(coordinators[Source.MOBIDATA_BW].data.by_area[subentry_id]) == 1


async def test_area_from_older_beta_keeps_working(
    hass: HomeAssistant, autobahn: AsyncMock, mobidata: AsyncMock
) -> None:
    """Areas created with b1 have no "sources"/"directions" keys: all apply."""
    entry = make_entry()  # AREA has only latitude, longitude, radius, roads
    await setup(hass, entry)
    (subentry_id,) = entry.subentries
    coordinators = entry.runtime_data.coordinators
    assert len(coordinators[Source.AUTOBAHN].data.by_area[subentry_id]) == 2
    assert len(coordinators[Source.MOBIDATA_BW].data.by_area[subentry_id]) == 1
