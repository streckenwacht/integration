"""The blueprints as real automations: triggers, conditions and message texts.

The mobile_app notify action needs a real phone; it is swapped for a test
service with the same title and message templates.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from homeassistant.components.automation.config import AUTOMATION_BLUEPRINT_SCHEMA
from homeassistant.components.blueprint.models import Blueprint, BlueprintInputs
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.yaml import load_yaml
from pytest_homeassistant_custom_component.common import async_mock_service

BLUEPRINTS = (
    Path(__file__).parent.parent.parent / "blueprints" / "automation" / "streckenwacht"
)
EVENT_ENTITY = "event.streckenwacht_arbeitsweg_event_change"
DELAY_SENSOR = "sensor.streckenwacht_arbeitsweg_travel_time_loss"
NEXT_CLOSURE = "sensor.streckenwacht_arbeitsweg_next_closure"


async def setup_blueprint(
    hass: HomeAssistant, name: str, inputs: dict[str, Any]
) -> list:
    blueprint = Blueprint(
        load_yaml(BLUEPRINTS / name),
        expected_domain="automation",
        schema=AUTOMATION_BLUEPRINT_SCHEMA,
    )
    config = BlueprintInputs(
        blueprint, {"use_blueprint": {"path": name, "input": inputs}}
    ).async_substitute()
    config.pop("use_blueprint", None)
    (notify,) = config["actions"]
    assert notify["domain"] == "mobile_app"
    assert notify["device_id"] == "phone"
    config["actions"] = [
        {
            "action": "test.notify",
            "data": {"title": notify["title"], "message": notify["message"]},
        }
    ]
    calls = async_mock_service(hass, "test", "notify")
    assert await async_setup_component(hass, "automation", {"automation": [config]})
    await hass.async_block_till_done()
    return calls


def fire(hass: HomeAssistant, timestamp: str, **attributes: Any) -> None:
    hass.states.async_set(EVENT_ENTITY, timestamp, attributes)


async def test_new_closure_notifies(hass: HomeAssistant) -> None:
    calls = await setup_blueprint(
        hass,
        "neue_meldung.yaml",
        {"event_entity": EVENT_ENTITY, "notify_device": "phone"},
    )
    fire(
        hass,
        "2026-10-05T12:00:00+00:00",
        event_type="new",
        type="closure",
        title="A81 | Leonberg - Engelbergtunnel",
        road="A81",
        direction="Stuttgart -> Heilbronn",
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["title"] == "Neu: Sperrung"
    assert calls[0].data["message"] == (
        "A81 | Leonberg - Engelbergtunnel (Stuttgart -> Heilbronn)"
    )


async def test_filtered_types_and_ended(hass: HomeAssistant) -> None:
    calls = await setup_blueprint(
        hass,
        "neue_meldung.yaml",
        {"event_entity": EVENT_ENTITY, "notify_device": "phone"},
    )
    # roadworks are not selected by default
    fire(
        hass, "2026-10-05T12:00:00+00:00", event_type="new", type="roadworks", title="x"
    )
    # "ended" only if enabled (default off)
    fire(
        hass, "2026-10-05T12:01:00+00:00", event_type="ended", type="closure", title="y"
    )
    # the entity going away must not break the automation
    hass.states.async_remove(EVENT_ENTITY)
    await hass.async_block_till_done()
    assert calls == []


async def test_ended_when_enabled(hass: HomeAssistant) -> None:
    calls = await setup_blueprint(
        hass,
        "neue_meldung.yaml",
        {
            "event_entity": EVENT_ENTITY,
            "notify_device": "phone",
            "notify_ended": True,
            "types": ["traffic_jam"],
        },
    )
    fire(
        hass,
        "2026-10-05T12:00:00+00:00",
        event_type="ended",
        type="traffic_jam",
        title="Stau",
        road="A8",
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["title"] == "Beendet: Stau"
    assert calls[0].data["message"] == "Stau (A8)"


async def test_traffic_jam_threshold(hass: HomeAssistant) -> None:
    hass.states.async_set(DELAY_SENSOR, "5", {"title": "A8 | Stau", "direction": None})
    calls = await setup_blueprint(
        hass,
        "stau_benachrichtigung.yaml",
        {"delay_sensor": DELAY_SENSOR, "notify_device": "phone", "threshold": 15},
    )
    hass.states.async_set(DELAY_SENSOR, "10", {"title": "A8 | Stau", "direction": None})
    await hass.async_block_till_done()
    assert calls == []

    hass.states.async_set(
        DELAY_SENSOR,
        "25",
        {
            "title": "A8 | Heimsheim - Pforzheim-Nord",
            "direction": "Stuttgart -> Karlsruhe",
        },
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["title"] == "Stau: +25 min"
    assert calls[0].data["message"] == (
        "A8 | Heimsheim - Pforzheim-Nord (Stuttgart -> Karlsruhe)"
    )


async def test_traffic_jam_in_one_direction(hass: HomeAssistant) -> None:
    jam = {"title": "A5 | Bruchsal - Kronau", "direction": "Karlsruhe -> Heidelberg"}
    hass.states.async_set(DELAY_SENSOR, "0", {"by_direction": {}})
    calls = await setup_blueprint(
        hass,
        "stau_benachrichtigung.yaml",
        {
            "delay_sensor": DELAY_SENSOR,
            "notify_device": "phone",
            "threshold": 10,
            "direction": "karlsruhe",  # the destination is enough, any case
        },
    )
    # the other carriageway: no message, although the sensor is above 10
    hass.states.async_set(
        DELAY_SENSOR,
        "25",
        jam | {"by_direction": {"Karlsruhe -> Heidelberg": 25}},
    )
    await hass.async_block_till_done()
    assert calls == []

    hass.states.async_set(
        DELAY_SENSOR,
        "25",
        jam
        | {
            "by_direction": {
                "Karlsruhe -> Heidelberg": 25,
                "Heidelberg -> Karlsruhe": 12,
            }
        },
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    # loss and direction of the chosen carriageway, not of the largest jam
    assert calls[0].data["title"] == "Stau: +12 min"
    assert calls[0].data["message"] == "Stau (Heidelberg -> Karlsruhe)"


# The template trigger re-evaluates now() every minute: its timer outlives the test.
@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_closure_warning_within_the_lead_time(hass: HomeAssistant) -> None:
    now = dt_util.utcnow()
    later = (now + timedelta(hours=48)).isoformat()
    hass.states.async_set(NEXT_CLOSURE, later, {"title": "A81 | Vollsperrung"})
    calls = await setup_blueprint(
        hass,
        "vorwarnung_sperrung.yaml",
        {"next_closure": NEXT_CLOSURE, "notify_device": "phone"},
    )
    await hass.async_block_till_done()
    assert calls == []  # 48 h ahead: outside the default 12 h lead time

    soon = now + timedelta(hours=11)
    hass.states.async_set(
        NEXT_CLOSURE,
        soon.isoformat(),
        {"title": "A81 | Leonberg - Engelbergtunnel", "road": "A81", "direction": None},
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    local = dt_util.as_local(soon.replace(microsecond=0))
    assert calls[0].data["title"] == f"Sperrung ab {local.strftime('%d.%m. %H:%M')}"
    assert calls[0].data["message"] == "A81 | Leonberg - Engelbergtunnel (A81)"
