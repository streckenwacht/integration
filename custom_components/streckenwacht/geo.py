"""Geometry helpers. Pure Python, no Home Assistant imports."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from itertools import pairwise
from math import asin, cos, hypot, radians, sin, sqrt
from typing import Any

EARTH_RADIUS_KM = 6371.0088
_KM_PER_DEGREE = radians(1) * EARTH_RADIUS_KM


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance between two WGS84 points in km."""
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def distance_to_geometry_km(
    lat: float, lon: float, geometry: dict[str, Any] | None
) -> float | None:
    """Return the shortest distance from a point to a GeoJSON geometry in km.

    Lines are measured to their segments, not just their vertices, so a long
    straight motorway section passing close by is found even if both ends are far
    away. Uses a local flat-earth projection around the point, which is accurate
    enough for observation radii up to roughly 100 km.

    Returns None if the geometry is missing or contains no usable coordinates.
    """
    kx = cos(radians(lat)) * _KM_PER_DEGREE
    ky = _KM_PER_DEGREE
    best: float | None = None
    for line in _lines(geometry):
        points = [((p[0] - lon) * kx, (p[1] - lat) * ky) for p in line]
        if len(points) == 1:
            dist = hypot(*points[0])
        else:
            dist = min(_origin_to_segment(a, b) for a, b in pairwise(points))
        if best is None or dist < best:
            best = dist
    return best


def _origin_to_segment(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Distance from (0, 0) to the segment a-b in a planar coordinate system."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return hypot(*a)
    t = max(0.0, min(1.0, -(a[0] * dx + a[1] * dy) / length_sq))
    return hypot(a[0] + t * dx, a[1] + t * dy)


def _lines(geometry: dict[str, Any] | None) -> Iterator[list[Sequence[float]]]:
    """Yield every coordinate sequence of a GeoJSON geometry as (lon, lat) lists."""
    if not isinstance(geometry, dict):
        return
    kind = geometry.get("type")
    coords = geometry.get("coordinates")
    if kind == "GeometryCollection":
        for part in geometry.get("geometries") or []:
            yield from _lines(part)
        return
    if kind == "Point":
        sequences = [[coords]]
    elif kind in ("MultiPoint", "LineString"):
        sequences = [coords]
    elif kind in ("MultiLineString", "Polygon"):
        sequences = coords
    elif kind == "MultiPolygon":
        sequences = [ring for polygon in coords or [] for ring in polygon]
    else:
        return
    for sequence in sequences or []:
        valid = [p for p in sequence or [] if _is_position(p)]
        if valid:
            yield valid


def _is_position(value: Any) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) >= 2
        and all(isinstance(v, (int, float)) for v in value[:2])
    )
