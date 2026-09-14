"""Global Hotkey Manager.

Uses pynput.keyboard.GlobalHotKeys to listen for system-wide shortcuts
and provides dynamic reconfiguration without application restarts.
"""

from typing import Callable, Dict, Any, Optional
from pynput import keyboard
from config import get_config
from utils.logger import get_logger

logger = get_logger()


class HotkeyManager:
    """Manages system-wide global hotkeys and action dispatching."""

    def __init__(self, action_callback: Optional[Callable[[Optional[str]], None]] = None):
        """Args:

        action_callback: Function called when a translation hotkey triggers.
        Receives optional target_language code override (e.g. 'en', 'zh-CN',
        'ja', or None for default).
        """
        self.config = get_config()
        self.action_callback = action_callback
        self._listener: Optional[keyboard.GlobalHotKeys] = None
        self._is_running = False

    def start(self) -> bool:
        """Starts the global hotkey listener with configured shortcuts."""
        self.stop()

        hotkey_mapping: Dict[str, Callable[[], None]] = {}
        configured_hotkeys = self.config.get_hotkeys()

        for name, info in configured_hotkeys.items():
            if not info.get("enabled", True):
                continue

            key_combo = info.get("key", "").strip()
            if not key_combo:
                continue

            target_override = info.get("target", None)

            # Create closure for each hotkey
            def make_handler(target: Optional[str]):
                return lambda: self._on_hotkey_triggered(target)

            try:
                # Normalize key combo syntax for pynput (lowercase, enclose in <>)
                normalized_combo = self._normalize_combo(key_combo)
                hotkey_mapping[normalized_combo] = make_handler(target_override)
                logger.info("Registered hotkey '%s' (%s) -> target: %s", name, normalized_combo, target_override or "default")
            except Exception as e:
                logger.error("Failed to parse hotkey '%s' (%s): %s", name, key_combo, e)

        if not hotkey_mapping:
            logger.warning("No hotkeys were registered")
            return False

        try:
            self._listener = keyboard.GlobalHotKeys(hotkey_mapping)
            self._listener.start()
            self._is_running = True
            logger.info("Global hotkey listener started with %d shortcuts", len(hotkey_mapping))
            return True
        except Exception as e:
            logger.error("Failed to start GlobalHotKeys listener: %s", e)
            self._is_running = False
            return False

    def stop(self) -> None:
        """Stops the active hotkey listener."""
        if self._listener is not None:
            try:
                self._listener.stop()
                logger.info("Global hotkey listener stopped")
            except Exception as e:
                logger.warning("Error stopping hotkey listener: %s", e)
            finally:
                self._listener = None
                self._is_running = False

    def reload(self) -> bool:
        """Reloads hotkey configurations from config and restarts listener."""
        logger.info("Reloading hotkeys configuration")
        return self.start()

    def _on_hotkey_triggered(self, target_language: Optional[str]) -> None:
        """Dispatches hotkey trigger to application callback."""
        logger.info("Global hotkey triggered (target override: %s)", target_language)
        if self.action_callback:
            try:
                self.action_callback(target_language)
            except Exception as e:
                logger.error("Error executing hotkey action callback: %s", e)

    @staticmethod
    def _normalize_combo(combo: str) -> str:
        """Normalizes shortcut string to pynput format (e.g. 'ctrl+shift+t' -> '<ctrl>+<shift>+t')."""
        parts = [p.strip().lower() for p in combo.replace("+", " ").split()]
        normalized = []
        for p in parts:
            p_clean = p.replace("<", "").replace(">", "")
            if p_clean in ("ctrl", "control"):
                normalized.append("<ctrl>")
            elif p_clean in ("shift",):
                normalized.append("<shift>")
            elif p_clean in ("alt",):
                normalized.append("<alt>")
            elif p_clean in ("cmd", "win", "windows", "super"):
                normalized.append("<cmd>")
            else:
                normalized.append(p_clean)
        return "+".join(normalized)
