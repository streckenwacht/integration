"""Remembers which events each area has seen, so restarts do not re-announce them."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

STORAGE_VERSION = 1
# At most one write per hour: the file holds every event of every area (a big
# city area: several hundred KB) and changes with nearly every poll while
# traffic jams come and go - too much for the SD cards many systems run on.
# Home Assistant writes pending data when it shuts down, and the entry does
# when it unloads; only a power cut can lose the last hour (some events are
# then announced a second time).
SAVE_DELAY = 60 * 60  # seconds


def _key(entry_id: str) -> str:
    return f"{DOMAIN}.{entry_id}.known_events"


class KnownEvents:
    """Per area: a fingerprint of its settings and the seen events per source.

    Layout: {subentry_id: {"fingerprint": str, "events": {source: {id: known}}}},
    known as in changes.KnownEvent.to_stored (older versions: title or [title, type]).
    """

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, _key(entry_id)
        )
        self._data: dict[str, Any] = {}
        self._pending = False

    async def async_load(self, keep: Iterable[str]) -> None:
        """Load stored data, dropping areas that no longer exist."""
        stored = await self._store.async_load() or {}
        keep = set(keep)
        self._data = {k: v for k, v in stored.items() if k in keep}
        if len(self._data) != len(stored):
            self._schedule_save()

    def get(self, subentry_id: str) -> dict[str, Any] | None:
        """Stored state of an area, if any."""
        return self._data.get(subentry_id)

    def set(self, subentry_id: str, value: dict[str, Any]) -> None:
        """Store the state of an area (written within the hour)."""
        self._data[subentry_id] = value
        self._schedule_save()

    async def async_flush(self) -> None:
        """Write pending changes now (before the entry unloads)."""
        if self._pending:
            self._pending = False
            await self._store.async_save(self._data)

    def _schedule_save(self) -> None:
        # Only the first change schedules: a later async_delay_save() would
        # postpone the write again, possibly for as long as changes keep coming.
        if not self._pending:
            self._pending = True
            self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    def _data_to_save(self) -> dict[str, Any]:
        self._pending = False
        return self._data

    @staticmethod
    async def async_remove(hass: HomeAssistant, entry_id: str) -> None:
        """Delete the stored file when the integration is removed."""
        await Store(hass, STORAGE_VERSION, _key(entry_id)).async_remove()
