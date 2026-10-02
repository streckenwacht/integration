"""Tests for the entities of an observation area."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import EVENT_STATE_CHANGED, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
)

from custom_components.streckenwacht.const import (
    CONF_INCLUDE_INRIX,
    CONF_RADIUS,
    CONF_ROADS,
    CONF_SCAN_INTERVAL,
    CONF_SOURCES,
    DOMAIN,
    SUBENTRY_AREA,
    Source,
)
from custom_components.streckenwacht.model import EventType, Period, StreckenwachtEvent
from custom_components.streckenwacht.providers import ProviderError

NOW = dt_util.parse_datetime("2026-10-05T12:00:00+00:00")
H = timedelta(hours=1)
PREFIX = "streckenwacht_arbeitsweg"
FETCH = (
    "custom_components.streckenwacht.providers.autobahn.AutobahnProvider.async_fetch"
)


def ev(id_: str, event_type: EventType, period: Period, **kwargs) -> StreckenwachtEvent:
    return StreckenwachtEvent(
        id=f"autobahn:{id_}",
        source=Source.AUTOBAHN,
        event_type=event_type,
        title=kwargs.pop("title", id_),
        road="A8",
        latitude=48.78,
        longitude=9.18,
        periods=(period,),
        **kwargs,
    )


ROADWORKS = ev("roadworks", EventType.ROADWORKS, Period(NOW - 1000 * H, NOW + 1000 * H))
CLOSURE = ev("closure", EventType.CLOSURE, Period(NOW - H, NOW + 5 * H))
JAM = ev(
    "jam", EventType.TRAFFIC_JAM, Period(NOW - H), delay_minutes=25, upstream="inrix"
)
PLANNED = ev("planned", EventType.CLOSURE, Period(NOW + 10 * H, NOW + 12 * H))
EVENTS = [ROADWORKS, CLOSURE, JAM, PLANNED]


def make_entry(**options: object) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Streckenwacht",
        options={
            CONF_SOURCES: ["autobahn"],
            CONF_SCAN_INTERVAL: 15,
            CONF_INCLUDE_INRIX: True,
        }
        | options,
        subentries_data=[
            ConfigSubentryData(
                data={
                    "latitude": 48.78,
                    "longitude": 9.18,
                    CONF_RADIUS: 10000,
                    CONF_ROADS: ["A8"],
                },
                subentry_type=SUBENTRY_AREA,
                title="Arbeitsweg",
                unique_id=None,
            )
        ],
    )


@pytest.fixture(autouse=True)
def frozen_time(freezer: FrozenDateTimeFactory) -> FrozenDateTimeFactory:
    freezer.move_to(NOW)
    return freezer


@pytest.fixture
def fetch() -> Iterator[AsyncMock]:
    with patch(FETCH, return_value=list(EVENTS)) as mock:
        yield mock


async def setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_entities_and_device(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, fetch: AsyncMock
) -> None:
    entry = make_entry()
    await setup(hass, entry)

    disruption = hass.states.get(f"binary_sensor.{PREFIX}_disruption_active")
    assert disruption.state == STATE_ON
    assert disruption.attributes["count"] == 2  # closure + jam, not roadworks
    assert [d["id"] for d in disruption.attributes["disruptions"]] == [
        "autobahn:closure",
        "autobahn:jam",
    ]
    assert "INRIX" in disruption.attributes["attribution"]

    events = hass.states.get(f"sensor.{PREFIX}_events")
    assert events.state == "3"  # planned closure not yet active
    assert events.attributes["roadworks"] == 1
    assert events.attributes["unavailable_sources"] == []

    assert hass.states.get(f"sensor.{PREFIX}_travel_time_loss").state == "25"
    assert hass.states.get(f"calendar.{PREFIX}").state == STATE_ON
    assert hass.states.get(f"event.{PREFIX}_event_change") is not None

    (subentry_id,) = entry.subentries
    device = device_registry.async_get_device(identifiers={(DOMAIN, subentry_id)})
    assert device.name == "Streckenwacht Arbeitsweg"


async def test_state_follows_the_clock(
    hass: HomeAssistant, fetch: AsyncMock, frozen_time: FrozenDateTimeFactory
) -> None:
    fetch.return_value = [CLOSURE]
    await setup(hass, make_entry())
    entity_id = f"binary_sensor.{PREFIX}_disruption_active"
    assert hass.states.get(entity_id).state == STATE_ON

    frozen_time.tick(6 * H)  # closure ended, no new data needed
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "off"


async def test_calendar_events(hass: HomeAssistant, fetch: AsyncMock) -> None:
    await setup(hass, make_entry())
    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {"entity_id": f"calendar.{PREFIX}", "duration": {"hours": 24}},
        blocking=True,
        return_response=True,
    )
    summaries = [e["summary"] for e in response[f"calendar.{PREFIX}"]["events"]]
    assert sorted(summaries) == ["closure", "jam", "planned", "roadworks"]


async def test_no_travel_time_sensor_without_inrix(
    hass: HomeAssistant, fetch: AsyncMock
) -> None:
    await setup(hass, make_entry(**{CONF_INCLUDE_INRIX: False}))
    assert hass.states.get(f"sensor.{PREFIX}_travel_time_loss") is None
    assert hass.states.get(f"sensor.{PREFIX}_events") is not None


async def test_entities_keep_last_data_when_source_fails(
    hass: HomeAssistant, fetch: AsyncMock
) -> None:
    entry = make_entry()
    await setup(hass, entry)
    coordinator = entry.runtime_data.coordinators[Source.AUTOBAHN]

    fetch.side_effect = ProviderError("down")
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.{PREFIX}_events")
    assert state.state == "3"
    assert state.attributes["unavailable_sources"] == ["Autobahn GmbH"]


async def test_change_events(hass: HomeAssistant, fetch: AsyncMock) -> None:
    entry = make_entry()
    entity_id = f"event.{PREFIX}_event_change"
    changes = async_capture_events(hass, EVENT_STATE_CHANGED)
    await setup(hass, entry)

    def fired() -> list[tuple[str, str]]:
        return [
            (
                c.data["new_state"].attributes["event_type"],
                c.data["new_state"].attributes["id"],
            )
            for c in changes
            if c.data["entity_id"] == entity_id
            and c.data["new_state"].attributes.get("event_type")
        ]

    assert fired() == []  # first data is learned silently

    new = ev("accident", EventType.ACCIDENT, Period(NOW), title="Unfall")
    fetch.return_value = [ROADWORKS, CLOSURE, PLANNED, new]  # jam gone, accident new
    await entry.runtime_data.coordinators[Source.AUTOBAHN].async_refresh()
    await hass.async_block_till_done()

    assert fired() == [("new", "autobahn:accident"), ("ended", "autobahn:jam")]
    state = hass.states.get(entity_id)
    assert state.attributes["title"] == "jam"  # "ended" carries the known title


async def test_failure_does_not_fire_ended(
    hass: HomeAssistant, fetch: AsyncMock
) -> None:
    entry = make_entry()
    entity_id = f"event.{PREFIX}_event_change"
    await setup(hass, entry)
    changes = async_capture_events(hass, EVENT_STATE_CHANGED)

    fetch.side_effect = ProviderError("down")
    await entry.runtime_data.coordinators[Source.AUTOBAHN].async_refresh()
    await hass.async_block_till_done()
    assert not [c for c in changes if c.data["entity_id"] == entity_id]


async def test_known_events_survive_reload(
    hass: HomeAssistant, fetch: AsyncMock, frozen_time: FrozenDateTimeFactory
) -> None:
    entry = make_entry()
    entity_id = f"event.{PREFIX}_event_change"
    await setup(hass, entry)
    frozen_time.tick(timedelta(seconds=15))  # let the delayed save run
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    changes = async_capture_events(hass, EVENT_STATE_CHANGED)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert not [
        c
        for c in changes
        if c.data["entity_id"] == entity_id
        and c.data["new_state"] is not None
        and c.data["new_state"].attributes.get("event_type")
        and c.data["old_state"] is not None
        and c.data["new_state"].state != c.data["old_state"].state
    ]
