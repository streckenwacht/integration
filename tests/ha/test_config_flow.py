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
    CONF_JAM_THRESHOLD,
    CONF_LOCATION,
    CONF_MERGE_DUPLICATES,
    CONF_RADIUS,
    CONF_ROADS,
    CONF_SCAN_INTERVAL,
    CONF_TYPES,
    DOMAIN,
    SUBENTRY_AREA,
    Source,
)
from custom_components.streckenwacht.model import EventType, StreckenwachtEvent
from custom_components.streckenwacht.providers import ProviderError

ROADS = ["A1", "A8", "A81"]
OPTIONS = {CONF_SCAN_INTERVAL: 15, CONF_INCLUDE_INRIX: True}


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
        minor_version=3,
    )


# --- Main entry --------------------------------------------------------------


async def test_user_flow(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    # Setup asks only for INRIX; the rest is in the options.
    assert set(result["data_schema"].schema) == {CONF_INCLUDE_INRIX}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_INCLUDE_INRIX: False}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Streckenwacht"
    assert result["options"] == {
        CONF_SCAN_INTERVAL: 15,  # default
        CONF_INCLUDE_INRIX: False,
        CONF_MERGE_DUPLICATES: True,  # default
    }


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
    # No area yet: the overview says what is missing.
    assert "Add observation area" in result["description_placeholders"]["overview"]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SCAN_INTERVAL: 30,
            CONF_INCLUDE_INRIX: False,
            CONF_MERGE_DUPLICATES: False,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        CONF_SCAN_INTERVAL: 30,
        CONF_INCLUDE_INRIX: False,
        CONF_MERGE_DUPLICATES: False,
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
STUTTGART = {"latitude": 48.78, "longitude": 9.18, CONF_RADIUS: 15000}
ALL_TYPES = ["roadworks", "closure", "traffic_jam", "accident", "warning"]
AREA_INPUT = {"name": "Arbeitsweg", CONF_LOCATION: STUTTGART, CONF_TYPES: ALL_TYPES}
SOURCES_INPUT = {CONF_AREA_SOURCES: ["autobahn", "mobidata_bw"]}


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


async def configure(hass: HomeAssistant, result: dict, user_input: dict) -> dict:
    return await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input
    )


def field(result: dict, name: str) -> tuple:
    """The schema marker and selector of a form field."""
    schema = result["data_schema"].schema
    key = next(k for k in schema if k == name)
    return key, schema[key]


def options_of(result: dict, name: str) -> list[str]:
    return field(result, name)[1].config["options"]


def suggested(result: dict, name: str) -> object:
    return field(result, name)[0].description["suggested_value"]


