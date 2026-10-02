"""Tests for the geometry helpers."""

from __future__ import annotations

import pytest

from custom_components.streckenwacht.geo import distance_to_geometry_km, haversine_km

STUTTGART_HBF = (48.7840, 9.1829)
KARLSRUHE_HBF = (48.9935, 8.4020)


def test_haversine_known_distance() -> None:
    assert haversine_km(*STUTTGART_HBF, *KARLSRUHE_HBF) == pytest.approx(61.3, abs=0.5)


def test_haversine_zero() -> None:
    assert haversine_km(*STUTTGART_HBF, *STUTTGART_HBF) == 0


def test_point_geometry_matches_haversine() -> None:
    lat, lon = KARLSRUHE_HBF
    geometry = {"type": "Point", "coordinates": [lon, lat]}
    assert distance_to_geometry_km(*STUTTGART_HBF, geometry) == pytest.approx(
        haversine_km(*STUTTGART_HBF, *KARLSRUHE_HBF), rel=0.01
    )


def test_line_measured_to_segment_not_vertices() -> None:
    # 20 km east-west line passing 1 km north of the point; both ends ~10 km away.
    lat, lon = 48.0, 9.0
    north = lat + 1 / 111.2
    geometry = {"type": "LineString", "coordinates": [[8.866, north], [9.134, north]]}
    assert distance_to_geometry_km(lat, lon, geometry) == pytest.approx(1.0, abs=0.05)


def test_multilinestring_uses_closest_part() -> None:
    geometry = {
        "type": "MultiLineString",
        "coordinates": [[[10.0, 50.0], [10.1, 50.0]], [[9.0, 48.0], [9.0, 48.01]]],
    }
    assert distance_to_geometry_km(48.0, 9.0, geometry) == pytest.approx(0, abs=0.01)


def test_geometry_collection() -> None:
    geometry = {
        "type": "GeometryCollection",
        "geometries": [{"type": "Point", "coordinates": [9.0, 48.0]}],
    }
    assert distance_to_geometry_km(48.0, 9.0, geometry) == pytest.approx(0, abs=0.01)


@pytest.mark.parametrize(
    "geometry",
    [
        None,
        {},
        {"type": "LineString", "coordinates": []},
        {"type": "LineString", "coordinates": [["a", "b"], None]},
        {"type": "Unknown", "coordinates": [9.0, 48.0]},
    ],
)
def test_unusable_geometry_returns_none(geometry: dict | None) -> None:
    assert distance_to_geometry_km(48.0, 9.0, geometry) is None
