"""Checks for location resolution: config overrides, IP lookup, caching and failures."""

from __future__ import annotations

import io
import json
import os
import tempfile
import time
import unittest
from unittest import mock

from airtrain_agent import geo
from airtrain_agent.config import Config
from airtrain_agent.coordinator import region_coords


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_urlopen(payloads):
    calls = []

    def urlopen(req, timeout=None):
        calls.append(req.full_url)
        item = payloads.pop(0)
        if isinstance(item, Exception):
            raise item
        return _Resp(json.dumps(item).encode())

    urlopen.calls = calls
    return urlopen


class Overrides(unittest.TestCase):
    def test_lat_lon_keys_win(self):
        cfg = Config(location="Home, IN", lat=12.9, lon=77.6)
        self.assertEqual(
            geo.resolve_location(cfg),
            {"city": "Home", "country": "IN", "lat": 12.9, "lon": 77.6, "source": "config"},
        )

    def test_known_city_gets_coordinates(self):
        loc = geo.resolve_location(Config(location="Bengaluru, IN"))
        self.assertEqual((loc["city"], loc["country"], loc["lat"], loc["lon"]), ("Bengaluru", "IN", 12.97, 77.59))

    def test_unknown_city_has_no_coordinates(self):
        loc = geo.resolve_location(Config(location="Smalltown, IN"))
        self.assertEqual(loc["city"], "Smalltown")
        self.assertIsNone(loc["lat"])

    def test_lat_lon_string(self):
        loc = geo.resolve_location(Config(location="18.52, 73.86"))
        self.assertEqual((loc["lat"], loc["lon"], loc["city"]), (18.52, 73.86, None))

    def test_override_skips_network(self):
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("no network expected")):
            self.assertEqual(geo.resolve_location(Config(location="Pune, IN"))["source"], "config")

    def test_config_set_validates_lat_lon(self):
        cfg = Config()
        cfg.set("lat", "12.5")
        self.assertEqual(cfg.lat, 12.5)
        with self.assertRaises(ValueError):
            cfg.set("lon", "200")
        cfg.set("lat", "")
        self.assertIsNone(cfg.lat)
        with self.assertRaises(KeyError):
            cfg.set("geo_cache", "{}")


class Lookup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"AIRTRAIN_HOME": self.tmp.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_lookup_and_cache(self):
        ok = {"city": "Nagpur", "country_code": "in", "latitude": 21.1463, "longitude": 79.0849}
        fake = fake_urlopen([ok])
        cfg = Config()
        with mock.patch("urllib.request.urlopen", fake):
            loc = geo.resolve_location(cfg)
            again = geo.resolve_location(cfg)  # served from the cache, no second request
        self.assertEqual(loc, {"city": "Nagpur", "country": "IN", "lat": 21.1463, "lon": 79.0849, "source": "ip"})
        self.assertEqual(again, loc)
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(cfg.geo_cache["provider"], "ipapi.co")

    def test_falls_back_to_second_provider(self):
        fake = fake_urlopen([OSError("blocked"), {"success": True, "city": "Pune", "country_code": "IN",
                                                  "latitude": 18.5, "longitude": 73.9}])
        with mock.patch("urllib.request.urlopen", fake):
            loc = geo.resolve_location(Config())
        self.assertEqual(loc["city"], "Pune")
        self.assertEqual(len(fake.calls), 2)

    def test_all_providers_fail_returns_none(self):
        fake = fake_urlopen([TimeoutError("slow"), {"success": False, "message": "rate limited"}])
        cfg = Config()
        with mock.patch("urllib.request.urlopen", fake):
            self.assertIsNone(geo.resolve_location(cfg))
        self.assertEqual(cfg.geo_cache, {})

    def test_bad_json_never_crashes(self):
        def urlopen(req, timeout=None):
            return _Resp(b"<html>not json")

        with mock.patch("urllib.request.urlopen", urlopen):
            self.assertIsNone(geo.resolve_location(Config()))

    def test_disabled_lookup(self):
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("no network expected")):
            self.assertIsNone(geo.resolve_location(Config(geo_lookup=False)))
            self.assertIsNone(geo.resolve_location(Config(), allow_lookup=False))

    def test_stale_cache_is_refreshed(self):
        old = {"city": "Old", "country": "IN", "lat": 1.0, "lon": 2.0, "source": "ip", "fetched_at": time.time() - 1e8}
        fake = fake_urlopen([{"city": "New", "country_code": "IN", "latitude": 3.0, "longitude": 4.0}])
        with mock.patch("urllib.request.urlopen", fake):
            self.assertEqual(geo.resolve_location(Config(geo_cache=old))["city"], "New")


class Regions(unittest.TestCase):
    def test_mock_regions_have_coordinates(self):
        from airtrain_agent.coordinator import _MOCK_SITES

        for _, _, region, _, _ in _MOCK_SITES:
            self.assertIsNotNone(region_coords(region)[0], region)
        self.assertEqual(region_coords("nowhere-1"), (None, None))


if __name__ == "__main__":
    unittest.main()
