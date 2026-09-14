"""Main Application Entry Point for Windows AI Translation Tool.

Initializes PySide6 application, single-instance lock, floating toast notifications,
system tray icon, global hotkey listener, and background worker threads.
"""

import sys
import threading
from typing import Optional

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, Signal, Slot, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from config import get_config, SUPPORTED_LANGUAGES
from database import get_database
from utils.logger import setup_logger, get_logger
from utils.startup import is_run_at_startup_enabled
from core.clipboard_manager import get_clipboard_manager
from core.translator import get_translator
from core.hotkey_manager import HotkeyManager
from ui.tray import TrayManager
from ui.toast import get_toast
from ui.resources import create_app_icon

logger = setup_logger()
SINGLE_INSTANCE_SERVER_NAME = "AITranslator_SingleInstance_Server"


class TranslationBridge(QObject):
    """Thread-safe signal bridge between background workers and Qt GUI thread."""

    sig_translating = Signal(str)
    sig_success = Signal(str)
    sig_error = Signal(str)
    sig_info = Signal(str)

    sig_trigger_translate = Signal(object)      # target_language (str or None)
    sig_trigger_clipboard = Signal()


class ApplicationController(QObject):
    """Controls the overall application state, workers, and UI events."""

    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.config = get_config()
        self.db = get_database()
        self.clipboard_mgr = get_clipboard_manager()
        self.translator = get_translator()
        self.bridge = TranslationBridge()
        self._is_busy = False

        # Connect UI toast signals
        self.bridge.sig_translating.connect(self._on_toast_translating)
        self.bridge.sig_success.connect(self._on_toast_success)
        self.bridge.sig_error.connect(self._on_toast_error)
        self.bridge.sig_info.connect(self._on_toast_info)

        # Connect worker trigger signals
        self.bridge.sig_trigger_translate.connect(self._start_translation_worker)
        self.bridge.sig_trigger_clipboard.connect(self._start_clipboard_worker)

        # Tray setup
        self.tray = TrayManager(
            app=self.app,
            on_translate_selected=lambda: self.bridge.sig_trigger_translate.emit(None),
            on_translate_clipboard=lambda: self.bridge.sig_trigger_clipboard.emit(),
            on_reload_hotkeys=self.reload_hotkeys
        )

        # Hotkey listener setup
        self.hotkey_mgr = HotkeyManager(
            action_callback=lambda target: self.bridge.sig_trigger_translate.emit(target)
        )

    def start(self) -> None:
        """Starts system tray icon and global hotkey listener."""
        self.tray.show()
        self.hotkey_mgr.start()
        logger.info("Application controller started successfully")

        if self.config.get("first_run", True):
            self.config.set("first_run", False)
            # On first run, open Settings window so user can explore options, and show friendly hint
            QTimer.singleShot(600, self.tray.open_settings)
            self.bridge.sig_success.emit("Chào mừng! Bôi đen văn bản và nhấn Ctrl + Shift + T để dịch")
        elif self.config.get("show_notifications", True):
            self.bridge.sig_info.emit("AI Translator đang chạy nền (Ctrl + Shift + T)")

    def reload_hotkeys(self) -> None:
        """Restarts hotkey listener with updated configurations."""
        self.hotkey_mgr.reload()

    # --- UI Toast Slots ---
    @Slot(str)
    def _on_toast_translating(self, msg: str) -> None:
        if self.config.get("show_notifications", True):
            get_toast().show_translating(msg)

    @Slot(str)
    def _on_toast_success(self, msg: str) -> None:
        if self.config.get("show_notifications", True):
            get_toast().show_success(msg)

    @Slot(str)
    def _on_toast_error(self, msg: str) -> None:
        if self.config.get("show_notifications", True):
            get_toast().show_error(msg)

    @Slot(str)
    def _on_toast_info(self, msg: str) -> None:
        if self.config.get("show_notifications", True):
            get_toast().show_info(msg)

    # --- Worker Dispatching ---
    @Slot(object)
    def _start_translation_worker(self, target_language: Optional[str]) -> None:
        """Runs the translation workflow in a background thread."""
        if self._is_busy:
            logger.warning("Translation already in progress, skipping duplicate hotkey event")
            return

        thread = threading.Thread(
            target=self._run_translation_pipeline,
            args=(target_language,),
            daemon=True
        )
        thread.start()

    @Slot()
    def _start_clipboard_worker(self) -> None:
        """Runs clipboard-only translation in a background thread."""
        if self._is_busy:
            return

        thread = threading.Thread(
            target=self._run_clipboard_translation_pipeline,
            daemon=True
        )
        thread.start()

    def _run_translation_pipeline(self, target_language: Optional[str]) -> None:
        """Background pipeline: Capture selected text -> Translate -> Paste -> Restore clipboard."""
        self._is_busy = True
        try:
            target_lang = target_language or self.config.get("target_language", "en")
            target_lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

            # 1. Attempt to capture highlighted text
            selected_text, backup_snapshot = self.clipboard_mgr.capture_selected_text()

            # Mode 1: Selected Text Translation
            if selected_text and selected_text.strip():
                self.bridge.sig_translating.emit(f"Đang dịch sang {target_lang_name}...")

                try:
                    translated = self.translator.translate_text(
                        text=selected_text,
                        target_language=target_lang
                    )

                    restore_pref = self.config.get("restore_clipboard", True)
                    self.clipboard_mgr.paste_and_restore(
                        new_text=translated,
                        backup_snapshot=backup_snapshot,
                        restore=restore_pref
                    )

                    self.bridge.sig_success.emit(f"Đã dịch → {target_lang_name}")
                except Exception as e:
                    logger.error("Selected text translation failed: %s", e)
                    # Restore original clipboard on failure
                    self.clipboard_mgr.restore_clipboard(backup_snapshot)
                    self.bridge.sig_error.emit(f"Dịch thất bại: {e}")

            # Mode 2: Clipboard Translation Fallback
            else:
                clipboard_text = self.clipboard_mgr.get_clipboard_text()
                if not clipboard_text or not clipboard_text.strip():
                    self.bridge.sig_info.emit("Chưa bôi đen văn bản và clipboard đang trống.")
                    return

                self.bridge.sig_translating.emit(f"Đang dịch clipboard sang {target_lang_name}...")
                try:
                    translated = self.translator.translate_text(
                        text=clipboard_text,
                        target_language=target_lang
                    )
                    self.clipboard_mgr.set_clipboard_text(translated)
                    self.bridge.sig_success.emit(
                        f"Đã dịch → {target_lang_name} (Đã chép vào clipboard)"
                    )
                except Exception as e:
                    logger.error("Clipboard translation failed: %s", e)
                    self.bridge.sig_error.emit(f"Dịch thất bại: {e}")

        finally:
            self._is_busy = False

    def _run_clipboard_translation_pipeline(self) -> None:
        """Background pipeline: Translate clipboard directly and save to clipboard."""
        self._is_busy = True
        try:
            target_lang = self.config.get("target_language", "en")
            target_lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

            clipboard_text = self.clipboard_mgr.get_clipboard_text()
            if not clipboard_text or not clipboard_text.strip():
                self.bridge.sig_info.emit("Clipboard đang trống.")
                return

            self.bridge.sig_translating.emit(f"Đang dịch clipboard sang {target_lang_name}...")
            try:
                translated = self.translator.translate_text(
                    text=clipboard_text,
                    target_language=target_lang
                )
                self.clipboard_mgr.set_clipboard_text(translated)
                self.bridge.sig_success.emit(
                    f"Đã dịch → {target_lang_name} (Đã chép vào clipboard)"
                )
            except Exception as e:
                logger.error("Explicit clipboard translation failed: %s", e)
                self.bridge.sig_error.emit(f"Dịch thất bại: {e}")
        finally:
            self._is_busy = False


