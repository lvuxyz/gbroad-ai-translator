"""Unit tests for SQLite database history manager."""

import unittest
import tempfile
import shutil
from pathlib import Path
from database import DatabaseManager


class TestDatabaseManager(unittest.TestCase):

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.db = DatabaseManager(db_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_add_and_search(self):
        item_id = self.db.add_translation(
            source_text="Tôi đang học lập trình",
            translated_text="I am learning programming",
            source_language="vi",
            target_language="en",
            provider="gemini",
            privacy_mode=False,
            history_enabled=True
        )
        self.assertIsNotNone(item_id)
        self.assertEqual(self.db.get_count(), 1)

        # Search by keyword
        results = self.db.search_translations("lập trình")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["translated_text"], "I am learning programming")

        # Search by target keyword
        results2 = self.db.search_translations("programming")
        self.assertEqual(len(results2), 1)

    def test_privacy_mode_prevents_saving(self):
        item_id = self.db.add_translation(
            source_text="Sensitive password 12345",
            translated_text="Mật khẩu nhạy cảm",
            source_language="en",
            target_language="vi",
            provider="gemini",
            privacy_mode=True,
            history_enabled=True
        )
        self.assertIsNone(item_id)
        self.assertEqual(self.db.get_count(), 0)

    def test_history_disabled_prevents_saving(self):
        item_id = self.db.add_translation(
            source_text="Hello world",
            translated_text="Xin chào",
            source_language="en",
            target_language="vi",
            provider="google",
            privacy_mode=False,
            history_enabled=False
        )
        self.assertIsNone(item_id)
        self.assertEqual(self.db.get_count(), 0)

    def test_delete_and_clear(self):
        id1 = self.db.add_translation("Xin chào", "Hello", "vi", "en", "google")
        id2 = self.db.add_translation("Tạm biệt", "Goodbye", "vi", "en", "google")
        self.assertEqual(self.db.get_count(), 2)

        self.db.delete_translation(id1)
        self.assertEqual(self.db.get_count(), 1)

        self.db.clear_history()
        self.assertEqual(self.db.get_count(), 0)


if __name__ == "__main__":
    unittest.main()
