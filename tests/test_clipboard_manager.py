"""Unit tests for Windows clipboard backup, restore, and key injection."""

import ctypes
import unittest
from core.clipboard_manager import (
    ClipboardManager,
    INPUT,
    KEYBDINPUT,
    MOUSEINPUT,
    VK_SHIFT,
)


class TestInputStructLayout(unittest.TestCase):
    """SendInput validates cbSize against its own struct and gives no other
    hint when the layout is wrong: it just returns 0 and nothing is typed."""

    def test_input_struct_matches_win32_layout(self):
        pointer_size = ctypes.sizeof(ctypes.c_void_p)
        expected = 40 if pointer_size == 8 else 28
        self.assertEqual(
            ctypes.sizeof(INPUT), expected,
            f"sizeof(INPUT) must be {expected} on this architecture, "
            f"or SendInput rejects every event with ERROR_INVALID_PARAMETER"
        )

    def test_union_is_sized_by_its_largest_member(self):
        """Dropping MOUSEINPUT from the union is what shrank INPUT before."""
        self.assertGreaterEqual(ctypes.sizeof(MOUSEINPUT), ctypes.sizeof(KEYBDINPUT))

    def test_send_key_event_is_accepted_by_windows(self):
        """A rejected event returns False rather than failing silently."""
        self.assertTrue(ClipboardManager._send_key_event(VK_SHIFT, key_up=True))


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
