"""Static checks for the bundled automation blueprints (run locally and in CI).

How they behave (texts in both languages, area in the title with several
areas, more actions)
is tested with Home Assistant in tests/ha/test_blueprints.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from homeassistant.components.automation.config import AUTOMATION_BLUEPRINT_SCHEMA
from homeassistant.components.blueprint.models import Blueprint
from homeassistant.util.yaml import Input, load_yaml

BLUEPRINTS = (
    Path(__file__).parent.parent / "blueprints" / "automation" / "streckenwacht"
)
FILES = sorted(BLUEPRINTS.glob("*.yaml"))
# Input keys before the blueprints became bilingual: none may disappear.
EARLIER_INPUTS = {
    "neue_meldung.yaml": {"event_entity", "types", "notify_ended", "notify_device"},
    "stau_benachrichtigung.yaml": {
        "delay_sensor",
        "threshold",
        "direction",
        "notify_device",
        "after",
        "before",
    },
    "vorwarnung_sperrung.yaml": {"next_closure", "lead_time", "notify_device"},
}


def load(path: Path) -> Blueprint:
    return Blueprint(
        load_yaml(path),
        expected_domain="automation",
        schema=AUTOMATION_BLUEPRINT_SCHEMA,
    )


def test_blueprints_exist() -> None:
    assert [f.name for f in FILES] == [
        "neue_meldung.yaml",
        "stau_benachrichtigung.yaml",
        "vorwarnung_sperrung.yaml",
    ]


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_blueprint_is_valid(path: Path) -> None:
    meta = load(path).metadata
    assert meta["name"].startswith("Streckenwacht – ")
    # The import button and HA's "re-import" use this URL.
    assert meta["source_url"] == (
        "https://github.com/streckenwacht/integration/blob/main/"
        f"blueprints/automation/streckenwacht/{path.name}"
    )
    assert meta["homeassistant"]["min_version"] == "2026.3.0"


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_texts_in_both_languages(path: Path) -> None:
    blueprint = load(path)
    meta = blueprint.metadata
    assert " / " in meta["name"]
    german, english = meta["description"].split("\n")
    assert "Handy" in german
    assert "phone" in english
    sections = [v for v in meta["input"].values() if v and "input" in v]
    for field in [*blueprint.inputs.values(), *sections]:
        assert " / " in field["name"], field["name"]
        assert " / " in field.get("description", " / "), field["description"]


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_inputs_stay_compatible(path: Path) -> None:
    inputs = load(path).inputs
    assert EARLIER_INPUTS[path.name] <= set(inputs)
    # The phone stays required as before.
    phone = inputs["notify_device"]
    assert "default" not in phone
    assert phone["selector"]["device"]["filter"] == [{"integration": "mobile_app"}]
    # Every new input has a default: nothing new to fill in.
    for key in set(inputs) - EARLIER_INPUTS[path.name]:
        assert "default" in inputs[key], key


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_language_and_more_actions(path: Path) -> None:
    blueprint = load(path)
    language = blueprint.inputs["language"]
    assert language["default"] == "de"
    options = language["selector"]["select"]["options"]
    assert [o["value"] for o in options] == ["de", "en"]

    section = blueprint.metadata["input"]["more_actions"]
    assert section["collapsed"] is True
    assert list(section["input"]) == ["extra_actions"]
    extra = section["input"]["extra_actions"]
    assert extra["default"] == []
    assert extra["selector"] == {"action": {}}
    assert "telegram_bot.send_message" in extra["description"]


def _input_name(value: Any) -> str | None:
    return value.name if isinstance(value, Input) else None


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_actions_share_title_and_message(path: Path) -> None:
    """The phone and the more actions get the same finished texts."""
    blueprint = load(path)
    assert _input_name(blueprint.data["variables"]["lang"]) == "language"
    texts, phone, more = blueprint.data["actions"]
    head = texts["variables"]["head"]
    assert "device_attr(dev, 'name_by_user') or device_attr(dev, 'name')" in head
    assert "'Streckenwacht'" in head  # without a device
    # The area only with several areas: the devices of the integration count.
    assert "integration_entities('streckenwacht') | map('device_id')" in head
    assert "if areas | count > 1 else none" in head
    title = texts["variables"]["title"]
    assert "head" in title
    assert "lang" in title
    assert "message" in texts["variables"]
    assert phone["domain"] == "mobile_app"
    assert _input_name(phone["device_id"]) == "notify_device"
    assert phone["title"] == "{{ title }}"
    assert phone["message"] == "{{ message }}"
    assert _input_name(more["sequence"]) == "extra_actions"


def test_every_device_is_an_area() -> None:
    """The blueprints count areas as devices of the integration's entities.

    That holds while only the area entities (entity.py) bring a device; a
    device for something else (e.g. a hub) would make one area look like two.
    """
    code = Path(__file__).parent.parent / "custom_components" / "streckenwacht"
    with_device = sorted(
        p.name for p in code.rglob("*.py") if "DeviceInfo(" in p.read_text("utf-8")
    )
    assert with_device == ["entity.py"]


def test_english_date_is_iso() -> None:
    """English: 2026-11-10 21:00 (no month names); German stays 10.11. 21:00."""
    when = load(BLUEPRINTS / "vorwarnung_sperrung.yaml").data["variables"]["when"]
    assert "'%Y-%m-%d %H:%M' if lang == 'en' else '%d.%m. %H:%M'" in when
