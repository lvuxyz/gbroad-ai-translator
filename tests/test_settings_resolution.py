"""Unit tests for how a request's target language, mode and style are chosen.

Exercises the real ApplicationController method against a stub, so no
QApplication is needed.
"""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import main as main_module
from main import ApplicationController
from config import ConfigManager
from core.app_context import AppContext, EMPTY_CONTEXT


class TestSettingsResolution(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.config = ConfigManager(config_dir=Path(self._tmp.name))
        self.stub = SimpleNamespace(config=self.config)
        self.stub.resolve = ApplicationController._resolve_settings.__get__(self.stub)

        self._real_foreground = main_module.get_foreground_app
        self.set_foreground(EMPTY_CONTEXT)

    def tearDown(self):
        main_module.get_foreground_app = self._real_foreground
        self._tmp.cleanup()

    def set_foreground(self, context):
        main_module.get_foreground_app = lambda: context

    # --- two-way auto-detection ---
    def test_auto_swap_picks_the_opposite_side_of_the_pair(self):
        self.config.set("auto_swap", {"enabled": True, "primary": "vi", "secondary": "en"})

        target, _, _, _ = self.stub.resolve("Tôi đang học lập trình", None)
        self.assertEqual(target, "en")

        target, _, _, _ = self.stub.resolve("I am learning to code", None)
        self.assertEqual(target, "vi")

    def test_auto_swap_can_be_turned_off(self):
        self.config.set("auto_swap", {"enabled": False, "primary": "vi", "secondary": "en"})
        self.config.set("target_language", "ja")
        target, _, _, _ = self.stub.resolve("Tôi đang học", None)
        self.assertEqual(target, "ja")

    # --- precedence ---
    def test_hotkey_language_beats_everything(self):
        self.config.set("auto_swap", {"enabled": True, "primary": "vi", "secondary": "en"})
        self.config.set("app_profiles", {"chrome.exe": {"enabled": True, "target_language": "ja"}})
        self.set_foreground(AppContext("chrome.exe", "browser"))

        target, _, _, _ = self.stub.resolve("Tôi đang học", "ko")
        self.assertEqual(target, "ko")

    def test_profile_language_beats_auto_swap(self):
        """A profile naming a language must not be undone by auto-detection."""
        self.config.set("auto_swap", {"enabled": True, "primary": "vi", "secondary": "en"})
        self.config.set("app_profiles", {
            "chrome.exe": {"enabled": True, "target_language": "ja", "rewrite_style": "casual"}
        })
        self.set_foreground(AppContext("chrome.exe", "browser"))

        target, _, _, style = self.stub.resolve("Tôi đang học", None)
        self.assertEqual(target, "ja")
        self.assertEqual(style, "casual")

    def test_profile_without_a_language_still_allows_auto_swap(self):
        """Leaving target_language out is how a profile opts into auto-detection."""
        self.config.set("auto_swap", {"enabled": True, "primary": "vi", "secondary": "en"})
        self.config.set("app_profiles", {
            "discord.exe": {"enabled": True, "rewrite_style": "casual", "mode": "rewrite"}
        })
        self.set_foreground(AppContext("discord.exe", "chat"))

        target, _, mode, style = self.stub.resolve("Tôi đang học", None)
        self.assertEqual(target, "en", "auto-detect should still apply")
        self.assertEqual(mode, "rewrite")
        self.assertEqual(style, "casual")

    def test_profile_carries_mode_and_style(self):
        self.config.set("auto_swap", {"enabled": False, "primary": "vi", "secondary": "en"})
        self.config.set("app_profiles", {
            "outlook.exe": {"enabled": True, "target_language": "en",
                            "mode": "rewrite", "rewrite_style": "formal"}
        })
        self.set_foreground(AppContext("outlook.exe", "mail"))

        target, _, mode, style = self.stub.resolve("Chào anh", None)
        self.assertEqual((target, mode, style), ("en", "rewrite", "formal"))

    def test_disabled_profile_is_ignored(self):
        self.config.set("auto_swap", {"enabled": False, "primary": "vi", "secondary": "en"})
        self.config.set("target_language", "th")
        self.config.set("app_profiles", {
            "code.exe": {"enabled": False, "target_language": "ja"}
        })
        self.set_foreground(AppContext("code.exe", "editor"))

        target, _, _, _ = self.stub.resolve("Tôi đang học", None)
        self.assertEqual(target, "th")

    def test_unknown_application_uses_the_defaults(self):
        self.config.set("auto_swap", {"enabled": False, "primary": "vi", "secondary": "en"})
        self.config.set("target_language", "fr")
        self.set_foreground(AppContext("unlisted.exe", "window"))

        target, _, _, _ = self.stub.resolve("Tôi đang học", None)
        self.assertEqual(target, "fr")


if __name__ == "__main__":
    unittest.main()
