"""Main Application Entry Point for Windows AI Translation Tool.

Initializes PySide6 application, single-instance lock, floating toast notifications,
system tray icon, global hotkey listener, and background worker threads.
"""

import sys
import time
import threading
from typing import Optional, Dict, Any, Tuple

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, Signal, Slot, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from config import get_config, SUPPORTED_LANGUAGES, TARGET_LANGUAGES
from database import get_database
from utils.logger import setup_logger, get_logger
from utils.startup import is_run_at_startup_enabled
from core.clipboard_manager import get_clipboard_manager
from core.translator import get_translator
from core.hotkey_manager import HotkeyManager
from core.language_detect import resolve_auto_target
from core.app_context import get_foreground_app, match_profile, get_caret_position
from ui.tray import TrayManager
from ui.toast import get_toast
from ui.preview_popup import get_preview_popup
from ui.resources import create_app_icon

logger = setup_logger()
SINGLE_INSTANCE_SERVER_NAME = "AITranslator_SingleInstance_Server"

# Two hotkey events closer together than this are treated as key bounce.
MIN_TRIGGER_INTERVAL_S = 0.25

# Languages offered in the preview popup's retarget dropdown
PREVIEW_LANGUAGE_LIMIT = 14


class TranslationBridge(QObject):
    """Thread-safe signal bridge between background workers and Qt GUI thread."""

    sig_translating = Signal(str)
    sig_success = Signal(str)
    sig_error = Signal(str)
    sig_info = Signal(str)

    sig_trigger_translate = Signal(object)      # target_language (str or None)
    sig_trigger_clipboard = Signal()
    sig_trigger_ocr = Signal(object)            # target_language (str or None)

    sig_show_preview = Signal(object)           # pending translation dict


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
        self._busy_lock = threading.Lock()
        self._is_busy = False
        self._last_trigger_time = 0.0

        # Result waiting on the preview popup, and the region selector's own
        # reference — dropping either would let Python collect it mid-use.
        self._pending: Optional[Dict[str, Any]] = None
        self._region_selector = None

        # Connect UI toast signals
        self.bridge.sig_translating.connect(self._on_toast_translating)
        self.bridge.sig_success.connect(self._on_toast_success)
        self.bridge.sig_error.connect(self._on_toast_error)
        self.bridge.sig_info.connect(self._on_toast_info)

        # Connect worker trigger signals
        self.bridge.sig_trigger_translate.connect(self._start_translation_worker)
        self.bridge.sig_trigger_clipboard.connect(self._start_clipboard_worker)
        self.bridge.sig_trigger_ocr.connect(self._start_ocr_selection)
        self.bridge.sig_show_preview.connect(self._on_show_preview)

        # Tray setup
        self.tray = TrayManager(
            app=self.app,
            on_translate_selected=lambda: self.bridge.sig_trigger_translate.emit(None),
            on_translate_clipboard=lambda: self.bridge.sig_trigger_clipboard.emit(),
            on_translate_ocr=lambda: self.bridge.sig_trigger_ocr.emit(None),
            on_reload_hotkeys=self.reload_hotkeys
        )

        # Hotkey listener setup
        self.hotkey_mgr = HotkeyManager(action_callback=self._on_hotkey)

        # Preview popup wiring
        popup = get_preview_popup()
        popup.replace_requested.connect(self._on_preview_replace)
        popup.copy_requested.connect(self._on_preview_copy)
        popup.retranslate_requested.connect(self._on_preview_retranslate)
        popup.dismissed.connect(self._on_preview_dismissed)

    # --- Startup ---
    def start(self) -> None:
        """Starts system tray icon and global hotkey listener."""
        self.tray.show()
        self.hotkey_mgr.start()
        # Hand the hotkey registrations back to Windows on the way out
        self.app.aboutToQuit.connect(self.hotkey_mgr.stop)
        logger.info("Application controller started successfully")

        shortcut = self._primary_hotkey_label()

        if self.config.get("first_run", True):
            self.config.set("first_run", False)
            # On first run, open Settings window so user can explore options, and show friendly hint
            QTimer.singleShot(600, self.tray.open_settings)
            self.bridge.sig_success.emit(f"Chào mừng! Bôi đen văn bản và nhấn {shortcut} để dịch")
        elif self.config.get("show_notifications", True):
            self.bridge.sig_info.emit(f"AI Translator đang chạy nền ({shortcut})")

        # A hotkey another application already owns fails silently otherwise
        if self.hotkey_mgr.failed_hotkeys:
            taken = ", ".join(
                HotkeyManager.format_combo(c) for c in self.hotkey_mgr.failed_hotkeys
            )
            QTimer.singleShot(
                3200,
                lambda: self.bridge.sig_error.emit(
                    f"Không đăng ký được phím tắt {taken} — ứng dụng khác đang giữ. "
                    f"Đổi phím khác trong Cài đặt."
                )
            )

    def _primary_hotkey_label(self) -> str:
        """Returns the main translate shortcut as the user would read it."""
        combo = self.config.get_hotkeys().get("translate", {}).get("key", "")
        return HotkeyManager.format_combo(combo) if combo else "phím tắt đã cấu hình"

    def reload_hotkeys(self) -> None:
        """Restarts hotkey listener with updated configurations."""
        self.hotkey_mgr.reload()

    def _on_hotkey(self, target_language: Optional[str], action: str) -> None:
        """Routes a hotkey press onto the Qt thread."""
        if action == "ocr":
            self.bridge.sig_trigger_ocr.emit(target_language)
        else:
            self.bridge.sig_trigger_translate.emit(target_language)

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

    # --- Concurrency Guard ---
    def _acquire_busy(self) -> bool:
        """Claims the single translation slot.

        The claim has to be made here, on the Qt thread, rather than inside the
        worker: a worker only sets the flag once it is already running, which
        leaves a window where a second hotkey press starts a second pipeline.
        Two pipelines mean two Ctrl+C injections, two Ctrl+V injections, and a
        clipboard restored out of order.

        Returns False when a translation is already running or the previous
        trigger arrived moments ago.
        """
        now = time.monotonic()
        with self._busy_lock:
            if self._is_busy:
                logger.warning("Translation already in progress, skipping duplicate trigger")
                return False
            if now - self._last_trigger_time < MIN_TRIGGER_INTERVAL_S:
                logger.debug("Trigger ignored as key bounce")
                return False
            self._is_busy = True
            self._last_trigger_time = now
            return True

    def _release_busy(self) -> None:
        """Releases the translation slot."""
        with self._busy_lock:
            self._is_busy = False

    # --- Request resolution ---
    def _resolve_settings(
        self,
        text: str,
        target_override: Optional[str]
    ) -> Tuple[str, str, str, str]:
        """Decides target language, mode and style for this particular request.

        Precedence, strongest first: the language bound to the hotkey, the
        profile for the foreground application, two-way auto-detection, then
        the global defaults.
        """
        mode = self.config.get("mode", "translate")
        style = self.config.get("rewrite_style", "natural")
        target = self.config.get("target_language", "en")
        source = self.config.get("source_language", "auto")

        # Per-application profile
        context = get_foreground_app()
        profile = match_profile(context, self.config.get_app_profiles())
        profile_target = None
        if profile:
            logger.info("Applying profile for %s", context.process_name)
            profile_target = profile.get("target_language")
            if profile_target:
                target = profile_target
            mode = profile.get("mode", mode)
            style = profile.get("rewrite_style", style)

        if target_override:
            # A hotkey bound to a language beats everything else
            target = target_override
        elif profile_target:
            # A profile that names a language means it. Auto-detection would
            # undo the choice the user made for this application; leaving the
            # profile's target_language empty is how they ask for auto instead.
            logger.info("Profile pinned the target language: %s", profile_target)
        else:
            auto = self.config.get_auto_swap()
            if auto.get("enabled", False):
                primary = auto.get("primary", "vi")
                secondary = auto.get("secondary", "en")
                target = resolve_auto_target(text, primary, secondary, fallback=target)
                logger.info("Two-way auto-detect chose target: %s", target)

        return target, source, mode, style

    def _preview_enabled(self) -> bool:
        return bool(self.config.get("preview_popup", {}).get("enabled", False))

    # --- Worker Dispatching ---
    @Slot(object)
    def _start_translation_worker(self, target_language: Optional[str]) -> None:
        """Runs the translation workflow in a background thread."""
        if not self._acquire_busy():
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
        if not self._acquire_busy():
            return

        thread = threading.Thread(
            target=self._run_clipboard_translation_pipeline,
            daemon=True
        )
        thread.start()

    @Slot(object)
    def _start_ocr_selection(self, target_language: Optional[str]) -> None:
        """Opens the screen-region overlay; the capture runs once a region is picked."""
        from core import ocr
        from ui.region_selector import select_region

        if not ocr.is_available():
            self.bridge.sig_error.emit(ocr.unavailable_reason())
            return

        if not self._acquire_busy():
            return

        def on_selected(left: int, top: int, width: int, height: int) -> None:
            self._region_selector = None
            thread = threading.Thread(
                target=self._run_ocr_pipeline,
                args=((left, top, width, height), target_language),
                daemon=True
            )
            thread.start()

        def on_cancelled() -> None:
            self._region_selector = None
            self._release_busy()

        self._region_selector = select_region(on_selected, on_cancelled)

    # --- Pipelines ---
    def _run_translation_pipeline(self, target_language: Optional[str]) -> None:
        """Background pipeline: Capture selected text -> Translate -> Paste -> Restore clipboard."""
        released = False
        try:
            # 1. Attempt to capture highlighted text
            selected_text, backup_snapshot = self.clipboard_mgr.capture_selected_text()

            # Mode 1: Selected Text Translation
            if selected_text and selected_text.strip():
                target_lang, source_lang, mode, style = self._resolve_settings(
                    selected_text, target_language
                )
                target_lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)
                self.bridge.sig_translating.emit(f"Đang dịch sang {target_lang_name}...")

                try:
                    translated = self.translator.translate_text(
                        text=selected_text,
                        target_language=target_lang,
                        source_language=source_lang,
                        mode=mode,
                        style=style
                    )

                    if self._preview_enabled():
                        self.bridge.sig_show_preview.emit({
                            "source_text": selected_text,
                            "translated": translated,
                            "target_language": target_lang,
                            "backup_snapshot": backup_snapshot,
                            "source_language": source_lang,
                            "mode": mode,
                            "style": style,
                        })
                        # The popup owns the outcome now
                        self._release_busy()
                        released = True
                        return

                    restore_pref = self.config.get("restore_clipboard", True)
                    self.clipboard_mgr.paste_and_restore(
                        new_text=translated,
                        backup_snapshot=backup_snapshot,
                        restore=restore_pref
                    )
                    self.config.remember_language(target_lang)
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

                self._translate_to_clipboard(clipboard_text, target_language)

        finally:
            if not released:
                self._release_busy()

    def _run_clipboard_translation_pipeline(self) -> None:
        """Background pipeline: Translate clipboard directly and save to clipboard."""
        try:
            clipboard_text = self.clipboard_mgr.get_clipboard_text()
            if not clipboard_text or not clipboard_text.strip():
                self.bridge.sig_info.emit("Clipboard đang trống.")
                return
            self._translate_to_clipboard(clipboard_text, None)
        finally:
            self._release_busy()

    def _run_ocr_pipeline(
        self,
        region: Tuple[int, int, int, int],
        target_language: Optional[str]
    ) -> None:
        """Background pipeline: Capture screen region -> OCR -> Translate -> Clipboard."""
        from core import ocr

        try:
            self.bridge.sig_translating.emit("Đang đọc chữ từ màn hình...")
            try:
                recognized = ocr.capture_and_recognize(
                    region, self.config.get("ocr", {}).get("language", "auto")
                )
            except Exception as e:
                logger.error("OCR failed: %s", e)
                self.bridge.sig_error.emit(str(e))
                return

            if not recognized.strip():
                self.bridge.sig_info.emit("Không tìm thấy chữ nào trong vùng đã chọn.")
                return

            logger.info("OCR recognised %d characters", len(recognized))
            self._translate_to_clipboard(recognized, target_language, prefix="OCR")
        finally:
            self._release_busy()

    def _translate_to_clipboard(
        self,
        text: str,
        target_language: Optional[str],
        prefix: str = ""
    ) -> None:
        """Translates text and leaves the result on the clipboard.

        Used wherever there is no selection to replace: clipboard mode and OCR.
        Pasting automatically in those cases would insert text wherever the
        caret happens to be, which is rarely where the user wanted it.
        """
        target_lang, source_lang, mode, style = self._resolve_settings(text, target_language)
        target_lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

        label = f"{prefix} → " if prefix else ""
        self.bridge.sig_translating.emit(f"Đang dịch {label}{target_lang_name}...")

        try:
            translated = self.translator.translate_text(
                text=text,
                target_language=target_lang,
                source_language=source_lang,
                mode=mode,
                style=style
            )
        except Exception as e:
            logger.error("Translation failed: %s", e)
            self.bridge.sig_error.emit(f"Dịch thất bại: {e}")
            return

        if self._preview_enabled():
            self.bridge.sig_show_preview.emit({
                "source_text": text,
                "translated": translated,
                "target_language": target_lang,
                "backup_snapshot": None,
                "source_language": source_lang,
                "mode": mode,
                "style": style,
            })
            return

        self.clipboard_mgr.set_clipboard_text(translated)
        self.config.remember_language(target_lang)
        self.bridge.sig_success.emit(
            f"Đã dịch → {target_lang_name} (Đã chép vào clipboard)"
        )

    # --- Preview popup ---
    @Slot(object)
    def _on_show_preview(self, pending: Dict[str, Any]) -> None:
        """Displays the translation and waits for the user's decision."""
        self._pending = pending
        settings = self.config.get("preview_popup", {})

        get_preview_popup().show_translation(
            source_text=pending["source_text"],
            translated_text=pending["translated"],
            target_language=pending["target_language"],
            languages=self._preview_languages(pending["target_language"]),
            anchor=get_caret_position(),
            timeout_seconds=int(settings.get("timeout_seconds", 12)),
        )

    def _preview_languages(self, current: str) -> Dict[str, str]:
        """Builds a short language list for the popup's retarget dropdown."""
        codes = []
        for code in [current] + list(self.config.get("recent_languages", [])):
            if code and code in TARGET_LANGUAGES and code not in codes:
                codes.append(code)
        for code in TARGET_LANGUAGES:
            if len(codes) >= PREVIEW_LANGUAGE_LIMIT:
                break
            if code not in codes:
                codes.append(code)
        return {code: TARGET_LANGUAGES[code] for code in codes}

    @Slot()
    def _on_preview_replace(self) -> None:
        """Replaces the selection with the previewed translation."""
        pending = self._pending
        self._pending = None
        if not pending:
            return

        def worker() -> None:
            try:
                translated = pending["translated"]
                snapshot = pending.get("backup_snapshot")
                if snapshot is None:
                    # Nothing was selected (clipboard or OCR flow), so there is
                    # nothing to paste over — leave the text on the clipboard.
                    self.clipboard_mgr.set_clipboard_text(translated)
                    self.bridge.sig_success.emit("Đã chép vào clipboard")
                    return

                self.clipboard_mgr.paste_and_restore(
                    new_text=translated,
                    backup_snapshot=snapshot,
                    restore=self.config.get("restore_clipboard", True)
                )
                name = SUPPORTED_LANGUAGES.get(
                    pending["target_language"], pending["target_language"]
                )
                self.config.remember_language(pending["target_language"])
                self.bridge.sig_success.emit(f"Đã dịch → {name}")
            except Exception as e:
                logger.error("Preview replace failed: %s", e)
                self.bridge.sig_error.emit(f"Thay thế thất bại: {e}")

        threading.Thread(target=worker, daemon=True).start()

    @Slot()
    def _on_preview_copy(self) -> None:
        """Copies the previewed translation without touching the selection."""
        pending = self._pending
        self._pending = None
        if not pending:
            return

        snapshot = pending.get("backup_snapshot")
        self.clipboard_mgr.set_clipboard_text(pending["translated"])
        self.config.remember_language(pending["target_language"])
        self.bridge.sig_success.emit("Đã chép vào clipboard")

        if snapshot is not None:
            logger.debug("Original clipboard discarded in favour of the translation")

    @Slot(str)
    def _on_preview_retranslate(self, target_language: str) -> None:
        """Re-runs the translation against a different target language."""
        pending = self._pending
        if not pending:
            return

        source_text = pending["source_text"]
        name = SUPPORTED_LANGUAGES.get(target_language, target_language)
        self.bridge.sig_translating.emit(f"Đang dịch lại sang {name}...")

        def worker() -> None:
            try:
                translated = self.translator.translate_text(
                    text=source_text,
                    target_language=target_language,
                    source_language=pending.get("source_language"),
                    mode=pending.get("mode"),
                    style=pending.get("style")
                )
            except Exception as e:
                logger.error("Preview retranslate failed: %s", e)
                self.bridge.sig_error.emit(f"Dịch lại thất bại: {e}")
                return

            updated = dict(pending)
            updated["translated"] = translated
            updated["target_language"] = target_language
            self.bridge.sig_show_preview.emit(updated)

        threading.Thread(target=worker, daemon=True).start()

    @Slot()
    def _on_preview_dismissed(self) -> None:
        """Drops a preview the user ignored, restoring the clipboard."""
        pending = self._pending
        self._pending = None
        if pending and pending.get("backup_snapshot"):
            self.clipboard_mgr.restore_clipboard(pending["backup_snapshot"])
        logger.info("Preview dismissed without action")


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
            controller.bridge.sig_info.emit(
                f"AI Translator đang chạy nền ({controller._primary_hotkey_label()})"
            )

    server.newConnection.connect(on_new_instance)

    # If user launched manually (no --tray flag), open Settings window for immediate feedback
    if "--tray" not in sys.argv:
        QTimer.singleShot(300, controller.tray.open_settings)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
