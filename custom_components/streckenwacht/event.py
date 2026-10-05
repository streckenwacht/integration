"""Event entity per observation area: fires when an event appears or ends."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import StreckenwachtConfigEntry
from .changes import ENDED, NEW, KnownEvent, diff, learn
from .const import (
    CONF_AREA_SOURCES,
    CONF_DIRECTIONS,
    CONF_INCLUDE_INRIX,
    CONF_JAM_THRESHOLD,
    CONF_RADIUS,
    CONF_ROADS,
    DEFAULT_INCLUDE_INRIX,
    DEFAULT_JAM_THRESHOLD,
    Source,
)
from .coordinator import area_subentries
from .entity import StreckenwachtEntity

if TYPE_CHECKING:
    from .known_events import KnownEvents

EVENT_NEW = NEW
EVENT_ENDED = ENDED
_SOURCES = {source.value for source in Source}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StreckenwachtConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """One event entity per observation area."""
    for subentry in area_subentries(entry):
        async_add_entities(
            [AreaChangeEvent(entry, subentry, "change")],
            config_subentry_id=subentry.subentry_id,
        )


def fingerprint(entry: StreckenwachtConfigEntry, subentry: ConfigSubentry) -> str:
    """Settings that change which events an area contains or announces.

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
            ",".join(sorted(data.get(CONF_AREA_SOURCES) or ())),
            ",".join(sorted(data.get(CONF_DIRECTIONS, ()))),
            entry.options.get(CONF_INCLUDE_INRIX, DEFAULT_INCLUDE_INRIX),
            data.get(CONF_JAM_THRESHOLD, DEFAULT_JAM_THRESHOLD),
        )
    )


class AreaChangeEvent(StreckenwachtEntity, EventEntity):
    """Fires "new" for events that appear and "ended" for events that vanish.

    The first data of a source is learned silently, and so is everything after
    the area was changed. Sources that have not loaded yet (or failed at
    startup) keep their known events, so an outage never fires "ended".
    Traffic jams are smoothed, see changes.py.
    """

    _attr_translation_key = "change"

    def __init__(
        self, entry: StreckenwachtConfigEntry, subentry: ConfigSubentry, key: str
    ) -> None:
        super().__init__(entry, subentry, key)
        self._attr_event_types = [EVENT_NEW, EVENT_ENDED]
        self._fingerprint = fingerprint(entry, subentry)
        self._jam_threshold = int(
            subentry.data.get(CONF_JAM_THRESHOLD, DEFAULT_JAM_THRESHOLD)
        )
        self._known: dict[Source, dict[str, KnownEvent]] = {}

    @property
    def _store(self) -> KnownEvents:
        return self._entry.runtime_data.known_events

    async def async_added_to_hass(self) -> None:
        """Restore known events, then compare with the current data."""
        await super().async_added_to_hass()
        stored = self._store.get(self._subentry_id)
        if stored and stored.get("fingerprint") == self._fingerprint:
            self._known = {
                Source(source): {
                    i: KnownEvent.from_stored(v) for i, v in events.items()
                }
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
                self._known[source] = learn(current, self._jam_threshold)
                changed = True
                continue
            changes, new_known = diff(known, current, self._jam_threshold)
            for change in changes:
                attributes = change.attributes
                if change.kind == ENDED:
                    attributes = {**attributes, "source": source.value}
                # One state write per event, so automations see each of them.
                self._trigger_event(change.kind, attributes)
                self.async_write_ha_state()
            if new_known != known:
                self._known[source] = new_known
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
                    "events": {
                        s.value: {i: k.to_stored() for i, k in e.items()}
                        for s, e in self._known.items()
                    },
                },
            )
