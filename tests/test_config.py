"""Unit tests for configuration manager and keyring integration."""

import unittest
import tempfile
import shutil
from pathlib import Path
from config import ConfigManager, DEFAULT_CONFIG


class TestConfigManager(unittest.TestCase):

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.config_mgr = ConfigManager(config_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_default_values(self):
        self.assertEqual(self.config_mgr.get("target_language"), "en")
        self.assertEqual(self.config_mgr.get("source_language"), "auto")
        self.assertTrue(self.config_mgr.get("restore_clipboard"))
        self.assertTrue(self.config_mgr.get("show_notifications"))

    def test_set_and_save(self):
        self.config_mgr.set("target_language", "ja")
        self.assertEqual(self.config_mgr.get("target_language"), "ja")

        # Reload from disk
        new_mgr = ConfigManager(config_dir=self.test_dir)
        self.assertEqual(new_mgr.get("target_language"), "ja")

    def test_hotkey_update(self):
        self.config_mgr.set_hotkey("translate", "<ctrl>+<alt>+t", enabled=True)
        hotkeys = self.config_mgr.get_hotkeys()
        self.assertEqual(hotkeys["translate"]["key"], "<ctrl>+<alt>+t")
        self.assertTrue(hotkeys["translate"]["enabled"])

    def test_reset_defaults(self):
        self.config_mgr.set("target_language", "fr")
        self.config_mgr.reset_defaults()
        self.assertEqual(self.config_mgr.get("target_language"), "en")


if __name__ == "__main__":
    unittest.main()
