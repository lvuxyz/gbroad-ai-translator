"""Unit tests for hotkey normalization, Win32 parsing, and manager configuration."""

import unittest
from core.hotkey_manager import (
    HotkeyManager,
    MOD_ALT,
    MOD_CONTROL,
    MOD_SHIFT,
    MOD_WIN,
    MOD_NOREPEAT,
)


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

    def test_parse_combo_letters_and_modifiers(self):
        modifiers, vk = HotkeyManager._parse_combo("<ctrl>+<alt>+t")
        self.assertEqual(modifiers, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT)
        self.assertEqual(vk, 0x54)  # VK_T

        modifiers, vk = HotkeyManager._parse_combo("ctrl+shift+e")
        self.assertEqual(modifiers, MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT)
        self.assertEqual(vk, 0x45)  # VK_E

        modifiers, vk = HotkeyManager._parse_combo("win+alt+space")
        self.assertEqual(modifiers, MOD_WIN | MOD_ALT | MOD_NOREPEAT)
        self.assertEqual(vk, 0x20)  # VK_SPACE

    def test_parse_combo_named_and_function_keys(self):
        self.assertEqual(HotkeyManager._parse_combo("ctrl+f1")[1], 0x70)   # VK_F1
        self.assertEqual(HotkeyManager._parse_combo("ctrl+f12")[1], 0x7B)  # VK_F12
        self.assertEqual(HotkeyManager._parse_combo("alt+enter")[1], 0x0D)
        self.assertEqual(HotkeyManager._parse_combo("ctrl+9")[1], 0x39)    # VK_9

    def test_parse_combo_always_requests_norepeat(self):
        """Holding the combination down must fire the pipeline once, not repeatedly."""
        for combo in ("ctrl+alt+t", "ctrl+shift+e", "alt+f4"):
            modifiers, _ = HotkeyManager._parse_combo(combo)
            self.assertTrue(modifiers & MOD_NOREPEAT, f"{combo} lacks MOD_NOREPEAT")

    def test_parse_combo_rejects_unusable_combinations(self):
        # A bare key would swallow that keystroke system-wide
        self.assertIsNone(HotkeyManager._parse_combo("t"))
        # Modifiers alone are not a hotkey
        self.assertIsNone(HotkeyManager._parse_combo("ctrl+shift"))
        # Two non-modifier keys cannot be registered together
        self.assertIsNone(HotkeyManager._parse_combo("ctrl+t+y"))
        # Unknown key name
        self.assertIsNone(HotkeyManager._parse_combo("ctrl+nosuchkey"))
        self.assertIsNone(HotkeyManager._parse_combo(""))

    def test_format_combo_for_display(self):
        self.assertEqual(HotkeyManager.format_combo("<ctrl>+<alt>+t"), "Ctrl + Alt + T")
        self.assertEqual(HotkeyManager.format_combo("ctrl+shift+e"), "Ctrl + Shift + E")
        self.assertEqual(HotkeyManager.format_combo("win+space"), "Win + Space")
        self.assertEqual(HotkeyManager.format_combo("ctrl+f5"), "Ctrl + F5")

    def test_every_shipped_default_hotkey_is_registrable(self):
        """A default that fails to parse would silently never register."""
        from config import DEFAULT_CONFIG

        for name, info in DEFAULT_CONFIG["hotkeys"].items():
            parsed = HotkeyManager._parse_combo(info["key"])
            self.assertIsNotNone(parsed, f"Default hotkey '{name}' ({info['key']}) is unusable")

    def test_shipped_defaults_avoid_the_ctrl_shift_collisions(self):
        """Ctrl+Shift+T/E/C/J collide with browser and IDE commands."""
        from config import DEFAULT_CONFIG, LEGACY_DEFAULT_HOTKEYS

        for name, legacy_key in LEGACY_DEFAULT_HOTKEYS.items():
            self.assertNotEqual(
                DEFAULT_CONFIG["hotkeys"][name]["key"],
                legacy_key,
                f"Default hotkey '{name}' still uses the retired combination {legacy_key}"
            )

    def test_stop_is_safe_before_start(self):
        mgr = HotkeyManager()
        mgr.stop()  # Must not raise when no listener thread exists
        self.assertFalse(mgr._is_running)


if __name__ == "__main__":
    unittest.main()
