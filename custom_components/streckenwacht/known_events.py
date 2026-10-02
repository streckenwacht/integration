"""Remembers which events each area has seen, so restarts do not re-announce them."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

STORAGE_VERSION = 1
SAVE_DELAY = 10  # seconds


def _key(entry_id: str) -> str:
    return f"{DOMAIN}.{entry_id}.known_events"


class KnownEvents:
    """Per area: a fingerprint of its settings and the seen events per source.

    Layout: {subentry_id: {"fingerprint": str, "events": {source: {id: title}}}}
    """

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, _key(entry_id)
        )
        self._data: dict[str, Any] = {}

    async def async_load(self, keep: Iterable[str]) -> None:
        """Load stored data, dropping areas that no longer exist."""
        stored = await self._store.async_load() or {}
        keep = set(keep)
        self._data = {k: v for k, v in stored.items() if k in keep}
        if len(self._data) != len(stored):
            self._store.async_delay_save(lambda: self._data, SAVE_DELAY)

    def get(self, subentry_id: str) -> dict[str, Any] | None:
        """Stored state of an area, if any."""
        return self._data.get(subentry_id)

    def set(self, subentry_id: str, value: dict[str, Any]) -> None:
        """Store the state of an area (saved with a short delay)."""
        self._data[subentry_id] = value
        self._store.async_delay_save(lambda: self._data, SAVE_DELAY)

    @staticmethod
    async def async_remove(hass: HomeAssistant, entry_id: str) -> None:
        """Delete the stored file when the integration is removed."""
        await Store(hass, STORAGE_VERSION, _key(entry_id)).async_remove()
