"""Tests for the diagnostics download."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.streckenwacht.const import (
    CONF_INCLUDE_INRIX,
    CONF_RADIUS,
    CONF_ROADS,
    CONF_SCAN_INTERVAL,
    CONF_SOURCES,
    DOMAIN,
    SUBENTRY_AREA,
    VERSION,
    Source,
)
from custom_components.streckenwacht.model import EventType, StreckenwachtEvent
from custom_components.streckenwacht.providers import ProviderError

EVENT = StreckenwachtEvent(
    id="autobahn:1",
    source=Source.AUTOBAHN,
    event_type=EventType.ROADWORKS,
    title="A8 | Test",
    road="A8",
    latitude=48.78,
    longitude=9.18,
)


async def test_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Streckenwacht",
        options={
            CONF_SOURCES: ["autobahn", "stuttgart"],
            CONF_SCAN_INTERVAL: 15,
            CONF_INCLUDE_INRIX: True,
        },
        subentries_data=[
            ConfigSubentryData(
                data={
                    "latitude": 48.7403,
                    "longitude": 9.1201,
                    CONF_RADIUS: 10000,
                    CONF_ROADS: ["A8"],
                },
                subentry_type=SUBENTRY_AREA,
                title="Zuhause",
                unique_id=None,
            )
        ],
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.streckenwacht.providers.autobahn.AutobahnProvider.async_fetch",
            return_value=[EVENT],
        ),
        patch(
            "custom_components.streckenwacht.providers.stuttgart.StuttgartProvider.async_fetch",
            side_effect=ProviderError("down"),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result["version"] == VERSION
    (area,) = result["areas"].values()
    assert area["title"] == "Zuhause"
    # the home location must never leak into a (public) bug report
    assert area["data"]["latitude"] == "**REDACTED**"
    assert area["data"]["longitude"] == "**REDACTED**"
    assert area["data"][CONF_ROADS] == ["A8"]

    autobahn = result["sources"]["autobahn"]
    assert autobahn["last_update_success"] is True
    assert autobahn["events_total"] == 1
    assert list(autobahn["events_per_area"].values()) == [1]
    assert autobahn["sample_events"][0]["title"] == "A8 | Test"
    assert autobahn["sample_events"][0]["latitude"] == "**REDACTED**"

    stuttgart = result["sources"]["stuttgart"]
    assert stuttgart["last_update_success"] is False
    assert stuttgart["consecutive_failures"] == 1
    assert "down" in stuttgart["last_exception"]
    assert stuttgart["events_total"] is None
