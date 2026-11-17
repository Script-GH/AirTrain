"""Where this device is, for the app's network map.

Order: config override (lat/lon, or a "City, CC" / "lat,lon" location string) -> cached IP lookup ->
one-time IP geolocation lookup (if allowed). Never raises; returns None when nothing is known.
IP geolocation is city level at best and often shows the ISP's city.
"""

from __future__ import annotations

import json
import time
import urllib.request
from typing import Any

from .config import Config

CACHE_MAX_AGE_S = 30 * 24 * 3600
TIMEOUT_S = 3.0
# Free HTTPS endpoints that need no API key; tried in order.
PROVIDERS = (
    ("ipapi.co", "https://ipapi.co/json/", ("city", "country_code", "latitude", "longitude")),
    ("ipwho.is", "https://ipwho.is/", ("city", "country_code", "latitude", "longitude")),
)

# Coordinates for common cities so `--set location="Bengaluru, IN"` is enough to place a device.
CITIES: dict[str, tuple[float, float]] = {
    "bengaluru": (12.97, 77.59), "bangalore": (12.97, 77.59), "mumbai": (19.08, 72.88),
    "delhi": (28.61, 77.21), "new delhi": (28.61, 77.21), "hyderabad": (17.39, 78.49),
    "chennai": (13.08, 80.27), "pune": (18.52, 73.86), "kolkata": (22.57, 88.36),
    "ahmedabad": (23.02, 72.57), "nagpur": (21.15, 79.09), "jaipur": (26.91, 75.79),
    "kochi": (9.93, 76.27), "noida": (28.54, 77.39), "gurugram": (28.46, 77.03),
    "singapore": (1.35, 103.82), "dubai": (25.20, 55.27), "tokyo": (35.68, 139.69),
    "seoul": (37.57, 126.98), "sydney": (-33.87, 151.21), "london": (51.51, -0.13),
    "berlin": (52.52, 13.40), "frankfurt": (50.11, 8.68), "paris": (48.86, 2.35),
    "amsterdam": (52.37, 4.90), "new york": (40.71, -74.01), "san francisco": (37.77, -122.42),
    "seattle": (47.61, -122.33), "austin": (30.27, -97.74), "toronto": (43.65, -79.38),
    "sao paulo": (-23.55, -46.63), "são paulo": (-23.55, -46.63),
}


def _loc(city: str | None, country: str | None, lat: float | None, lon: float | None, source: str) -> dict[str, Any]:
    return {
        "city": city or None,
        "country": (country or "").upper() or None,
        "lat": None if lat is None else round(float(lat), 4),
        "lon": None if lon is None else round(float(lon), 4),
        "source": source,
    }


def _split_place(text: str) -> tuple[str | None, str | None]:
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if not parts:
        return None, None
    return parts[0], (parts[-1] if len(parts) > 1 else None)


def from_config(cfg: Config) -> dict[str, Any] | None:
    city, country = _split_place(cfg.location)
    if cfg.lat is not None and cfg.lon is not None:
        return _loc(city, country, cfg.lat, cfg.lon, "config")
    if not cfg.location.strip():
        return None
    try:  # "12.97,77.59"
        lat_s, lon_s = cfg.location.split(",")
        lat, lon = float(lat_s), float(lon_s)
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return _loc(None, None, lat, lon, "config")
    except ValueError:
        pass
    coords = CITIES.get((city or "").lower())
    return _loc(city, country, *(coords or (None, None)), "config")


def lookup_ip(timeout: float = TIMEOUT_S) -> dict[str, Any] | None:
    """One IP geolocation request (first provider that answers). None on any failure."""
    for name, url, (k_city, k_cc, k_lat, k_lon) in PROVIDERS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "airtrain-agent", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
            if data.get("error") or data.get("success") is False:
                continue
            lat, lon = data.get(k_lat), data.get(k_lon)
            if lat is None or lon is None:
                continue
            loc = _loc(data.get(k_city), data.get(k_cc), float(lat), float(lon), "ip")
            loc["provider"] = name
            return loc
        except Exception:  # network down, blocked, rate limited, bad JSON
            continue
    return None


def resolve_location(cfg: Config, allow_lookup: bool = True, save: bool = True) -> dict[str, Any] | None:
    """Best known location for this device. Looks up the IP at most once per cache period."""
    try:
        loc = from_config(cfg)
        if loc:
            return loc
        if not (allow_lookup and cfg.geo_lookup):
            return None
        cached = cfg.geo_cache or {}
        if cached.get("lat") is not None and time.time() - cached.get("fetched_at", 0) < CACHE_MAX_AGE_S:
            return {k: cached.get(k) for k in ("city", "country", "lat", "lon", "source")}
        loc = lookup_ip()
        if loc is None:
            return None
        cfg.geo_cache = {**loc, "fetched_at": time.time()}
        if save:
            cfg.save()
        return {k: loc[k] for k in ("city", "country", "lat", "lon", "source")}
    except Exception:
        return None


def describe(loc: dict[str, Any] | None) -> str:
    if not loc:
        return "unknown (set one with: airtrain config --set location=\"City, CC\")"
    place = ", ".join(x for x in (loc.get("city"), loc.get("country")) if x) or "coordinates only"
    coords = f" ({loc['lat']:.2f}, {loc['lon']:.2f})" if loc.get("lat") is not None else ", no coordinates"
    how = {"config": "from config", "ip": "from IP geolocation, city level"}.get(loc.get("source"), loc.get("source"))
    return f"{place}{coords}, {how}"
