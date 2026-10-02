"""Tests for the common data model."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from custom_components.streckenwacht.const import Source
from custom_components.streckenwacht.model import (
    EventType,
    ObservationArea,
    Period,
    StreckenwachtEvent,
)


def dt(day: int, hour: int = 0) -> datetime:
    return datetime(2026, 10, day, hour, tzinfo=UTC)


def make_event(**kwargs) -> StreckenwachtEvent:
    defaults = {
        "id": "mobidata_bw:1",
        "source": Source.MOBIDATA_BW,
        "event_type": EventType.ROADWORKS,
        "title": "Test",
    }
    return StreckenwachtEvent(**(defaults | kwargs))


def test_period_bounds() -> None:
    period = Period(dt(5), dt(7))
    assert not period.contains(dt(4, 23))
    assert period.contains(dt(5))
    assert period.contains(dt(6, 12))
    assert not period.contains(dt(7))  # end is exclusive


def test_open_period() -> None:
    assert Period().contains(dt(1))
    assert Period(start=dt(5)).contains(dt(30))
    assert Period(end=dt(5)).contains(dt(1))


def test_event_without_periods_is_active() -> None:
    event = make_event()
    assert event.is_active(dt(1))
    assert event.start is None
    assert event.end is None


def test_event_with_multiple_windows() -> None:
    event = make_event(
        periods=(Period(dt(5, 10), dt(5, 16)), Period(dt(6, 8), dt(6, 16)))
    )
    assert event.start == dt(5, 10)
    assert event.end == dt(6, 16)
    assert event.is_active(dt(5, 12))
    assert not event.is_active(dt(5, 20))  # between the windows
    assert event.is_active(dt(6, 9))


def test_open_ended_period_has_no_end() -> None:
    event = make_event(periods=(Period(dt(1), dt(2)), Period(dt(3))))
    assert event.end is None


def test_attribution_per_source() -> None:
    assert "CC BY 4.0" in make_event(source=Source.STUTTGART).attribution


def test_inrix_attribution() -> None:
    event = make_event(source=Source.AUTOBAHN, upstream="inrix")
    assert event.attribution == "Die Autobahn GmbH des Bundes; Verkehrslage: INRIX"
    assert "INRIX" not in make_event(source=Source.AUTOBAHN).attribution


def test_geometry_not_in_repr() -> None:
    event = make_event(geometry={"type": "Point", "coordinates": [9.0, 48.0]})
    assert "coordinates" not in repr(event)


AREA = ObservationArea(
    name="Arbeitsweg",
    latitude=48.0,
    longitude=9.0,
    radius_km=5,
    roads=frozenset({"A8"}),
)


@pytest.mark.parametrize(
    ("event_kwargs", "expected"),
    [
        # geometry within radius
        ({"geometry": {"type": "Point", "coordinates": [9.0, 48.02]}}, True),
        # geometry outside radius
        ({"geometry": {"type": "Point", "coordinates": [9.0, 48.2]}}, False),
        # no geometry: fall back to latitude/longitude
        ({"latitude": 48.01, "longitude": 9.0}, True),
        # no location at all
        ({}, False),
        # Autobahn event on a selected road
        (
            {
                "source": Source.AUTOBAHN,
                "road": "A8",
                "latitude": 48.0,
                "longitude": 9.0,
            },
            True,
        ),
        # Autobahn event on a road the area does not watch, even if nearby
        (
            {
                "source": Source.AUTOBAHN,
                "road": "A81",
                "latitude": 48.0,
                "longitude": 9.0,
            },
            False,
        ),
    ],
)
def test_area_contains(event_kwargs: dict, expected: bool) -> None:
    assert AREA.contains(make_event(**event_kwargs)) is expected