def check_single_instance() -> Optional[QLocalServer]:
    """Ensures only one instance of the application runs simultaneously.
    If another instance is running, sends an activation message and exits.
    """
    socket = QLocalSocket()
    socket.connectToServer(SINGLE_INSTANCE_SERVER_NAME)
    if socket.waitForConnected(500):
        # Notify existing instance to bring window up
        socket.write(b"ACTIVATE\n")
        socket.flush()
        socket.waitForBytesWritten(500)
        socket.close()
        return None

    # This instance becomes the primary server
    server = QLocalServer()
    server.removeServer(SINGLE_INSTANCE_SERVER_NAME)
    if not server.listen(SINGLE_INSTANCE_SERVER_NAME):
        logger.warning("Could not start single instance local server")
    return server


def main() -> int:
    """Application entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName("AITranslator")
    app.setApplicationDisplayName("AI Translator")
    app.setQuitOnLastWindowClosed(False)  # Keep running in system tray
    app.setWindowIcon(create_app_icon(64))

    # Single instance check
    server = check_single_instance()
    if server is None:
        logger.warning("Another instance of AI Translator is already running. Notified and exiting.")
        return 0

    controller = ApplicationController(app)
    controller.start()

    # Handle activation requests from subsequent instances
    def on_new_instance():
        client = server.nextPendingConnection()
        if client:
            controller.tray.open_settings()
            controller.bridge.sig_info.emit("AI Translator đang chạy nền (Ctrl + Shift + T)")

    server.newConnection.connect(on_new_instance)

    # If user launched manually (no --tray flag), open Settings window for immediate feedback
    if "--tray" not in sys.argv:
        QTimer.singleShot(300, controller.tray.open_settings)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