async def test_add_area_wizard(
    hass: HomeAssistant, roads: AsyncMock, directions: AsyncMock
) -> None:
    entry = entry_with(OPTIONS)
    entry.add_to_hass(hass)

    # step 1: name and circle only
    result = await start_area_flow(hass, entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert set(result["data_schema"].schema) == {"name", CONF_LOCATION, CONF_TYPES}
    assert suggested(result, CONF_TYPES) == ALL_TYPES

    # step 2: the sources covering Stuttgart, all preselected
    result = await configure(hass, result, AREA_INPUT)
    assert result["step_id"] == "sources"
    offered = ["autobahn", "mobidata_bw", "stuttgart", "lms_bw"]
    assert options_of(result, CONF_AREA_SOURCES) == offered
    assert suggested(result, CONF_AREA_SOURCES) == offered
    roads.assert_not_awaited()

    # step 3: motorways
    result = await configure(hass, result, SOURCES_INPUT)
    assert result["step_id"] == "roads"
    assert options_of(result, CONF_ROADS) == ROADS

    # step 4: directions actually used on these motorways
    result = await configure(hass, result, {CONF_ROADS: ["A81", "A8"]})
    assert result["step_id"] == "directions"
    assert options_of(result, CONF_DIRECTIONS) == [
        "Singen -> Stuttgart",
        "Stuttgart -> Singen",
    ]
    (areas,) = directions.await_args.args
    assert areas[0].roads == frozenset({"A8", "A81"})

    result = await configure(hass, result, {CONF_DIRECTIONS: ["Singen -> Stuttgart"]})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    (subentry,) = entry.subentries.values()
    assert subentry.title == "Arbeitsweg"
    assert dict(subentry.data) == {
        "latitude": 48.78,
        "longitude": 9.18,
        CONF_RADIUS: 15000.0,
        CONF_AREA_SOURCES: ["autobahn", "mobidata_bw"],
        CONF_ROADS: ["A8", "A81"],
        CONF_JAM_THRESHOLD: 10,
        CONF_DIRECTIONS: ["Singen -> Stuttgart"],
        CONF_TYPES: None,  # all kinds
    }


@pytest.mark.parametrize(
    ("location", "offered"),
    [
        ({"latitude": 52.13, "longitude": 11.63}, ["autobahn", "sachsen_anhalt"]),
        (
            {"latitude": 52.52, "longitude": 13.40},
            ["autobahn", "berlin", "brandenburg"],
        ),
        ({"latitude": 53.55, "longitude": 10.0}, ["autobahn", "norddeutschland"]),
        ({"latitude": 48.14, "longitude": 11.58}, ["autobahn", "muenchen"]),
    ],
)
async def test_sources_offered_by_location(
    hass: HomeAssistant, location: dict, offered: list[str]
) -> None:
    entry = entry_with(OPTIONS)
    entry.add_to_hass(hass)
    result = await start_area_flow(hass, entry)
    result = await configure(
        hass,
        result,
        {
            "name": "Test",
            CONF_LOCATION: location | {CONF_RADIUS: 5000},
            CONF_TYPES: ALL_TYPES,
        },
    )
    assert result["step_id"] == "sources"
    assert options_of(result, CONF_AREA_SOURCES) == offered


async def test_only_autobahn_skips_the_sources_step(
    hass: HomeAssistant, roads: AsyncMock
) -> None:
    entry = entry_with(OPTIONS)
    entry.add_to_hass(hass)
    result = await start_area_flow(hass, entry)
    nuremberg = {"latitude": 49.45, "longitude": 11.08, CONF_RADIUS: 5000}
    result = await configure(
        hass, result, AREA_INPUT | {"name": "A9", CONF_LOCATION: nuremberg}
    )
    assert result["step_id"] == "roads"


async def test_area_without_motorway_source_ends_after_sources(
    hass: HomeAssistant, roads: AsyncMock, directions: AsyncMock
) -> None:
    entry = entry_with(OPTIONS)
    entry.add_to_hass(hass)
    result = await start_area_flow(hass, entry)
    result = await configure(hass, result, AREA_INPUT)
    result = await configure(hass, result, {CONF_AREA_SOURCES: ["mobidata_bw"]})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    (subentry,) = entry.subentries.values()
    assert subentry.data[CONF_AREA_SOURCES] == ["mobidata_bw"]
    assert subentry.data[CONF_ROADS] == []
    assert subentry.data[CONF_DIRECTIONS] == []
    roads.assert_not_awaited()
    directions.assert_not_awaited()


async def test_a_source_is_required(hass: HomeAssistant) -> None:
    entry = entry_with(OPTIONS)
    entry.add_to_hass(hass)
    result = await start_area_flow(hass, entry)
    result = await configure(hass, result, AREA_INPUT)
    result = await configure(hass, result, {CONF_AREA_SOURCES: []})
    assert result["step_id"] == "sources"
    assert result["errors"] == {CONF_AREA_SOURCES: "no_sources"}


@pytest.mark.parametrize(
    ("changes", "errors"),
    [
        ({"name": "   "}, {"name": "name_required"}),
        ({CONF_TYPES: []}, {CONF_TYPES: "no_types"}),
        (
            {CONF_LOCATION: STUTTGART | {CONF_RADIUS: 150000}},
            {CONF_LOCATION: "radius_too_large"},
        ),
    ],
)
async def test_area_validation(
    hass: HomeAssistant, roads: AsyncMock, changes: dict, errors: dict
) -> None:
    entry = entry_with(OPTIONS)
    entry.add_to_hass(hass)
    result = await start_area_flow(hass, entry)
    result = await configure(hass, result, AREA_INPUT | changes)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors


async def test_motorway_required(hass: HomeAssistant, roads: AsyncMock) -> None:
    entry = entry_with(OPTIONS)
    entry.add_to_hass(hass)
    result = await start_area_flow(hass, entry)
    result = await configure(hass, result, AREA_INPUT)
    result = await configure(hass, result, SOURCES_INPUT)
    result = await configure(hass, result, {CONF_ROADS: []})
    assert result["step_id"] == "roads"
    assert result["errors"] == {CONF_ROADS: "no_roads"}


async def test_area_road_list_unavailable(hass: HomeAssistant) -> None:
    entry = entry_with(OPTIONS)
    entry.add_to_hass(hass)
    result = await start_area_flow(hass, entry)
    result = await configure(hass, result, AREA_INPUT)
    with patch(
        "custom_components.streckenwacht.config_flow.AutobahnProvider.async_fetch_roads",
        side_effect=ProviderError("down"),
    ):
        result = await configure(hass, result, SOURCES_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_area_directions_unavailable(
    hass: HomeAssistant, roads: AsyncMock
) -> None:
    entry = entry_with(OPTIONS)
    entry.add_to_hass(hass)
    result = await start_area_flow(hass, entry)
    result = await configure(hass, result, AREA_INPUT)
    result = await configure(hass, result, SOURCES_INPUT)
    with patch(
        "custom_components.streckenwacht.config_flow.AutobahnProvider.async_fetch",
        side_effect=ProviderError("down"),
    ):
        result = await configure(hass, result, {CONF_ROADS: ["A8"]})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


def stored_area(**data: object) -> ConfigSubentryData:
    return ConfigSubentryData(
        data={
            "latitude": 48.0,
            "longitude": 9.0,
            CONF_RADIUS: 5000,
            CONF_ROADS: ["A8"],
            CONF_AREA_SOURCES: ["autobahn", "stuttgart"],
            CONF_DIRECTIONS: ["Stuttgart -> Karlsruhe"],
        }
        | data,
        subentry_type=SUBENTRY_AREA,
        title="Alt",
        unique_id=None,
    )


async def start_reconfigure(hass: HomeAssistant, entry: MockConfigEntry) -> dict:
    (subentry_id,) = entry.subentries
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_AREA),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry_id},
    )


