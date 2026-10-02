"""Calendar per observation area: every event period as an entry."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import StreckenwachtConfigEntry
from .const import SUBENTRY_AREA
from .entity import StreckenwachtEntity
from .summary import CalendarItem, calendar_items, current_or_next


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StreckenwachtConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """One calendar per observation area."""
    for subentry in entry.get_subentries_of_type(SUBENTRY_AREA):
        async_add_entities(
            [AreaCalendar(entry, subentry, "calendar")],
            config_subentry_id=subentry.subentry_id,
        )


class AreaCalendar(StreckenwachtEntity, CalendarEntity):
    """All events of an area; days with several windows get several entries."""

    _attr_name = None  # the device name: "Streckenwacht <area>"

    @property
    def event(self) -> CalendarEvent | None:
        """The most severe active event, otherwise the next one."""
        item = current_or_next(self.area_events, dt_util.utcnow())
        return _to_calendar_event(item) if item else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Entries between start_date and end_date."""
        return [
            _to_calendar_event(item)
            for item in calendar_items(self.area_events, start_date, end_date)
        ]


def _to_calendar_event(item: CalendarItem) -> CalendarEvent:
    event = item.event
    # Attribution required by the licenses; proper names, so no translation needed.
    description = "\n\n".join(
        part for part in (event.description, event.attribution) if part
    )
    return CalendarEvent(
        start=item.start,
        end=item.end,
        summary=event.title,
        description=description,
        location=", ".join(p for p in (event.road, event.direction) if p) or None,
        uid=item.uid,
    )
