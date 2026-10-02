"""Tests for the time-dependent views used by the entities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from custom_components.streckenwacht.const import Source
from custom_components.streckenwacht.model import EventType, Period, StreckenwachtEvent
from custom_components.streckenwacht.summary import (
    MAX_LISTED_EVENTS,
    active,
    calendar_items,
    current_or_next,
    disruptions,
    listed,
    max_delay,
)

NOW = datetime(2026, 10, 5, 12, tzinfo=UTC)
H = timedelta(hours=1)


def ev(
    id_: str,
    event_type: EventType = EventType.ROADWORKS,
    periods: tuple[Period, ...] = (),
    **kwargs,
) -> StreckenwachtEvent:
    return StreckenwachtEvent(
        id=id_,
        source=Source.AUTOBAHN,
        event_type=event_type,
        title=kwargs.pop("title", id_),
        periods=periods,
        **kwargs,
    )


RUNNING = Period(NOW - 24 * H, NOW + 24 * H)
PAST = Period(NOW - 48 * H, NOW - 24 * H)
FUTURE = Period(NOW + 10 * H, NOW + 12 * H)

ROADWORKS = ev("roadworks", EventType.ROADWORKS, (RUNNING,))
CLOSURE = ev("closure", EventType.CLOSURE, (RUNNING,))
ACCIDENT = ev("accident", EventType.ACCIDENT, (Period(NOW - H),))
JAM = ev("jam", EventType.TRAFFIC_JAM, (Period(NOW - H),), delay_minutes=25)
SMALL_JAM = ev("small_jam", EventType.TRAFFIC_JAM, (Period(NOW - H),), delay_minutes=5)
OLD_JAM = ev("old_jam", EventType.TRAFFIC_JAM, (PAST,), delay_minutes=90)
PLANNED = ev("planned", EventType.CLOSURE, (FUTURE,))


def test_active_sorted_by_severity() -> None:
    events = [ROADWORKS, JAM, PLANNED, CLOSURE, ACCIDENT, OLD_JAM]
    assert [e.id for e in active(events, NOW)] == [
        "accident",
        "closure",
        "jam",
        "roadworks",
    ]


def test_disruptions_exclude_plain_roadworks() -> None:
    events = [ROADWORKS, CLOSURE, JAM, PLANNED]
    assert [e.id for e in disruptions(events, NOW)] == ["closure", "jam"]
    assert disruptions([ROADWORKS], NOW) == []


def test_max_delay_is_the_largest_active() -> None:
    assert max_delay([SMALL_JAM, JAM, OLD_JAM], NOW) == (25, JAM)
    assert max_delay([ROADWORKS, OLD_JAM], NOW) == (0, None)


def test_listed_is_capped() -> None:
    events = [ev(f"e{i}") for i in range(MAX_LISTED_EVENTS + 5)]
    attributes = listed(events)
    assert len(attributes) == MAX_LISTED_EVENTS
    assert attributes[0]["id"] == "e0"
    assert "geometry" not in attributes[0]


def test_calendar_one_item_per_window() -> None:
    nights = ev(
        "nights",
        periods=(
            Period(NOW + 10 * H, NOW + 17 * H),
            Period(NOW + 34 * H, NOW + 41 * H),
            Period(NOW + 58 * H, NOW + 65 * H),
        ),
    )
    items = calendar_items([nights], NOW, NOW + 48 * H)
    assert [(i.start, i.end) for i in items] == [
        (NOW + 10 * H, NOW + 17 * H),
        (NOW + 34 * H, NOW + 41 * H),
    ]
    assert [i.uid for i in items] == ["nights#0", "nights#1"]


def test_calendar_open_ends_are_clipped_to_window() -> None:
    start, end = NOW - 24 * H, NOW + 24 * H
    items = calendar_items([JAM, ev("no_times")], start, end)
    by_id = {i.event.id: i for i in items}
    assert (by_id["jam"].start, by_id["jam"].end) == (NOW - H, end)
    assert (by_id["no_times"].start, by_id["no_times"].end) == (start, end)


def test_calendar_excludes_events_outside_window() -> None:
    assert calendar_items([OLD_JAM, PLANNED], NOW, NOW + 5 * H) == []


def test_current_or_next_prefers_active_and_most_severe() -> None:
    item = current_or_next([ROADWORKS, CLOSURE, PLANNED], NOW)
    assert item is not None
    assert item.event is CLOSURE
    assert (item.start, item.end) == (RUNNING.start, RUNNING.end)


def test_current_or_next_uses_the_next_window() -> None:
    nights = ev(
        "nights",
        periods=(Period(NOW - 20 * H, NOW - 13 * H), Period(NOW + 4 * H, NOW + 11 * H)),
    )
    item = current_or_next([nights, PLANNED], NOW)
    assert item is not None
    assert item.event is nights
    assert item.start == NOW + 4 * H
    assert item.uid == "nights#1"


def test_current_or_next_open_end_gets_nominal_end() -> None:
    item = current_or_next([JAM], NOW)
    assert item is not None
    assert item.start == NOW - H
    assert item.end > NOW


def test_current_or_next_nothing() -> None:
    assert current_or_next([OLD_JAM], NOW) is None
    assert current_or_next([], NOW) is None


def test_jam_threshold() -> None:
    unknown_delay = ev("unknown", EventType.TRAFFIC_JAM, (Period(NOW - H),))
    events = [CLOSURE, ACCIDENT, JAM, SMALL_JAM, unknown_delay]
    ids = lambda threshold: [e.id for e in disruptions(events, NOW, threshold)]  # noqa: E731
    # 0: every jam, also without a known delay
    assert ids(0) == ["accident", "closure", "jam", "small_jam", "unknown"]
    # 10: the 25-minute jam counts, the 5-minute and unknown ones do not
    assert ids(10) == ["accident", "closure", "jam"]
    # closures and accidents always count
    assert ids(60) == ["accident", "closure"]