async def test_reconfigure_area(
    hass: HomeAssistant, roads: AsyncMock, directions: AsyncMock
) -> None:
    entry = entry_with(OPTIONS, [stored_area()])
    entry.add_to_hass(hass)
    (subentry_id,) = entry.subentries
    result = await start_reconfigure(hass, entry)
    assert result["step_id"] == "reconfigure"

    result = await configure(hass, result, AREA_INPUT)
    assert result["step_id"] == "sources"
    # stored sources are preselected and stay offered
    assert suggested(result, CONF_AREA_SOURCES) == ["autobahn", "stuttgart"]

    result = await configure(hass, result, SOURCES_INPUT)
    assert result["step_id"] == "roads"
    # stored motorways are preselected
    assert suggested(result, CONF_ROADS) == ["A8"]

    result = await configure(hass, result, {CONF_ROADS: ["A8", "A81"]})
    assert result["step_id"] == "directions"
    # the stored direction stays selectable even if it has no events right now
    assert "Stuttgart -> Karlsruhe" in options_of(result, CONF_DIRECTIONS)

    result = await configure(hass, result, {CONF_DIRECTIONS: []})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    subentry = entry.subentries[subentry_id]
    assert subentry.title == "Arbeitsweg"
    assert subentry.data[CONF_AREA_SOURCES] == ["autobahn", "mobidata_bw"]
    assert subentry.data[CONF_ROADS] == ["A8", "A81"]
    assert subentry.data[CONF_RADIUS] == 15000.0
    assert subentry.data[CONF_DIRECTIONS] == []


async def test_options_overview_lists_the_areas(hass: HomeAssistant) -> None:
    entry = entry_with(OPTIONS, [stored_area()])
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    overview = result["description_placeholders"]["overview"]
    # Not loaded: no event counts.
    assert overview == "**Set up**\n- Alt: radius 5 km, 2 sources"


async def test_reconfigure_shows_an_overview(hass: HomeAssistant) -> None:
    entry = entry_with(
        OPTIONS | {CONF_INCLUDE_INRIX: False},
        [stored_area(types=["closure", "traffic_jam"], jam_threshold=20)],
    )
    entry.add_to_hass(hass)
    hass.states.async_set(
        "zone.work",
        "0",
        {"latitude": 48.001, "longitude": 9.0, "radius": 300, "friendly_name": "Work"},
    )
    result = await start_reconfigure(hass, entry)
    overview = result["description_placeholders"]["overview"]
    assert overview.startswith("**Set up**\n- Centre: Work, radius 5 km\n")
    assert "- Sources: Autobahn GmbH, Stadt Stuttgart\n" in overview
    # Without INRIX no jam threshold, and the jams are missing.
    assert "- Motorways: A8 (direction Stuttgart -> Karlsruhe)\n" in overview
    assert "- Kinds of reports: Closures, Traffic jams\n" in overview
    assert "- Automations: none" in overview
    assert "**Missing**" in overview
    assert "need INRIX" in overview
    # The circle (48.0, 9.0) lies outside the city of Stuttgart.
    assert "nothing from them here: Stadt Stuttgart" in overview


async def test_reconfigure_overview_in_german(hass: HomeAssistant) -> None:
    hass.config.language = "de"
    entry = entry_with(OPTIONS, [stored_area()])
    entry.add_to_hass(hass)
    result = await start_reconfigure(hass, entry)
    overview = result["description_placeholders"]["overview"]
    assert overview.startswith(
        "**Eingerichtet**\n- Mittelpunkt: 48.00, 9.00, Radius 5 km"
    )
    assert "Stau zählt ab 10 min" in overview


