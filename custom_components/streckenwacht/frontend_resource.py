"""Make the map card known to the frontend.

With dashboard resources in storage mode (the default), the card is a
dashboard resource: the frontend fetches that list whenever a page opens a
dashboard, and browsers keep the file cached. An extra module URL instead is
written into the page HTML when the page is requested; a page opened while
Home Assistant was still starting (the Companion app reloads often then) lacks
it until the next reload: "Custom element not found".

With resources in YAML mode they cannot be changed, so the card falls back
to the extra module URL.

Copies: tarifwacht/custom_components/tarifwacht/frontend_resource.py,
waermewacht/custom_components/waermewacht/frontend_resource.py,
speicherwacht/custom_components/speicherwacht/frontend_resource.py,
einspeisewacht/custom_components/einspeisewacht/frontend_resource.py (all
derived).
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlsplit

from homeassistant.components.frontend import add_extra_js_url, remove_extra_js_url
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.core import HomeAssistant

from .websocket import CARD_URL

_LOGGER = logging.getLogger(__name__)

# Resources are matched by path: other versions (?v=...) are ours too.
CARD_PATH = urlsplit(CARD_URL).path
RESOURCE_TYPE = "module"


def _storage_resources(hass: HomeAssistant) -> ResourceStorageCollection | None:
    """The editable dashboard resources, or None (YAML mode, no dashboards)."""
    data = hass.data.get(LOVELACE_DATA)
    resources = getattr(data, "resources", None)
    if isinstance(resources, ResourceStorageCollection):
        return resources
    return None


def _ours(resources: ResourceStorageCollection) -> list[dict[str, Any]]:
    return [
        item
        for item in resources.async_items()
        if urlsplit(str(item.get("url", ""))).path == CARD_PATH
    ]


async def async_register_card(hass: HomeAssistant) -> None:
    """Add or update the card resource; fall back to an extra module URL."""
    resources = _storage_resources(hass)
    if resources is not None:
        try:
            await _async_update_resources(resources)
        except Exception:
            _LOGGER.warning(
                "Could not add the map card to the dashboard resources", exc_info=True
            )
        else:
            return
    if "frontend" in hass.config.components:
        add_extra_js_url(hass, CARD_URL)


async def _async_update_resources(resources: ResourceStorageCollection) -> None:
    await resources.async_get_info()  # loads the collection if not done yet
    found = _ours(resources)
    if not found:
        await resources.async_create_item({"res_type": RESOURCE_TYPE, "url": CARD_URL})
        _LOGGER.debug("Added dashboard resource %s", CARD_URL)
        return
    first, *duplicates = found
    if first.get("url") != CARD_URL or first.get("type") != RESOURCE_TYPE:
        await resources.async_update_item(
            first["id"], {"res_type": RESOURCE_TYPE, "url": CARD_URL}
        )
        _LOGGER.debug("Updated dashboard resource to %s", CARD_URL)
    for item in duplicates:
        await resources.async_delete_item(item["id"])


def card_status(hass: HomeAssistant) -> str:
    """How the card reaches the frontend, for the bug report (button.py)."""
    resources = _storage_resources(hass)
    if resources is not None:
        found = _ours(resources)
        if not found:
            return "no dashboard resource"
        if any(item.get("url") == CARD_URL for item in found):
            return "dashboard resource"
        return "dashboard resource of another version"
    if "frontend" in hass.config.components:
        return "extra module URL (resources in YAML or no dashboards)"
    return "no frontend"


async def async_unregister_card(hass: HomeAssistant) -> None:
    """Remove the card resource (or extra module URL) again."""
    if "frontend" in hass.config.components:
        remove_extra_js_url(hass, CARD_URL)
    resources = _storage_resources(hass)
    if resources is None:
        return
    try:
        await resources.async_get_info()
        for item in _ours(resources):
            await resources.async_delete_item(item["id"])
    except Exception:
        _LOGGER.warning(
            "Could not remove the map card from the dashboard resources",
            exc_info=True,
        )
