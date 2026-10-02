"""Event entity per observation area: fires when an event appears or ends."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import StreckenwachtConfigEntry
from .const import (
    CONF_INCLUDE_INRIX,
    CONF_RADIUS,
    CONF_ROADS,
    DEFAULT_INCLUDE_INRIX,
    SUBENTRY_AREA,
    Source,
)
from .entity import StreckenwachtEntity
from .summary import event_attributes

if TYPE_CHECKING:
    from .known_events import KnownEvents

EVENT_NEW = "new"
EVENT_ENDED = "ended"
_SOURCES = {source.value for source in Source}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StreckenwachtConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """One event entity per observation area."""
    for subentry in entry.get_subentries_of_type(SUBENTRY_AREA):
        async_add_entities(
            [AreaChangeEvent(entry, subentry, "change")],
            config_subentry_id=subentry.subentry_id,
        )


def fingerprint(entry: StreckenwachtConfigEntry, subentry: ConfigSubentry) -> str:
    """Settings that change which events an area contains.

    If they differ from the stored ones, the known events are rebuilt silently
    instead of announcing dozens of "new" events after reconfiguring.
    """
    data = subentry.data
    return "|".join(
        str(part)
        for part in (
            data.get("latitude"),
            data.get("longitude"),
            data.get(CONF_RADIUS),
            ",".join(sorted(data.get(CONF_ROADS, ()))),
            entry.options.get(CONF_INCLUDE_INRIX, DEFAULT_INCLUDE_INRIX),
        )
    )


class AreaChangeEvent(StreckenwachtEntity, EventEntity):
    """Fires "new" for events that appear and "ended" for events that vanish.

    The first data of a source is learned silently, and so is everything after
    the area was changed. Sources that have not loaded yet (or failed at
    startup) keep their known events, so an outage never fires "ended".
    """

    _attr_translation_key = "change"

    def __init__(
        self, entry: StreckenwachtConfigEntry, subentry: ConfigSubentry, key: str
    ) -> None:
        super().__init__(entry, subentry, key)
        self._attr_event_types = [EVENT_NEW, EVENT_ENDED]
        self._fingerprint = fingerprint(entry, subentry)
        # source -> {event id: title}
        self._known: dict[Source, dict[str, str]] = {}

    @property
    def _store(self) -> KnownEvents:
        return self._entry.runtime_data.known_events

    async def async_added_to_hass(self) -> None:
        """Restore known events, then compare with the current data."""
        await super().async_added_to_hass()
        stored = self._store.get(self._subentry_id)
        if stored and stored.get("fingerprint") == self._fingerprint:
            self._known = {
                Source(source): dict(events)
                for source, events in stored.get("events", {}).items()
                if source in _SOURCES
            }
        self._process()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._process()

    @callback
    def _process(self) -> None:
        changed = False
        for source, coordinator in self._coordinators.items():
            if coordinator.data is None:
                continue  # never loaded: keep what we knew
            current = {
                event.id: event
                for event in coordinator.data.by_area.get(self._subentry_id, ())
            }
            known = self._known.get(source)
            if known is None:
                # First data of this source for this area: learn silently.
                self._known[source] = {i: e.title for i, e in current.items()}
                changed = True
                continue
            for event_id in sorted(current.keys() - known.keys()):
                self._fire(EVENT_NEW, event_attributes(current[event_id]))
            for event_id in sorted(known.keys() - current.keys()):
                self._fire(
                    EVENT_ENDED,
                    {"id": event_id, "title": known[event_id], "source": source.value},
                )
            if current.keys() != known.keys():
                self._known[source] = {i: e.title for i, e in current.items()}
                changed = True

        # Sources that were switched off: forget them without announcements.
        for source in set(self._known) - set(self._coordinators):
            del self._known[source]
            changed = True

        if changed:
            self._store.set(
                self._subentry_id,
                {
                    "fingerprint": self._fingerprint,
                    "events": {s.value: e for s, e in self._known.items()},
                },
            )

    def _fire(self, event_type: str, attributes: dict[str, Any]) -> None:
        self._trigger_event(event_type, attributes)
        self.async_write_ha_state()
