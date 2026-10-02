"""The blueprints as real automations: triggers, conditions and message texts.

The mobile_app notify action needs a real phone; it is swapped for a test
service with the same title and message templates.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from homeassistant.components.automation.config import AUTOMATION_BLUEPRINT_SCHEMA
from homeassistant.components.blueprint.models import Blueprint, BlueprintInputs
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.yaml import load_yaml
from pytest_homeassistant_custom_component.common import async_mock_service

BLUEPRINTS = (
    Path(__file__).parent.parent.parent / "blueprints" / "automation" / "streckenwacht"
)
EVENT_ENTITY = "event.streckenwacht_arbeitsweg_event_change"
DELAY_SENSOR = "sensor.streckenwacht_arbeitsweg_travel_time_loss"


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
