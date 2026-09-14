"""Windows Clipboard Manager with Multi-Format Backup and Key Simulation.

Safely backups and restores all available clipboard formats (Unicode text,
images, files, custom formats) using pywin32, and simulates keystrokes
via Win32 SendInput without triggering modifier key conflicts.
"""

import time
import ctypes
from ctypes import wintypes
from typing import Dict, Any, Optional, Tuple
import win32clipboard
import win32con
from utils.logger import get_logger

logger = get_logger()

# Win32 Constants
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_MENU = 0x12  # Alt
VK_C = 0x43
VK_V = 0x56


# ULONG_PTR follows the pointer width of the running interpreter
ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUT(ctypes.Structure):
    """Win32 INPUT.

    Every member of the union has to be declared even though only keyboard
    events are sent. MOUSEINPUT is the largest at 32 bytes, so omitting it
    shrinks sizeof(INPUT) from 40 to 32 on x64 — and SendInput rejects any
    cbSize that does not match its own idea of the struct, failing with
    ERROR_INVALID_PARAMETER and no other symptom.
    """

    class _INPUT_UNION(ctypes.Union):
        _fields_ = [
            ("mi", MOUSEINPUT),
            ("ki", KEYBDINPUT),
            ("hi", HARDWAREINPUT),
        ]

    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUT_UNION)]


user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT


