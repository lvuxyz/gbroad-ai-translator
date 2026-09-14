"""Unit tests for Windows clipboard backup and restore operations."""

import unittest
from core.clipboard_manager import ClipboardManager


class TestClipboardManager(unittest.TestCase):

    def setUp(self):
        self.mgr = ClipboardManager()

    def test_set_and_get_unicode_text(self):
        test_str = "Kiểm tra Clipboard tiếng Việt 🇻🇳 với ký tự Unicode và Emoji 😊"
        success = self.mgr.set_clipboard_text(test_str)
        self.assertTrue(success)

        retrieved = self.mgr.get_clipboard_text()
        self.assertEqual(retrieved, test_str)

    def test_backup_and_restore_cycle(self):
        original_text = "Original clipboard text before translation"
        self.mgr.set_clipboard_text(original_text)

        # 1. Take snapshot
        snapshot = self.mgr.backup_clipboard()
        self.assertTrue(len(snapshot) > 0)

        # 2. Mutate clipboard
        self.mgr.set_clipboard_text("Temporary translated text replacing clipboard")
        self.assertEqual(self.mgr.get_clipboard_text(), "Temporary translated text replacing clipboard")

        # 3. Restore snapshot
        restore_success = self.mgr.restore_clipboard(snapshot)
        self.assertTrue(restore_success)

        # 4. Verify original text is back
        restored_text = self.mgr.get_clipboard_text()
        self.assertEqual(restored_text, original_text)


if __name__ == "__main__":
    unittest.main()
