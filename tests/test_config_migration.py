"""Unit tests for settings migration between configuration versions."""

import json
import tempfile
import unittest
from pathlib import Path

from config import ConfigManager, CONFIG_VERSION, DEFAULT_CONFIG, LEGACY_DEFAULT_HOTKEYS


def _write_v1_config(directory: Path, hotkeys: dict) -> None:
    """Writes a config.json shaped the way version 1 saved it (no version field)."""
    payload = {
        "first_run": False,
        "target_language": "ja",
        "provider": "gemini",
        "hotkeys": hotkeys,
    }
    (directory / "config.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=4), encoding="utf-8"
    )


class TestConfigMigration(unittest.TestCase):

    def test_untouched_legacy_hotkeys_are_migrated(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _write_v1_config(directory, {
                name: {"key": key, "enabled": True}
                for name, key in LEGACY_DEFAULT_HOTKEYS.items()
            })

            config = ConfigManager(config_dir=directory)

            for name in LEGACY_DEFAULT_HOTKEYS:
                self.assertEqual(
                    config.get_hotkeys()[name]["key"],
                    DEFAULT_CONFIG["hotkeys"][name]["key"],
                    f"Hotkey '{name}' was not migrated",
                )
            self.assertEqual(config.get("config_version"), CONFIG_VERSION)

    def test_user_chosen_hotkeys_are_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _write_v1_config(directory, {
                "translate": {"key": "<ctrl>+<shift>+q", "enabled": True},
                "translate_en": {"key": "<ctrl>+<shift>+e", "enabled": True},
            })

            config = ConfigManager(config_dir=directory)

            # Deliberately chosen: untouched
            self.assertEqual(config.get_hotkeys()["translate"]["key"], "<ctrl>+<shift>+q")
            # Still on the old default: migrated
            self.assertEqual(
                config.get_hotkeys()["translate_en"]["key"],
                DEFAULT_CONFIG["hotkeys"]["translate_en"]["key"],
            )

    def test_migration_is_persisted_and_runs_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _write_v1_config(directory, {
                name: {"key": key, "enabled": True}
                for name, key in LEGACY_DEFAULT_HOTKEYS.items()
            })

            ConfigManager(config_dir=directory)

            saved = json.loads((directory / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["config_version"], CONFIG_VERSION)

            # A user who now picks a legacy combination on purpose keeps it
            reopened = ConfigManager(config_dir=directory)
            reopened.set_hotkey("translate", "<ctrl>+<shift>+t", True)
            again = ConfigManager(config_dir=directory)
            self.assertEqual(again.get_hotkeys()["translate"]["key"], "<ctrl>+<shift>+t")

    def test_other_saved_settings_survive_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _write_v1_config(directory, {
                name: {"key": key, "enabled": True}
                for name, key in LEGACY_DEFAULT_HOTKEYS.items()
            })

            config = ConfigManager(config_dir=directory)

            self.assertEqual(config.get("target_language"), "ja")
            self.assertEqual(config.get("provider"), "gemini")
            self.assertFalse(config.get("first_run"))

    def test_current_version_config_is_not_rewritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            payload = {
                "config_version": CONFIG_VERSION,
                "hotkeys": {"translate": {"key": "<ctrl>+<shift>+t", "enabled": True}},
            }
            (directory / "config.json").write_text(json.dumps(payload), encoding="utf-8")

            config = ConfigManager(config_dir=directory)
            self.assertEqual(config.get_hotkeys()["translate"]["key"], "<ctrl>+<shift>+t")


if __name__ == "__main__":
    unittest.main()
