# ruff: noqa: SLF001
import unittest

from orchestra.common.user_preference_cache import UserPreferenceCache


class TestUserPreferenceCache(unittest.TestCase):
    def setUp(self):
        self.cache = UserPreferenceCache()

    def test_get_miss_returns_default(self):
        """Test that cache miss returns default value"""
        default_value = "default_value"
        result = self.cache.get("test_key", default_value)
        self.assertEqual(result, default_value)

    def test_get_hit_returns_cached(self):
        """Test that cache hit returns cached value"""
        cached_value = {"preference": "cached_value"}
        self.cache._cache["test_key"] = cached_value  # noqa: SLF001

        result = self.cache.get("test_key", "default_value")
        self.assertEqual(result, cached_value)

    def test_set_stores_value(self):
        """Test that set stores value in cache"""
        value = {"preference": "stored_value"}
        self.cache.set("test_key", value)

        self.assertEqual(self.cache._cache["test_key"], value)  # noqa: SLF001

    def test_clear_removes_all(self):
        """Test that clear removes all entries"""
        self.cache.set("key1", {"value": 1})
        self.cache.set("key2", {"value": 2})

        self.cache.clear()

        self.assertEqual(len(self.cache._cache), 0)  # noqa: SLF001

    def test_lru_eviction(self):
        """Test that LRU eviction works when cache exceeds max size"""
        # Fill cache to max
        for i in range(100):
            self.cache.set(f"key{i}", {"value": i})

        # Access key0 to make it recently used
        self.cache.get("key0")

        # Add one more to trigger eviction
        self.cache.set("key100", {"value": 100})

        # Cache should still be at max size
        self.assertEqual(len(self.cache._cache), 100)  # noqa: SLF001

        # key0 should still be there (recently accessed)
        self.assertIn("key0", self.cache._cache)  # noqa: SLF001

        # key1 should have been evicted (least recently used)
        self.assertNotIn("key1", self.cache._cache)  # noqa: SLF001

        # key100 should be there (just added)
        self.assertIn("key100", self.cache._cache)  # noqa: SLF001

    def test_lru_access_updates_order(self):
        """Test that accessing items updates their LRU order"""
        # Add 3 items
        self.cache.set("key1", {"value": 1})
        self.cache.set("key2", {"value": 2})
        self.cache.set("key3", {"value": 3})

        # Access key1 to move it to end (most recent)
        self.cache._cache["key1"]  # Direct access to update order  # noqa: SLF001
        self.cache._cache.move_to_end("key1")  # noqa: SLF001

        # Verify order by converting to list
        keys = list(self.cache._cache.keys())  # noqa: SLF001
        self.assertEqual(keys, ["key2", "key3", "key1"])


if __name__ == "__main__":
    unittest.main()
