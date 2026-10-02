"""Tests for the config, options and observation area flows."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigSubentryData,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.streckenwacht.const import (
    CONF_AREA_SOURCES,
    CONF_DIRECTIONS,
    CONF_INCLUDE_INRIX,
    CONF_LOCATION,
    CONF_RADIUS,
    CONF_ROADS,
    CONF_SCAN_INTERVAL,
    CONF_SOURCES,
    DOMAIN,
    SUBENTRY_AREA,
    Source,
)
from custom_components.streckenwacht.model import EventType, StreckenwachtEvent
from custom_components.streckenwacht.providers import ProviderError

ROADS = ["A1", "A8", "A81"]
OPTIONS = {
    CONF_SOURCES: ["autobahn", "mobidata_bw"],
    CONF_SCAN_INTERVAL: 15,
    CONF_INCLUDE_INRIX: True,
}
AREA_INPUT = {
    "name": "Arbeitsweg",
    CONF_LOCATION: {"latitude": 48.78, "longitude": 9.18, CONF_RADIUS: 15000},
    CONF_AREA_SOURCES: ["autobahn", "mobidata_bw"],
    CONF_ROADS: ["A81", "A8"],
}


@pytest.fixture(autouse=True)
def no_setup() -> Iterator[AsyncMock]:
    """Flows are tested without actually setting up the entry."""
    with patch(
        "custom_components.streckenwacht.async_setup_entry", return_value=True
    ) as mock:
        yield mock


@pytest.fixture
def roads() -> Iterator[AsyncMock]:
    with patch(
        "custom_components.streckenwacht.config_flow.AutobahnProvider.async_fetch_roads",
        return_value=ROADS,
    ) as mock:
        yield mock


def entry_with(options: dict, subentries: list | None = None) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Streckenwacht",
        options=options,
        subentries_data=subentries or [],
    )


# --- Main entry --------------------------------------------------------------


async def test_user_flow_in_bw_preselects_all_sources(hass: HomeAssistant) -> None:
    hass.config.latitude, hass.config.longitude = 48.78, 9.18  # Stuttgart
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    schema = result["data_schema"].schema
    default = next(k for k in schema if k == CONF_SOURCES).default()
    assert default == ["autobahn", "mobidata_bw", "stuttgart"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SOURCES: ["autobahn"],
            CONF_SCAN_INTERVAL: 20.0,
            CONF_INCLUDE_INRIX: False,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Streckenwacht"
    assert result["options"] == {
        CONF_SOURCES: ["autobahn"],
        CONF_SCAN_INTERVAL: 20,
        CONF_INCLUDE_INRIX: False,
    }


async def test_user_flow_outside_bw_preselects_autobahn(hass: HomeAssistant) -> None:
    hass.config.latitude, hass.config.longitude = 52.52, 13.40  # Berlin
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    schema = result["data_schema"].schema
    assert next(k for k in schema if k == CONF_SOURCES).default() == ["autobahn"]


async def test_user_flow_requires_a_source(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SOURCES: [], CONF_SCAN_INTERVAL: 15, CONF_INCLUDE_INRIX: True},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_sources"}


async def test_single_instance(hass: HomeAssistant) -> None:
    entry_with(OPTIONS).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow(hass: HomeAssistant) -> None:
    entry = entry_with(OPTIONS)
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_SOURCES: [], CONF_SCAN_INTERVAL: 30, CONF_INCLUDE_INRIX: True},
    )
    assert result["errors"] == {"base": "no_sources"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SOURCES: ["stuttgart"],
            CONF_SCAN_INTERVAL: 30,
            CONF_INCLUDE_INRIX: False,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        CONF_SOURCES: ["stuttgart"],
        CONF_SCAN_INTERVAL: 30,
        CONF_INCLUDE_INRIX: False,
    }


# --- Observation areas -------------------------------------------------------

DIRECTION_EVENTS = [
    StreckenwachtEvent(
        id=f"autobahn:{i}",
        source=Source.AUTOBAHN,
        event_type=EventType.ROADWORKS,
        title="x",
        road="A81",
        direction=direction,
    )
    for i, direction in enumerate(
        [
            "Singen -> Stuttgart",
            "Stuttgart -> Singen",
            "Singen -> Stuttgart",
            "AS Böblingen-Hulb (aus Richtung Ehningen)",
            None,
        ]
    )
]


@pytest.fixture
def directions() -> Iterator[AsyncMock]:
    with patch(
        "custom_components.streckenwacht.config_flow.AutobahnProvider.async_fetch",
        return_value=DIRECTION_EVENTS,
    ) as mock:
        yield mock


async def start_area_flow(hass: HomeAssistant, entry: MockConfigEntry) -> dict:
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_AREA), context={"source": SOURCE_USER}
    )


async def test_add_area_with_directions(
    hass: HomeAssistant, roads: AsyncMock, directions: AsyncMock
) -> None:
    entry = entry_with(OPTIONS)
    entry.add_to_hass(hass)
    result = await start_area_flow(hass, entry)
    assert result["type"] is FlowResultType.FORM
    schema = result["data_schema"].schema
    assert CONF_ROADS in schema
    assert CONF_AREA_SOURCES in schema  # two sources configured

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], AREA_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "directions"
    # only real carriageway directions are offered, sorted and deduplicated
    (key,) = result["data_schema"].schema
    options = result["data_schema"].schema[key].config["options"]
    assert options == ["Singen -> Stuttgart", "Stuttgart -> Singen"]
    (areas,) = directions.await_args.args
    assert areas[0].roads == frozenset({"A8", "A81"})

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_DIRECTIONS: ["Singen -> Stuttgart"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    (subentry,) = entry.subentries.values()
    assert subentry.title == "Arbeitsweg"
    assert dict(subentry.data) == {
        "latitude": 48.78,
        "longitude": 9.18,
        CONF_RADIUS: 15000.0,
        CONF_ROADS: ["A8", "A81"],
        CONF_AREA_SOURCES: ["autobahn", "mobidata_bw"],
        CONF_DIRECTIONS: ["Singen -> Stuttgart"],
    }
    roads.assert_awaited_once()


async def test_area_without_motorway_source_skips_directions(
    hass: HomeAssistant, roads: AsyncMock, directions: AsyncMock
) -> None:
    entry = entry_with(OPTIONS)
    entry.add_to_hass(hass)
    result = await start_area_flow(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], AREA_INPUT | {CONF_AREA_SOURCES: ["mobidata_bw"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    (subentry,) = entry.subentries.values()
    assert subentry.data[CONF_AREA_SOURCES] == ["mobidata_bw"]
    assert subentry.data[CONF_DIRECTIONS] == []
    directions.assert_not_awaited()


async def test_area_with_single_source(hass: HomeAssistant, roads: AsyncMock) -> None:
    entry = entry_with(OPTIONS | {CONF_SOURCES: ["stuttgart"]})
    entry.add_to_hass(hass)
    result = await start_area_flow(hass, entry)
    schema = result["data_schema"].schema
    assert CONF_ROADS not in schema
    assert CONF_AREA_SOURCES not in schema  # nothing to choose
    roads.assert_not_awaited()

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"name": "Stadt", CONF_LOCATION: AREA_INPUT[CONF_LOCATION]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    (subentry,) = entry.subentries.values()
    assert subentry.data[CONF_AREA_SOURCES] is None  # all configured sources


@pytest.mark.parametrize(
    ("changes", "errors"),
    [
        ({"name": "   "}, {"name": "name_required"}),
        (
            {
                CONF_LOCATION: {
                    "latitude": 48.78,
                    "longitude": 9.18,
                    CONF_RADIUS: 150000,
                }
            },
            {CONF_LOCATION: "radius_too_large"},
        ),
        ({CONF_AREA_SOURCES: []}, {CONF_AREA_SOURCES: "no_sources"}),
    ],
)
async def test_area_validation(
    hass: HomeAssistant, roads: AsyncMock, changes: dict, errors: dict
) -> None:
    entry = entry_with(OPTIONS)
    entry.add_to_hass(hass)
    result = await start_area_flow(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], AREA_INPUT | changes
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors


async def test_area_road_list_unavailable(hass: HomeAssistant) -> None:
    entry = entry_with(OPTIONS)
    entry.add_to_hass(hass)
    with patch(
        "custom_components.streckenwacht.config_flow.AutobahnProvider.async_fetch_roads",
        side_effect=ProviderError("down"),
    ):
        result = await start_area_flow(hass, entry)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_area_directions_unavailable(
    hass: HomeAssistant, roads: AsyncMock
) -> None:
    entry = entry_with(OPTIONS)
    entry.add_to_hass(hass)
    result = await start_area_flow(hass, entry)
    with patch(
        "custom_components.streckenwacht.config_flow.AutobahnProvider.async_fetch",
        side_effect=ProviderError("down"),
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], AREA_INPUT
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_reconfigure_area(
    hass: HomeAssistant, roads: AsyncMock, directions: AsyncMock
) -> None:
    entry = entry_with(
        OPTIONS,
        [
            ConfigSubentryData(
                data={
                    "latitude": 48.0,
                    "longitude": 9.0,
                    CONF_RADIUS: 5000,
                    CONF_ROADS: ["A8"],
                    CONF_AREA_SOURCES: None,
                    CONF_DIRECTIONS: ["Stuttgart -> Karlsruhe"],
                },
                subentry_type=SUBENTRY_AREA,
                title="Alt",
                unique_id=None,
            )
        ],
    )
    entry.add_to_hass(hass)
    (subentry_id,) = entry.subentries
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_AREA),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry_id},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], AREA_INPUT
    )
    assert result["step_id"] == "directions"
    # the stored direction stays selectable even if it has no events right now
    (key,) = result["data_schema"].schema
    assert (
        "Stuttgart -> Karlsruhe" in result["data_schema"].schema[key].config["options"]
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_DIRECTIONS: []}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    subentry = entry.subentries[subentry_id]
    assert subentry.title == "Arbeitsweg"
    assert subentry.data[CONF_ROADS] == ["A8", "A81"]
    assert subentry.data[CONF_RADIUS] == 15000.0
    assert subentry.data[CONF_DIRECTIONS] == []