async def test_reconfigure_without_inrix_keeps_the_jam_threshold(
    hass: HomeAssistant, roads: AsyncMock, directions: AsyncMock
) -> None:
    entry = entry_with(
        OPTIONS | {CONF_INCLUDE_INRIX: False}, [stored_area(jam_threshold=25)]
    )
    entry.add_to_hass(hass)
    (subentry_id,) = entry.subentries
    result = await start_reconfigure(hass, entry)
    result = await configure(hass, result, AREA_INPUT)
    result = await configure(hass, result, SOURCES_INPUT)
    assert CONF_JAM_THRESHOLD not in result["data_schema"].schema
    result = await configure(hass, result, {CONF_ROADS: ["A8"]})
    result = await configure(hass, result, {CONF_DIRECTIONS: []})
    assert result["reason"] == "reconfigure_successful"
    assert entry.subentries[subentry_id].data[CONF_JAM_THRESHOLD] == 25


async def test_reconfigure_keeps_stored_sources_selectable_after_moving(
    hass: HomeAssistant,
) -> None:
    entry = entry_with(OPTIONS, [stored_area()])
    entry.add_to_hass(hass)
    result = await start_reconfigure(hass, entry)
    magdeburg = {"latitude": 52.13, "longitude": 11.63, CONF_RADIUS: 5000}
    result = await configure(
        hass, result, AREA_INPUT | {"name": "Neu", CONF_LOCATION: magdeburg}
    )
    # Stuttgart is far away now, but can still be deselected.
    assert options_of(result, CONF_AREA_SOURCES) == [
        "autobahn",
        "stuttgart",
        "sachsen_anhalt",
    ]


async def test_reconfigure_dropping_autobahn_clears_motorways(
    hass: HomeAssistant, roads: AsyncMock
) -> None:
    entry = entry_with(OPTIONS, [stored_area()])
    entry.add_to_hass(hass)
    (subentry_id,) = entry.subentries
    result = await start_reconfigure(hass, entry)
    result = await configure(hass, result, AREA_INPUT)
    result = await configure(hass, result, {CONF_AREA_SOURCES: ["mobidata_bw"]})
    assert result["type"] is FlowResultType.ABORT
    data = entry.subentries[subentry_id].data
    assert data[CONF_ROADS] == []
    assert data[CONF_DIRECTIONS] == []


async def test_jam_threshold_in_motorway_step(
    hass: HomeAssistant, roads: AsyncMock, directions: AsyncMock
) -> None:
    entry = entry_with(OPTIONS)
    entry.add_to_hass(hass)
    result = await start_area_flow(hass, entry)
    result = await configure(hass, result, AREA_INPUT)
    result = await configure(hass, result, SOURCES_INPUT)
    assert CONF_JAM_THRESHOLD in result["data_schema"].schema
    result = await configure(
        hass, result, {CONF_ROADS: ["A8"], CONF_JAM_THRESHOLD: 20.0}
    )
    result = await configure(hass, result, {CONF_DIRECTIONS: []})
    (subentry,) = entry.subentries.values()
    assert subentry.data[CONF_JAM_THRESHOLD] == 20


async def test_no_jam_threshold_without_inrix(
    hass: HomeAssistant, roads: AsyncMock, directions: AsyncMock
) -> None:
    entry = entry_with(OPTIONS | {CONF_INCLUDE_INRIX: False})
    entry.add_to_hass(hass)
    result = await start_area_flow(hass, entry)
    result = await configure(hass, result, AREA_INPUT)
    result = await configure(hass, result, SOURCES_INPUT)
    assert CONF_JAM_THRESHOLD not in result["data_schema"].schema


async def test_area_with_some_kinds_of_reports(
    hass: HomeAssistant, roads: AsyncMock
) -> None:
    entry = entry_with(OPTIONS)
    entry.add_to_hass(hass)
    result = await start_area_flow(hass, entry)
    result = await configure(
        hass, result, AREA_INPUT | {CONF_TYPES: ["closure", "accident"]}
    )
    result = await configure(hass, result, {CONF_AREA_SOURCES: ["mobidata_bw"]})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    (subentry,) = entry.subentries.values()
    assert subentry.data[CONF_TYPES] == ["accident", "closure"]


async def test_reconfigure_preselects_stored_kinds(hass: HomeAssistant) -> None:
    entry = entry_with(OPTIONS, [stored_area(types=["closure"])])
    entry.add_to_hass(hass)
    result = await start_reconfigure(hass, entry)
    assert suggested(result, CONF_TYPES) == ["closure"]
