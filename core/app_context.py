"""Identifies the application the user is typing into.

Read immediately before the clipboard is touched, so the profile that applies
is the one for the window that actually holds the selection. Waiting until
after Ctrl+C would risk reading our own window instead.
"""

import ctypes
import os
from ctypes import wintypes
from typing import Optional, NamedTuple, Dict, Any, Tuple

from utils.logger import get_logger

logger = get_logger()

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class AppContext(NamedTuple):
    """The foreground application at the moment a hotkey fired."""

    process_name: str   # Lower-cased executable name, e.g. "chrome.exe"
    window_title: str

    @property
    def is_known(self) -> bool:
        return bool(self.process_name)


EMPTY_CONTEXT = AppContext(process_name="", window_title="")


def get_foreground_app() -> AppContext:
    """Returns the foreground window's process name and title.

    Never raises: an unreadable window simply yields an empty context, and the
    caller falls back to the global defaults.
    """
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return EMPTY_CONTEXT

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return EMPTY_CONTEXT

        title = _get_window_title(hwnd)
        process_name = _get_process_name(pid.value)
        return AppContext(process_name=process_name, window_title=title)
    except Exception as e:
        logger.debug("Could not read foreground application: %s", e)
        return EMPTY_CONTEXT


def _get_window_title(hwnd) -> str:
    try:
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value
    except Exception:
        return ""


def _get_process_name(pid: int) -> str:
    """Resolves a PID to its lower-cased executable name.

    PROCESS_QUERY_LIMITED_INFORMATION is used rather than the full query right:
    it is the one access level that still works against processes running at a
    higher integrity level.
    """
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(1024)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return os.path.basename(buffer.value).lower()
        return ""
    finally:
        kernel32.CloseHandle(handle)


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


user32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.POINTER(GUITHREADINFO)]
user32.GetGUIThreadInfo.restype = wintypes.BOOL
user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.ClientToScreen.restype = wintypes.BOOL
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.restype = wintypes.BOOL


def get_caret_position() -> Optional[Tuple[int, int]]:
    """Returns the screen position just below the text cursor.

    Falls back to the mouse pointer, and then to nothing at all. Many editors
    draw their own caret rather than using the Windows one — browsers and
    Electron apps especially — so the fallback is the common path, not the
    exception.
    """
    try:
        hwnd = user32.GetForegroundWindow()
        if hwnd:
            thread_id = user32.GetWindowThreadProcessId(hwnd, None)
            info = GUITHREADINFO()
            info.cbSize = ctypes.sizeof(GUITHREADINFO)

            if user32.GetGUIThreadInfo(thread_id, ctypes.byref(info)) and info.hwndCaret:
                point = wintypes.POINT(info.rcCaret.left, info.rcCaret.bottom)
                if user32.ClientToScreen(info.hwndCaret, ctypes.byref(point)):
                    return int(point.x), int(point.y)
    except Exception as e:
        logger.debug("Could not read caret position: %s", e)

    return get_cursor_position()


def get_cursor_position() -> Optional[Tuple[int, int]]:
    """Returns the mouse pointer position in screen coordinates."""
    try:
        point = wintypes.POINT()
        if user32.GetCursorPos(ctypes.byref(point)):
            return int(point.x), int(point.y)
    except Exception as e:
        logger.debug("Could not read cursor position: %s", e)
    return None


def match_profile(
    context: AppContext,
    profiles: Dict[str, Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Finds the profile configured for this application, if any.

    Matching is on the executable name alone. Window titles change constantly
    (the open document, the current channel) and would make profiles fire
    unpredictably.
    """
    if not context.is_known or not profiles:
        return None

    profile = profiles.get(context.process_name)
    if profile and profile.get("enabled", True):
        return profile
    return None
