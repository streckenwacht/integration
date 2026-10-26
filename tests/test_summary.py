"""Tests for the time-dependent views used by the entities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from custom_components.streckenwacht.const import Source
from custom_components.streckenwacht.model import (
    EventType,
    ObservationArea,
    Period,
    StreckenwachtEvent,
)
from custom_components.streckenwacht.summary import (
    LIVE_SPAN,
    MAX_LISTED_EVENTS,
    active,
    calendar_items,
    current_or_next,
    delays_by_direction,
    disruptions,
    listed,
    map_events,
    max_delay,
    next_closure,
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


D = timedelta(days=1)


@pytest.mark.parametrize(
    ("periods", "counts"),
    [
        ((Period(NOW - 20 * D, NOW + 5 * D),), True),  # 25 days: short enough
        ((Period(NOW - 3 * D, NOW + 300 * D),), True),  # long, but new
        ((Period(NOW - 60 * D, NOW + 300 * D),), False),  # long-running
        ((Period(NOW - 60 * D, None),), False),  # open-ended and old
        ((Period(NOW - 2 * D, None),), True),  # open-ended but new
        ((Period(None, NOW + 300 * D),), False),  # unknown start
        ((), True),  # no times: listed by the source as current
        # Nightly closures of a long project: each night is a short window.
        ((Period(NOW - 90 * D, NOW - 89 * D), Period(NOW - H, NOW + 5 * H)), True),
    ],
)
def test_long_running_closures_only_count_while_new(
    periods: tuple[Period, ...], counts: bool
) -> None:
    closure = ev("c", EventType.CLOSURE, periods)
    assert bool(disruptions([closure], NOW)) is counts


def test_long_running_closures_stay_active_events() -> None:
    closure = ev("c", EventType.CLOSURE, (Period(NOW - 60 * D, NOW + 300 * D),))
    assert active([closure], NOW) == [closure]


def test_max_delay_is_the_largest_active() -> None:
    assert max_delay([SMALL_JAM, JAM, OLD_JAM], NOW) == (25, JAM)
    assert max_delay([ROADWORKS, OLD_JAM], NOW) == (0, None)


def test_delays_by_direction() -> None:
    def jam(id_: str, direction: str | None, minutes: int) -> StreckenwachtEvent:
        return ev(
            id_,
            EventType.TRAFFIC_JAM,
            (Period(NOW - H),),
            direction=direction,
            delay_minutes=minutes,
        )

    north = jam("north", "Karlsruhe -> Heidelberg", 14)
    north_small = jam("north_small", "Karlsruhe -> Heidelberg", 3)
    south = jam("south", "Heidelberg -> Karlsruhe", 5)
    ramp = jam("ramp", "AK Walldorf (aus Richtung Bucheneck)", 7)
    no_direction = jam("none", None, 30)
    old = ev(
        "old", EventType.TRAFFIC_JAM, (PAST,), direction="X -> Y", delay_minutes=90
    )
    assert delays_by_direction(
        [south, no_direction, north_small, ramp, old, north, ROADWORKS], NOW
    ) == {
        "Karlsruhe -> Heidelberg": 14,
        "Heidelberg -> Karlsruhe": 5,
    }
    # ramps and events without a direction are not listed, but the state
    # (max_delay) may still come from them
    assert max_delay([no_direction, north], NOW) == (30, no_direction)
    assert max_delay([ramp, south], NOW) == (7, ramp)
    assert delays_by_direction([ROADWORKS, OLD_JAM], NOW) == {}


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
    items = calendar_items([nights], NOW, NOW + 48 * H, NOW)
    assert [(i.start, i.end) for i in items] == [
        (NOW + 10 * H, NOW + 17 * H),
        (NOW + 34 * H, NOW + 41 * H),
    ]
    assert [i.uid for i in items] == ["nights#0", "nights#1"]


def test_calendar_open_ends_are_clipped_to_window() -> None:
    start, end = NOW - 24 * H, NOW + 24 * H
    open_roadworks = ev("open_roadworks", periods=(Period(NOW - 5 * H),))
    items = calendar_items([open_roadworks, ev("no_times")], start, end, NOW)
    by_id = {i.event.id: i for i in items}
    # roadworks "until further notice" fill the visible range
    assert (by_id["open_roadworks"].start, by_id["open_roadworks"].end) == (
        NOW - 5 * H,
        end,
    )
    assert (by_id["no_times"].start, by_id["no_times"].end) == (start, end)


def test_calendar_live_events_end_shortly_after_now() -> None:
    """A jam since 17:13 must not show up as "all day" for the rest of the month."""
    start, end = NOW - 24 * H, NOW + 30 * 24 * H
    no_start = ev("warning", EventType.WARNING)
    items = {i.event.id: i for i in calendar_items([JAM, no_start], start, end, NOW)}
    assert (items["jam"].start, items["jam"].end) == (NOW - H, NOW + LIVE_SPAN)
    assert (items["warning"].start, items["warning"].end) == (NOW, NOW + LIVE_SPAN)
    # a later window does not show the jam at all
    assert calendar_items([JAM], NOW + 24 * H, NOW + 48 * H, NOW) == []


def test_calendar_excludes_events_outside_window() -> None:
    assert calendar_items([OLD_JAM, PLANNED], NOW, NOW + 5 * H, NOW) == []


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
    assert item.end == NOW + LIVE_SPAN


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


def test_next_closure_is_the_earliest_upcoming_window() -> None:
    soon = ev("soon", EventType.CLOSURE, (PAST, Period(NOW + 2 * H, NOW + 4 * H)))
    later = ev("later", EventType.CLOSURE, (Period(NOW + 5 * H, None),))
    roadworks = ev("rw", EventType.ROADWORKS, (Period(NOW + H, NOW + 3 * H),))
    upcoming = next_closure([later, roadworks, soon, CLOSURE], NOW)
    assert upcoming is not None
    assert upcoming.event.id == "soon"
    assert (upcoming.start, upcoming.end) == (NOW + 2 * H, NOW + 4 * H)


def test_next_closure_only_within_the_horizon() -> None:
    far = ev("far", EventType.CLOSURE, (Period(NOW + 20 * 24 * H, None),))
    assert next_closure([far, CLOSURE], NOW) is None


def test_map_events_once_each_nearest_area_most_severe_first() -> None:
    def at(id_: str, event_type: EventType, lat: float) -> StreckenwachtEvent:
        return ev(id_, event_type, (RUNNING,), latitude=lat, longitude=9.0)

    north = ObservationArea("Nord", 49.0, 9.0, 20)
    south = ObservationArea("Süd", 48.8, 9.0, 20)
    shared = at("shared", EventType.ROADWORKS, 48.9)
    closure = at("closure", EventType.CLOSURE, 48.81)
    planned = ev("planned", EventType.CLOSURE, (FUTURE,), latitude=48.8, longitude=9.0)
    no_position = ev("nopos", EventType.ACCIDENT, (RUNNING,))
    items = map_events(
        {"n": [shared], "s": [shared, closure, planned, no_position]},
        {"n": north, "s": south},
        NOW,
    )
    assert [i.event.id for i in items] == ["closure", "shared"]
    assert items[1].areas == ("Nord", "Süd")
    assert items[0].distance_km == pytest.approx(1.1, abs=0.1)
    assert (
        map_events({"n": [shared, closure]}, {"n": north}, NOW, limit=1)[0].event.id
        == "closure"
    )
