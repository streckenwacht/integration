"""Static checks for the bundled automation blueprints (run locally and in CI)."""

from __future__ import annotations

from pathlib import Path

import pytest
from homeassistant.components.automation.config import AUTOMATION_BLUEPRINT_SCHEMA
from homeassistant.components.blueprint.models import Blueprint
from homeassistant.util.yaml import load_yaml

BLUEPRINTS = (
    Path(__file__).parent.parent / "blueprints" / "automation" / "streckenwacht"
)
FILES = sorted(BLUEPRINTS.glob("*.yaml"))


def test_blueprints_exist() -> None:
    assert [f.name for f in FILES] == [
        "neue_meldung.yaml",
        "stau_benachrichtigung.yaml",
    ]


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_blueprint_is_valid(path: Path) -> None:
    blueprint = Blueprint(
        load_yaml(path),
        expected_domain="automation",
        schema=AUTOMATION_BLUEPRINT_SCHEMA,
    )
    meta = blueprint.metadata
    assert meta["name"].startswith("Streckenwacht")
    # The import button and HA's "re-import" use this URL.
    assert meta["source_url"] == (
        "https://github.com/streckenwacht/integration/blob/main/"
        f"blueprints/automation/streckenwacht/{path.name}"
    )
    assert meta["homeassistant"]["min_version"] == "2026.3.0"
