"""The button "Report for a bug report": what it shows, and that nothing in
it locates an area."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.streckenwacht.const import (
    CONF_AREA_SOURCES,
    CONF_DIRECTIONS,
    CONF_INCLUDE_INRIX,
    CONF_JAM_THRESHOLD,
    CONF_RADIUS,
    CONF_ROADS,
    CONF_SCAN_INTERVAL,
    CONF_TYPES,
    DOMAIN,
    SUBENTRY_AREA,
    Source,
)
from custom_components.streckenwacht.model import EventType, Period, StreckenwachtEvent
from custom_components.streckenwacht.providers import ProviderError

NOW = dt_util.parse_datetime("2026-10-05T12:00:00+00:00")
H = timedelta(hours=1)
AUTOBAHN_FETCH = (
    "custom_components.streckenwacht.providers.autobahn.AutobahnProvider.async_fetch"
)
MOBIDATA_FETCH = (
    "custom_components.streckenwacht.providers.mobidata_bw."
    "MobiDataBWProvider.async_fetch"
)
CREATE = (
    "custom_components.streckenwacht.issue_report.persistent_notification.async_create"
)


def ev(id_: str, event_type: EventType, **kwargs) -> StreckenwachtEvent:
    return StreckenwachtEvent(
        id=f"autobahn:{id_}",
        source=Source.AUTOBAHN,
        event_type=event_type,
        title=f"A8 Leonberg-Ost {id_}",
        road="A8",
        latitude=48.7801,
        longitude=9.1801,
        periods=(Period(NOW - H, NOW + 5 * H),),
        **kwargs,
    )


EVENTS = [
    ev("works", EventType.ROADWORKS),
    ev("closed", EventType.CLOSURE),
    ev(
        "jam",
        EventType.TRAFFIC_JAM,
        direction="Karlsruhe -> Stuttgart",
        delay_minutes=25,
        upstream="inrix",
    ),
]


def timeout() -> ProviderError:
    # The message names the URL (for the Autobahn: the chosen roads).
    err = ProviderError(
        "Timeout fetching https://api.mobidata-bw.de/datasets/traffic/A8"
    )
    err.__cause__ = TimeoutError()
    return err


def make_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Streckenwacht",
        options={CONF_SCAN_INTERVAL: 15, CONF_INCLUDE_INRIX: True},
        subentries_data=[
            ConfigSubentryData(
                data={
                    "latitude": 48.7799,
                    "longitude": 9.1799,
                    CONF_RADIUS: 10000,
                    CONF_AREA_SOURCES: ["autobahn", "mobidata_bw"],
                    CONF_ROADS: ["A8"],
                    CONF_DIRECTIONS: ["Karlsruhe -> Stuttgart"],
                    CONF_JAM_THRESHOLD: 10,
                },
                subentry_type=SUBENTRY_AREA,
                title="Arbeitsweg",
                unique_id=None,
            ),
            ConfigSubentryData(
                data={
                    "latitude": 48.7403,
                    "longitude": 9.1201,
                    CONF_RADIUS: 4600,
                    CONF_AREA_SOURCES: ["mobidata_bw"],
                    CONF_ROADS: [],
                    CONF_DIRECTIONS: [],
                    CONF_TYPES: ["closure", "accident"],
                },
                subentry_type=SUBENTRY_AREA,
                title="Zuhause",
                unique_id=None,
            ),
        ],
        minor_version=3,
    )


async def test_report_for_a_bug_report(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(NOW)
    entry = make_entry()
    entry.add_to_hass(hass)
    with (
        patch(AUTOBAHN_FETCH, return_value=list(EVENTS)),
        patch(MOBIDATA_FETCH, side_effect=timeout()),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        mobidata = entry.runtime_data.coordinators[Source.MOBIDATA_BW]
        await mobidata.async_refresh()
        await mobidata.async_refresh()  # third failure: repair issue

    registry = er.async_get(hass)
    first, second = entry.subentries
    button = registry.async_get_entity_id("button", DOMAIN, f"{second}_issue_report")
    assert button == "button.streckenwacht_zuhause_report_for_a_bug_report"
    assert registry.async_get(button).entity_category is EntityCategory.DIAGNOSTIC
    assert registry.async_get_entity_id("button", DOMAIN, f"{first}_issue_report")

    with patch(CREATE) as create:
        await hass.services.async_call(
            "button", "press", {"entity_id": button}, blocking=True
        )
    assert create.call_args.kwargs["notification_id"] == (
        f"streckenwacht_issue_report_{entry.entry_id}"
    )
    assert create.call_args.kwargs["title"] == "Streckenwacht: report for a bug report"
    message = create.call_args.args[1]

    for line in (
        "areas: 2",
        "report from area: 2",
        "sources polled: 2",
        "events in the areas: ",
        "map card: ",
        "area 1: radius 10 km, sources 2, roads 1, directions 1, "
        "jam threshold 10 min, types all, events 3\n",
        "area 2: radius 5 km, sources 1, roads 0, types accident/closure, events 0",
        "autobahn: ok, 0 min ago, 3 fetched, 3 in the areas\n",
        "mobidata_bw: failed 3x (timeout), last success never, no data",
        "scan_interval: 15 min",
        "include_inrix: yes",
        "merge_duplicates: yes",
        "with a value: ",
        "open: provider_failed_mobidata_bw",
    ):
        assert line in message, line

    # Nothing that locates an area or names the user's entities.
    for secret in (
        "48.7",
        "9.18",
        "9.12",
        "Arbeitsweg",
        "Zuhause",
        "A8",
        "Leonberg",
        "Karlsruhe",
        "Stuttgart",
        "mobidata-bw.de",
        "streckenwacht_",
        entry.entry_id,
        first,
        second,
    ):
        assert secret not in message, secret