class ClipboardManager:
    """Handles clipboard backup, restore, and automated text retrieval/replacement."""

    def __init__(self):
        self._busy = False

    @staticmethod
    def _send_key_event(vk_code: int, key_up: bool = False) -> bool:
        """Sends a single keyboard event using Win32 SendInput.

        Returns True when the event reached the input queue. A rejected event
        used to pass unnoticed, leaving copy and paste simulation silently
        doing nothing, so the outcome is checked and logged.
        """
        flags = KEYEVENTF_KEYUP if key_up else 0
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.ki = KEYBDINPUT(
            wVk=vk_code,
            wScan=0,
            dwFlags=flags,
            time=0,
            dwExtraInfo=0
        )
        sent = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        if sent != 1:
            logger.error(
                "SendInput rejected key event (vk=0x%02X, up=%s): Win32 error %d",
                vk_code, key_up, ctypes.get_last_error()
            )
            return False
        return True

    @staticmethod
    def release_modifier_keys() -> None:
        """Explicitly releases physical Ctrl, Shift, and Alt keys to avoid hotkey interference."""
        # Key up for Shift, Control, Alt
        ClipboardManager._send_key_event(VK_SHIFT, key_up=True)
        ClipboardManager._send_key_event(VK_CONTROL, key_up=True)
        ClipboardManager._send_key_event(VK_MENU, key_up=True)

    @staticmethod
    def simulate_copy() -> None:
        """Simulates pure Ctrl+C keystroke."""
        ClipboardManager.release_modifier_keys()
        time.sleep(0.04)
        ClipboardManager._send_key_event(VK_CONTROL, key_up=False)
        ClipboardManager._send_key_event(VK_C, key_up=False)
        time.sleep(0.03)
        ClipboardManager._send_key_event(VK_C, key_up=True)
        ClipboardManager._send_key_event(VK_CONTROL, key_up=True)

    @staticmethod
    def simulate_paste() -> None:
        """Simulates pure Ctrl+V keystroke."""
        ClipboardManager.release_modifier_keys()
        time.sleep(0.04)
        ClipboardManager._send_key_event(VK_CONTROL, key_up=False)
        ClipboardManager._send_key_event(VK_V, key_up=False)
        time.sleep(0.03)
        ClipboardManager._send_key_event(VK_V, key_up=True)
        ClipboardManager._send_key_event(VK_CONTROL, key_up=True)

    @staticmethod
    def get_sequence_number() -> int:
        """Returns the current Windows clipboard sequence number."""
        try:
            return win32clipboard.GetClipboardSequenceNumber()
        except Exception:
            return 0

    def backup_clipboard(self) -> Dict[int, Any]:
        """Captures a snapshot of all readable clipboard formats."""
        snapshot: Dict[int, Any] = {}
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                win32clipboard.OpenClipboard()
                try:
                    fmt = win32clipboard.EnumClipboardFormats(0)
                    while fmt != 0:
                        try:
                            data = win32clipboard.GetClipboardData(fmt)
                            snapshot[fmt] = data
                        except Exception:
                            # Some formats cannot be read directly (e.g. delayed rendering)
                            pass
                        fmt = win32clipboard.EnumClipboardFormats(fmt)
                finally:
                    win32clipboard.CloseClipboard()
                break
            except Exception as e:
                time.sleep(0.02)
                if attempt == max_attempts - 1:
                    logger.warning("Could not open clipboard for backup: %s", e)

        return snapshot

    def restore_clipboard(self, snapshot: Dict[int, Any]) -> bool:
        """Restores clipboard data from a previously taken snapshot."""
        if not snapshot:
            return True

        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                win32clipboard.OpenClipboard()
                try:
                    win32clipboard.EmptyClipboard()
                    for fmt, data in snapshot.items():
                        try:
                            win32clipboard.SetClipboardData(fmt, data)
                        except Exception as e:
                            logger.debug("Could not restore clipboard format %s: %s", fmt, e)
                finally:
                    win32clipboard.CloseClipboard()
                return True
            except Exception as e:
                time.sleep(0.03)
                if attempt == max_attempts - 1:
                    logger.warning("Could not restore clipboard after %d attempts: %s", max_attempts, e)

        return False

    def get_clipboard_text(self) -> str:
        """Reads plain/Unicode text currently on the clipboard."""
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                win32clipboard.OpenClipboard()
                text = ""
                try:
                    if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                        text = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                    elif win32clipboard.IsClipboardFormatAvailable(win32con.CF_TEXT):
                        raw = win32clipboard.GetClipboardData(win32con.CF_TEXT)
                        text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
                finally:
                    win32clipboard.CloseClipboard()
                return text or ""
            except Exception:
                time.sleep(0.02)
        return ""

    def set_clipboard_text(self, text: str) -> bool:
        """Puts Unicode text onto the clipboard."""
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                win32clipboard.OpenClipboard()
                try:
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
                finally:
                    win32clipboard.CloseClipboard()
                return True
            except Exception as e:
                time.sleep(0.02)
                if attempt == max_attempts - 1:
                    logger.warning("Could not set clipboard text: %s", e)
        return False

    def capture_selected_text(self) -> Tuple[Optional[str], Dict[int, Any]]:
        """Backs up clipboard and attempts to capture selected text via Ctrl+C.

        Returns:
            (selected_text, backup_snapshot):
            - If text was selected and copied: (text, snapshot)
            - If no selection was detected: (None, snapshot)
        """
        # 1. Backup existing clipboard content
        snapshot = self.backup_clipboard()
        initial_seq = self.get_sequence_number()
        initial_text = self.get_clipboard_text()

        # 2. Simulate Ctrl+C
        self.simulate_copy()

        # 3. Wait for clipboard sequence number to increment (up to 300ms)
        start_time = time.time()
        selection_copied = False

        while time.time() - start_time < 0.35:
            current_seq = self.get_sequence_number()
            if current_seq != initial_seq:
                selection_copied = True
                break
            time.sleep(0.03)

        current_text = self.get_clipboard_text()

        # If sequence number changed or clipboard text changed to something non-empty
        if selection_copied and current_text and current_text != initial_text:
            return current_text, snapshot

        # If sequence changed even to identical text (e.g. user re-copied same text)
        if selection_copied and current_text:
            return current_text, snapshot

        # No selected text was copied
        return None, snapshot

    def paste_and_restore(self, new_text: str, backup_snapshot: Dict[int, Any], restore: bool = True) -> bool:
        """Puts new_text into clipboard, pastes via Ctrl+V, then restores original clipboard."""
        # 1. Put new translated text on clipboard
        if not self.set_clipboard_text(new_text):
            logger.error("Failed to set translated text onto clipboard")
            return False

        # 2. Simulate Ctrl+V
        self.simulate_paste()

        # 3. Allow target application message queue to process WM_PASTE
        time.sleep(0.12)

        # 4. Restore previous clipboard if requested
        if restore and backup_snapshot:
            self.restore_clipboard(backup_snapshot)

        return True


# Singleton instance
_clipboard_instance: Optional[ClipboardManager] = None


def get_clipboard_manager() -> ClipboardManager:
    """Gets or initializes the global ClipboardManager singleton."""
    global _clipboard_instance
    if _clipboard_instance is None:
        _clipboard_instance = ClipboardManager()
    return _clipboard_instance
