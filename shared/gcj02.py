"""GCJ-02 (Amap/Baidu Mars coordinates) -> WGS-84 (OSM/MapLibre).

Only mainland-China coordinates need conversion (offset ~300-500m); overseas
coords like Tokyo are unaffected. Ported from vine's maps-cli
(~/Work/self/vine/apps/maps-cli/src/lib/gcj02.ts), which cites the Python
original and the research notes make-own-map.md; the constant table is fixed
by the WGS-84 / GCJ-02 datum definitions.
"""

from math import cos, pi, sin, sqrt

_A = 6378245.0  # WGS-84 semi-major axis (m)
_EE = 0.00669342162296594323  # WGS-84 eccentricity squared


def _transform_lat(x: float, y: float) -> float:
    r = -100 + 2 * x + 3 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * sqrt(abs(x))
    r += ((20 * sin(6 * x * pi) + 20 * sin(2 * x * pi)) * 2) / 3
    r += ((20 * sin(y * pi) + 40 * sin((y / 3) * pi)) * 2) / 3
    r += ((160 * sin((y / 12) * pi) + 320 * sin((y * pi) / 30)) * 2) / 3
    return r


def _transform_lng(x: float, y: float) -> float:
    r = 300 + x + 2 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * sqrt(abs(x))
    r += ((20 * sin(6 * x * pi) + 20 * sin(2 * x * pi)) * 2) / 3
    r += ((20 * sin(x * pi) + 40 * sin((x / 3) * pi)) * 2) / 3
    r += ((150 * sin((x / 12) * pi) + 300 * sin((x / 30) * pi)) * 2) / 3
    return r


def gcj02_to_wgs84(lng: float, lat: float) -> tuple[float, float]:
    """GCJ-02 -> WGS-84, returns (lng, lat)."""
    d_lat = _transform_lat(lng - 105, lat - 35)
    d_lng = _transform_lng(lng - 105, lat - 35)
    rad_lat = (lat / 180) * pi
    magic = sin(rad_lat)
    magic = 1 - _EE * magic * magic
    sqrt_magic = sqrt(magic)
    d_lat_final = (d_lat * 180) / (((_A * (1 - _EE)) / (magic * sqrt_magic)) * pi)
    d_lng_final = (d_lng * 180) / ((_A / sqrt_magic) * cos(rad_lat) * pi)
    return lng * 2 - (lng + d_lng_final), lat * 2 - (lat + d_lat_final)
