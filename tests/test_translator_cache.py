"""Unit tests for the in-memory translation cache."""

import time
import threading
import unittest
from core.translator import TranslationCache


class TestTranslationCache(unittest.TestCase):

    def setUp(self):
        self.cache = TranslationCache(max_entries=3, ttl_seconds=60.0)
        self.key = ("Xin chào", "auto", "en", "google", "translate", "natural")

    def test_miss_then_hit(self):
        self.assertIsNone(self.cache.get(self.key))
        self.cache.put(self.key, "Hello")
        self.assertEqual(self.cache.get(self.key), "Hello")

    def test_key_components_are_distinct(self):
        """Changing target language, provider, mode or style must miss."""
        self.cache.put(self.key, "Hello")

        variants = [
            ("Xin chào", "auto", "ja", "google", "translate", "natural"),   # language
            ("Xin chào", "auto", "en", "gemini", "translate", "natural"),   # provider
            ("Xin chào", "auto", "en", "google", "rewrite", "natural"),     # mode
            ("Xin chào", "auto", "en", "google", "translate", "formal"),    # style
            ("Chào bạn", "auto", "en", "google", "translate", "natural"),   # text
        ]
        for variant in variants:
            self.assertIsNone(self.cache.get(variant), f"{variant} should not hit")

    def test_expired_entry_is_dropped(self):
        cache = TranslationCache(max_entries=8, ttl_seconds=0.05)
        cache.put(self.key, "Hello")
        self.assertEqual(cache.get(self.key), "Hello")
        time.sleep(0.08)
        self.assertIsNone(cache.get(self.key))
        self.assertEqual(len(cache), 0)

    def test_evicts_least_recently_used_when_full(self):
        keys = [(f"text{i}", "auto", "en", "google", "translate", "natural") for i in range(4)]
        for i in range(3):
            self.cache.put(keys[i], f"result{i}")

        # Touch the oldest so it is no longer the least recently used
        self.assertEqual(self.cache.get(keys[0]), "result0")

        self.cache.put(keys[3], "result3")

        self.assertEqual(len(self.cache), 3)
        self.assertIsNone(self.cache.get(keys[1]), "keys[1] should have been evicted")
        self.assertEqual(self.cache.get(keys[0]), "result0")
        self.assertEqual(self.cache.get(keys[3]), "result3")

    def test_clear_empties_the_cache(self):
        self.cache.put(self.key, "Hello")
        self.cache.clear()
        self.assertEqual(len(self.cache), 0)
        self.assertIsNone(self.cache.get(self.key))

    def test_concurrent_access_stays_within_bounds(self):
        """Worker threads hit the cache, so it must not exceed its cap or corrupt."""
        cache = TranslationCache(max_entries=20, ttl_seconds=60.0)

        def hammer(offset: int) -> None:
            for i in range(100):
                key = (f"t{offset}-{i}", "auto", "en", "google", "translate", "natural")
                cache.put(key, f"r{offset}-{i}")
                cache.get(key)

        threads = [threading.Thread(target=hammer, args=(n,)) for n in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertLessEqual(len(cache), 20)


if __name__ == "__main__":
    unittest.main()
