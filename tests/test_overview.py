"""Tests for the overviews at the top of the settings forms."""

from __future__ import annotations

from custom_components.streckenwacht.const import Source
from custom_components.streckenwacht.model import EventType
from custom_components.streckenwacht.overview import (
    TEXTS,
    TYPE_NAMES,
    Zone,
    area_overview,
    entry_overview,
    place_name,
)

COMMUTE = {
    "latitude": 48.7758,
    "longitude": 9.1829,
    "radius": 15000.0,
    "sources": ["autobahn", "mobidata_bw", "stuttgart", "lms_bw"],
    "roads": ["A8", "A81"],
    "directions": [],
    "types": None,
    "jam_threshold": 10,
}


def test_area_overview_in_german() -> None:
    text = area_overview(
        COMMUTE,
        language="de",
        include_inrix=True,
        place="Zuhause",
        events=7,
        automations=["Stau morgens"],
    )
    assert text == (
        "**Eingerichtet**\n"
        "- Mittelpunkt: Zuhause, Radius 15 km\n"
        "- Quellen: Autobahn GmbH, MobiData BW, Stadt Stuttgart, "
        "Landesmeldestelle Baden-Württemberg\n"
        "- Autobahnen: A8, A81 (alle Richtungen, Stau zählt ab 10 min)\n"
        "- Meldungsarten: alle\n"
        "- Automationen: Stau morgens\n"
        "- Zurzeit 7 Meldungen"
    )


def test_coordinates_without_a_zone() -> None:
    text = area_overview(COMMUTE, language="en", include_inrix=True)
    assert "- Centre: 48.78, 9.18, radius 15 km\n" in text
    # Not loaded: no event count.
    assert "Currently" not in text


def test_small_radius_with_one_decimal() -> None:
    text = area_overview(COMMUTE | {"radius": 2500}, language="en", include_inrix=True)
    assert "radius 2.5 km" in text
    text = area_overview(COMMUTE | {"radius": 5000}, language="en", include_inrix=True)
    assert "radius 5 km" in text
    text = area_overview(COMMUTE | {"radius": 2500}, language="de", include_inrix=True)
    assert "Radius 2,5 km" in text


def test_directions_and_kinds() -> None:
    text = area_overview(
        COMMUTE
        | {
            "directions": ["Singen -> Stuttgart", "Stuttgart -> Heilbronn"],
            "types": ["accident", "closure"],
        },
        language="en",
        include_inrix=False,
    )
    # Without INRIX no threshold; kinds in their usual order.
    assert (
        "- Motorways: A8, A81 (direction Singen -> Stuttgart; Stuttgart -> Heilbronn)\n"
        in text
    )
    assert "- Kinds of reports: Closures, Accidents\n" in text
    # No traffic jams wanted: INRIX is not missing.
    assert "**Missing**" not in text


def test_without_inrix_jams_are_missing() -> None:
    text = area_overview(COMMUTE, language="de", include_inrix=False)
    assert text.endswith(
        "**Was fehlt**\n- Staus und Reisezeitverlust nur mit INRIX – in den "
        "Optionen von Streckenwacht einschalten."
    )


def test_inrix_not_missing_without_the_motorways() -> None:
    area = COMMUTE | {"sources": ["mobidata_bw", "stuttgart", "lms_bw"], "roads": []}
    text = area_overview(area, language="en", include_inrix=False)
    assert "Motorways" not in text
    assert "INRIX" not in text
    # Not chosen, but available here: named, not missing (often on purpose).
    assert "- Not chosen, but available here: Autobahn GmbH\n" in text
    assert "**Missing**" not in text


def test_sources_available_but_not_chosen() -> None:
    area = COMMUTE | {"sources": ["autobahn"]}
    text = area_overview(area, language="en", include_inrix=True)
    assert (
        "- Sources: Autobahn GmbH\n- Not chosen, but available here: MobiData BW, "
        "Stadt Stuttgart, Landesmeldestelle Baden-Württemberg\n"
    ) in text
    assert "**Missing**" not in text


def test_source_outside_its_region() -> None:
    # Moved to Berlin, Stuttgart still chosen.
    area = COMMUTE | {
        "latitude": 52.52,
        "longitude": 13.40,
        "radius": 5000,
        "sources": ["autobahn", "berlin", "stuttgart"],
    }
    text = area_overview(area, language="en", include_inrix=True)
    assert (
        "- Circle outside their region, nothing from them here: Stadt Stuttgart" in text
    )
    assert "nothing_covers" not in text


def test_nothing_covers_the_circle() -> None:
    # Paris: not even the Autobahn has anything there.
    area = COMMUTE | {
        "latitude": 48.86,
        "longitude": 2.35,
        "sources": ["autobahn"],
        "roads": ["A8"],
    }
    text = area_overview(area, language="de", include_inrix=True)
    assert text.endswith(
        "**Was fehlt**\n- Keine gewählte Quelle deckt diesen Kreis ab – hier "
        "kommen keine Meldungen."
    )


def test_unreachable_sources_of_the_area_only() -> None:
    text = area_overview(
        COMMUTE,
        language="en",
        include_inrix=True,
        unreachable={Source.STUTTGART, Source.DUISBURG},
    )
    assert "- Currently unreachable: Stadt Stuttgart (see Repairs)" in text
    assert "Duisburg" not in text


def test_many_automations_are_counted() -> None:
    text = area_overview(
        COMMUTE,
        language="en",
        include_inrix=True,
        automations=["a", "b", "c", "d", "e"],
        events=1,
    )
    assert "- Automations: a, b, c and 2 more\n- Currently 1 event" in text


def test_area_from_before_per_area_sources() -> None:
    area = {"latitude": 48.78, "longitude": 9.18, "roads": ["A8"]}
    text = area_overview(area, language="en", include_inrix=True)
    assert "- Sources: Autobahn GmbH\n" in text
    assert "radius 10 km" in text


def test_entry_overview() -> None:
    other = {"latitude": 52.5, "longitude": 13.4, "radius": 8000, "sources": ["berlin"]}
    text = entry_overview(
        [("Arbeitsweg", COMMUTE, 3), ("Berlin", other, 1)],
        language="de",
        unreachable={Source.BERLIN},
    )
    assert text == (
        "**Eingerichtet**\n"
        "- Arbeitsweg: Radius 15 km, 4 Quellen, zurzeit 3 Meldungen\n"
        "- Berlin: Radius 8 km, 1 Quelle, zurzeit 1 Meldung\n\n"
        "**Was fehlt**\n"
        "- Zurzeit nicht erreichbar: VIZ Berlin (siehe Reparaturen)"
    )


def test_entry_overview_not_loaded_and_without_areas() -> None:
    assert entry_overview([("Arbeitsweg", COMMUTE, None)], language="en") == (
        "**Set up**\n- Arbeitsweg: radius 15 km, 4 sources"
    )
    assert entry_overview([], language="en").startswith(
        "**Missing**\n- No observation area yet"
    )


def test_place_name_nearest_zone_containing_the_centre() -> None:
    zones = [
        Zone("Home", 48.7758, 9.1829, 0.1),
        Zone("Town", 48.78, 9.18, 5.0),
        Zone("Work", 48.70, 9.00, 0.2),
    ]
    assert place_name(48.7758, 9.1829, zones) == "Home"
    assert place_name(48.79, 9.20, zones) == "Town"
    assert place_name(48.0, 9.0, zones) is None


def test_texts_complete() -> None:
    assert TEXTS["de"].keys() == TEXTS["en"].keys()
    for names in TYPE_NAMES.values():
        assert set(names) == set(EventType)
