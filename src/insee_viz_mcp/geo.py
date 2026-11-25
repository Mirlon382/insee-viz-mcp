"""France geometry: bundled simplified contours + Lambert-93 projection.

Contours: gregoiredavid/france-geojson (departements-version-simplifiee),
derived from IGN ADMIN-EXPRESS, licence ouverte. Simplified shapes are fine
for thematic mapping at national scale.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from importlib import resources

# --- Lambert-93 (EPSG:2154), spherical approximation -------------------------
_A = 6378137.0
_LAT0, _LON0 = math.radians(46.5), math.radians(3.0)
_LAT1, _LAT2 = math.radians(44.0), math.radians(49.0)
_X0, _Y0 = 700000.0, 6600000.0

_n = math.log(math.cos(_LAT1) / math.cos(_LAT2)) / math.log(
    math.tan(math.pi / 4 + _LAT2 / 2) / math.tan(math.pi / 4 + _LAT1 / 2)
)
_F = math.cos(_LAT1) * math.tan(math.pi / 4 + _LAT1 / 2) ** _n / _n
_rho0 = _A * _F / math.tan(math.pi / 4 + _LAT0 / 2) ** _n


def lambert93(lon: float, lat: float) -> tuple[float, float]:
    lam, phi = math.radians(lon), math.radians(lat)
    rho = _A * _F / math.tan(math.pi / 4 + phi / 2) ** _n
    x = _X0 + rho * math.sin(_n * (lam - _LON0))
    y = _Y0 + _rho0 - rho * math.cos(_n * (lam - _LON0))
    return x, y


@lru_cache(maxsize=4)
def features(level: str = "departement") -> tuple[dict, ...]:
    filename = {
        "departement": "departements.geojson",
        "region": "regions.geojson",
    }[level]
    raw = resources.files("insee_viz_mcp.data").joinpath(filename).read_text(encoding="utf-8")
    return tuple(json.loads(raw)["features"])


def _rings(geometry: dict) -> list[list[list[tuple[float, float]]]]:
    """Return polygons as lists of rings of (x, y) projected coordinates."""
    kind = geometry.get("type")
    coords = geometry.get("coordinates", [])
    if kind == "Polygon":
        polygons = [coords]
    elif kind == "MultiPolygon":
        polygons = coords
    else:
        return []
    out: list[list[list[tuple[float, float]]]] = []
    for polygon in polygons:
        rings = []
        for ring in polygon:
            rings.append([lambert93(pt[0], pt[1]) for pt in ring])
        out.append(rings)
    return out


def paths(level: str = "departement") -> list[tuple[str, list[list[list[tuple[float, float]]]]]]:
    """(code, polygons) for every feature, projected once."""
    result = []
    for feature in features(level):
        code = str(feature["properties"].get("code", "")).strip()
        result.append((code, _rings(feature["geometry"])))
    return result


def bounds(level: str = "departement") -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for _, polygons in paths(level):
        for polygon in polygons:
            for ring in polygon:
                for x, y in ring:
                    xs.append(x)
                    ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def names(level: str = "departement") -> dict[str, str]:
    return {str(f["properties"].get("code", "")).strip(): f["properties"].get("nom", "") for f in features(level)}
