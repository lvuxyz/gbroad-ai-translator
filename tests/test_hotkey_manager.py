"""Unit tests for hotkey normalization and manager configuration."""

import unittest
from core.hotkey_manager import HotkeyManager


class TestHotkeyManager(unittest.TestCase):

    def test_normalize_combo(self):
        cases = [
            ("ctrl+shift+t", "<ctrl>+<shift>+t"),
            ("Ctrl + Shift + E", "<ctrl>+<shift>+e"),
            ("<ctrl>+<shift>+c", "<ctrl>+<shift>+c"),
            ("alt+shift+j", "<alt>+<shift>+j"),
            ("windows+ctrl+t", "<cmd>+<ctrl>+t"),
        ]
        for raw, expected in cases:
            self.assertEqual(HotkeyManager._normalize_combo(raw), expected)

    def test_hotkey_manager_initialization(self):
        mgr = HotkeyManager()
        self.assertFalse(mgr._is_running)


if __name__ == "__main__":
    unittest.main()
