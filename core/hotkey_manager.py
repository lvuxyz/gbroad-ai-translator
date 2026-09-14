"""Global Hotkey Manager built on the Win32 RegisterHotKey API.

A keyboard-hook listener observes keys without consuming them, so the
foreground application receives the combination too: pressing Ctrl+Shift+T in
Chrome would translate the selection *and* reopen the last closed tab. The
operating system consumes a combination registered through RegisterHotKey, so
the foreground application never sees it.

RegisterHotKey delivers WM_HOTKEY to the message queue of the thread that
registered it, which is why registration and the message pump both live on the
listener thread.
"""

import ctypes
import threading
from ctypes import wintypes
from typing import Callable, Dict, Any, Optional, Tuple, List

from config import get_config
from utils.logger import get_logger

logger = get_logger()

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = ctypes.c_int  # Signed: returns -1 on failure
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostThreadMessageW.restype = wintypes.BOOL

# Win32 modifier flags accepted by RegisterHotKey
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000  # Fire once per press instead of repeating while held

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

ERROR_HOTKEY_ALREADY_REGISTERED = 1409

MODIFIER_FLAGS: Dict[str, int] = {
    "<ctrl>": MOD_CONTROL,
    "<shift>": MOD_SHIFT,
    "<alt>": MOD_ALT,
    "<cmd>": MOD_WIN,
}

