"""Tests for the "new"/"ended" detection including traffic jam smoothing."""

from __future__ import annotations

from custom_components.streckenwacht.changes import (
    ENDED,
    NEW,
    KnownEvent,
    diff,
    learn,
)
from custom_components.streckenwacht.const import Source
from custom_components.streckenwacht.model import EventType, StreckenwachtEvent

THRESHOLD = 10
# About 1.1 km per 0.01 degrees of latitude.
LAT, LON = 48.70, 9.10


def jam(
    id_: str,
    delay: int | None = 15,
    lat: float = LAT,
    road: str = "A8",
    direction: str = "Karlsruhe",
) -> StreckenwachtEvent:
    return StreckenwachtEvent(
        id=id_,
        source=Source.AUTOBAHN,
        event_type=EventType.TRAFFIC_JAM,
        title=f"{road} Stau {id_}",
        road=road,
        direction=direction,
        latitude=lat,
        longitude=LON,
        delay_minutes=delay,
        upstream="inrix",
    )


def roadworks(id_: str) -> StreckenwachtEvent:
    return StreckenwachtEvent(
        id=id_,
        source=Source.AUTOBAHN,
        event_type=EventType.ROADWORKS,
        title=f"Baustelle {id_}",
        road="A8",
    )


def by_id(*events: StreckenwachtEvent) -> dict[str, StreckenwachtEvent]:
    return {e.id: e for e in events}


def run(known, *events, threshold=THRESHOLD):
    changes, new_known = diff(known, by_id(*events), threshold)
    return [(c.kind, c.attributes["id"]) for c in changes], new_known


def test_plain_new_and_ended() -> None:
    known = learn(by_id(roadworks("a")), THRESHOLD)
    changes, known = run(known, roadworks("b"))
    assert changes == [(NEW, "b"), (ENDED, "a")]
    assert set(known) == {"b"}


def test_ended_attributes() -> None:
    known = learn(by_id(roadworks("a")), THRESHOLD)
    changes, _ = diff(known, {}, THRESHOLD)
    assert changes[0].attributes == {
        "id": "a",
        "title": "Baustelle a",
        "type": "roadworks",
    }


def test_new_identifier_for_same_jam_is_silent() -> None:
    known = learn(by_id(jam("old")), THRESHOLD)
    changes, known = run(known, jam("new", lat=LAT + 0.02))
    assert changes == []
    assert set(known) == {"new"}
    assert known["new"].announced
    # ... and it still ends normally later on.
    changes, _ = run(known)
    assert changes == [(ENDED, "new")]


def test_jam_too_far_away_is_a_new_jam() -> None:
    known = learn(by_id(jam("old")), THRESHOLD)
    changes, _ = run(known, jam("new", lat=LAT + 0.1))  # about 11 km
    assert changes == [(NEW, "new"), (ENDED, "old")]


def test_jam_on_other_road_or_direction_is_a_new_jam() -> None:
    known = learn(by_id(jam("old")), THRESHOLD)
    changes, _ = run(known, jam("a", road="A81"), jam("b", direction="München"))
    assert changes == [(NEW, "a"), (NEW, "b"), (ENDED, "old")]


def test_continuation_picks_the_closest_vanished_jam() -> None:
    known = learn(by_id(jam("far", lat=LAT + 0.04), jam("near")), THRESHOLD)
    changes, known = run(known, jam("new", lat=LAT + 0.005))
    assert changes == [(ENDED, "far")]
    assert set(known) == {"new"}


def test_each_vanished_jam_continues_only_once() -> None:
    known = learn(by_id(jam("old")), THRESHOLD)
    changes, _ = run(known, jam("x", lat=LAT + 0.001), jam("y", lat=LAT + 0.002))
    assert changes == [(NEW, "y")]


def test_minor_jam_is_not_announced_until_it_reaches_the_threshold() -> None:
    known = learn({}, THRESHOLD)
    changes, known = run(known, jam("j", delay=3))
    assert changes == []
    assert not known["j"].announced
    changes, known = run(known, jam("j", delay=12))
    assert changes == [(NEW, "j")]
    changes, known = run(known, jam("j", delay=4))
    assert changes == []  # announced once, stays announced
    changes, _ = run(known)
    assert changes == [(ENDED, "j")]


def test_minor_jam_ends_silently() -> None:
    known = learn(by_id(jam("j", delay=2)), THRESHOLD)
    changes, _ = run(known)
    assert changes == []


def test_jam_without_delay_counts_as_minor() -> None:
    changes, _ = run({}, jam("j", delay=None))
    assert changes == []


def test_threshold_zero_announces_every_jam() -> None:
    changes, _ = run({}, jam("j", delay=None), threshold=0)
    assert changes == [(NEW, "j")]


def test_minor_jam_continued_under_new_identifier_announced_when_growing() -> None:
    known = learn(by_id(jam("old", delay=5)), THRESHOLD)
    changes, known = run(known, jam("new", delay=20, lat=LAT + 0.01))
    assert changes == [(NEW, "new")]
    changes, _ = run(known)
    assert changes == [(ENDED, "new")]


def test_stored_formats_of_older_versions() -> None:
    assert KnownEvent.from_stored("Titel") == KnownEvent("Titel", "")
    assert KnownEvent.from_stored(["Titel", "closure"]) == KnownEvent(
        "Titel", "closure"
    )
    stored = KnownEvent.from_event(jam("j"), announced=False).to_stored()
    assert KnownEvent.from_stored(stored) == KnownEvent.from_event(
        jam("j"), announced=False
    )


def test_old_entries_without_position_end_normally() -> None:
    known = {"old": KnownEvent.from_stored(["A8 Stau", "traffic_jam"])}
    changes, _ = run(known, jam("new"))
    assert changes == [(NEW, "new"), (ENDED, "old")]