# Keys that have no single-character spelling
NAMED_VK_CODES: Dict[str, int] = {
    "space": 0x20,
    "enter": 0x0D,
    "return": 0x0D,
    "tab": 0x09,
    "esc": 0x1B,
    "escape": 0x1B,
    "backspace": 0x08,
    "delete": 0x2E,
    "insert": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "page_up": 0x21,
    "pageup": 0x21,
    "page_down": 0x22,
    "pagedown": 0x22,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
}
for _fn in range(1, 25):
    NAMED_VK_CODES[f"f{_fn}"] = 0x6F + _fn  # VK_F1 == 0x70


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
        self.failed_hotkeys: List[str] = []
        self._thread: Optional[threading.Thread] = None
        self._thread_id: Optional[int] = None
        self._ready = threading.Event()
        self._registered_count = 0
        self._is_running = False

    def start(self) -> bool:
        """Starts the global hotkey listener with configured shortcuts."""
        self.stop()
        self.failed_hotkeys = []

        # hotkey_id -> (modifiers, vk_code, target_language, display_name)
        bindings: Dict[int, Tuple[int, int, Optional[str], str]] = {}
        next_id = 1

        for name, info in self.config.get_hotkeys().items():
            if not info.get("enabled", True):
                continue

            key_combo = info.get("key", "").strip()
            if not key_combo:
                continue

            parsed = self._parse_combo(key_combo)
            if parsed is None:
                logger.error("Failed to parse hotkey '%s' (%s)", name, key_combo)
                self.failed_hotkeys.append(key_combo)
                continue

            modifiers, vk_code = parsed
            bindings[next_id] = (modifiers, vk_code, info.get("target"), key_combo)
            next_id += 1

        if not bindings:
            logger.warning("No hotkeys were registered")
            return False

        self._ready.clear()
        self._thread = threading.Thread(
            target=self._message_loop,
            args=(bindings,),
            name="HotkeyListener",
            daemon=True
        )
        self._thread.start()

        # Registration happens on the listener thread; wait for its verdict
        if not self._ready.wait(timeout=5.0):
            logger.error("Hotkey listener did not become ready within 5 seconds")
            return False

        self._is_running = self._registered_count > 0
        return self._is_running

    def stop(self) -> None:
        """Stops the active hotkey listener and releases its registrations."""
        if self._thread is None:
            return

        if self._thread_id is not None:
            # Breaks GetMessageW, letting the loop unregister and exit
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)

        self._thread.join(timeout=3.0)
        if self._thread.is_alive():
            logger.warning("Hotkey listener thread did not stop within 3 seconds")
        else:
            logger.info("Global hotkey listener stopped")

        self._thread = None
        self._thread_id = None
        self._is_running = False
        self._registered_count = 0

    def reload(self) -> bool:
        """Reloads hotkey configurations from config and restarts listener."""
        logger.info("Reloading hotkeys configuration")
        return self.start()

    def _message_loop(self, bindings: Dict[int, Tuple[int, int, Optional[str], str]]) -> None:
        """Registers every hotkey, then pumps WM_HOTKEY until asked to quit."""
        self._thread_id = kernel32.GetCurrentThreadId()
        registered: Dict[int, Optional[str]] = {}

        try:
            for hotkey_id, (modifiers, vk_code, target, display) in bindings.items():
                if user32.RegisterHotKey(None, hotkey_id, modifiers, vk_code):
                    registered[hotkey_id] = target
                    logger.info(
                        "Registered hotkey '%s' (mod=0x%04X vk=0x%02X) -> target: %s",
                        display, modifiers, vk_code, target or "default"
                    )
                else:
                    err = ctypes.get_last_error()
                    if err == ERROR_HOTKEY_ALREADY_REGISTERED:
                        logger.error(
                            "Hotkey '%s' is already owned by another application", display
                        )
                    else:
                        logger.error(
                            "Failed to register hotkey '%s' (Win32 error %d)", display, err
                        )
                    self.failed_hotkeys.append(display)

            self._registered_count = len(registered)
            if registered:
                logger.info("Global hotkey listener started with %d shortcuts", len(registered))
        finally:
            # Report the outcome even if registration raised, so start() unblocks
            self._ready.set()

        if not registered:
            return

        msg = wintypes.MSG()
        try:
            while True:
                result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if result in (0, -1):  # WM_QUIT, or an error we cannot recover from
                    break
                if msg.message == WM_HOTKEY:
                    self._on_hotkey_triggered(registered.get(int(msg.wParam)))
        finally:
            for hotkey_id in registered:
                user32.UnregisterHotKey(None, hotkey_id)

    def _on_hotkey_triggered(self, target_language: Optional[str]) -> None:
        """Dispatches hotkey trigger to application callback."""
        logger.info("Global hotkey triggered (target override: %s)", target_language)
        if self.action_callback:
            try:
                self.action_callback(target_language)
            except Exception as e:
                # Never let a callback failure kill the message pump
                logger.error("Error executing hotkey action callback: %s", e)

    @staticmethod
    def _normalize_combo(combo: str) -> str:
        """Normalizes shortcut string to canonical format (e.g. 'ctrl+shift+t' -> '<ctrl>+<shift>+t')."""
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

    @staticmethod
    def format_combo(combo: str) -> str:
        """Renders a stored combo for display (e.g. '<ctrl>+<alt>+t' -> 'Ctrl + Alt + T')."""
        labels = {"<ctrl>": "Ctrl", "<shift>": "Shift", "<alt>": "Alt", "<cmd>": "Win"}
        parts = []
        for part in HotkeyManager._normalize_combo(combo).split("+"):
            part = part.strip()
            if not part:
                continue
            parts.append(labels.get(part, part.upper() if len(part) == 1 else part.capitalize()))
        return " + ".join(parts)

    @staticmethod
    def _parse_combo(combo: str) -> Optional[Tuple[int, int]]:
        """Converts a shortcut string into (modifier_flags, virtual_key_code).

        Returns None if the combination is unusable: unknown key name, more than
        one non-modifier key, or no modifier at all (which would swallow a plain
        keystroke system-wide).
        """
        modifiers = 0
        vk_code: Optional[int] = None

        for part in HotkeyManager._normalize_combo(combo).split("+"):
            part = part.strip()
            if not part:
                continue

            if part in MODIFIER_FLAGS:
                modifiers |= MODIFIER_FLAGS[part]
                continue

            if vk_code is not None:
                return None  # A hotkey may carry only one non-modifier key

            if len(part) == 1:
                vk_code = ord(part.upper())
            elif part in NAMED_VK_CODES:
                vk_code = NAMED_VK_CODES[part]
            else:
                return None

        if vk_code is None or modifiers == 0:
            return None

        return modifiers | MOD_NOREPEAT, vk_code
