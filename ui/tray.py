"""System Tray Icon and Context Menu for Windows AI Translation Tool.

Handles tray interactions, quick language/provider switching,
and launches background translation workflows.
"""

from typing import Optional, Callable
from PySide6.QtWidgets import (
    QSystemTrayIcon, QMenu, QMessageBox, QWidget, QApplication
)
from PySide6.QtGui import QAction, QActionGroup, QFont
from PySide6.QtCore import Qt

from config import get_config, SUPPORTED_LANGUAGES, PROVIDERS
from core.hotkey_manager import HotkeyManager
from ui.resources import create_tray_icon
from ui.settings_window import SettingsWindow
from ui.history_window import HistoryWindow
from utils.logger import get_logger

logger = get_logger()


class TrayManager:
    """Manages the Windows system tray icon and its context menu."""

    def __init__(
        self,
        app: QApplication,
        on_translate_selected: Callable[[], None],
        on_translate_clipboard: Callable[[], None],
        on_reload_hotkeys: Callable[[], None]
    ):
        self.app = app
        self.config = get_config()
        self.on_translate_selected = on_translate_selected
        self.on_translate_clipboard = on_translate_clipboard
        self.on_reload_hotkeys = on_reload_hotkeys

        self.settings_window: Optional[SettingsWindow] = None
        self.history_window: Optional[HistoryWindow] = None

        self.tray_icon = QSystemTrayIcon()
        self.tray_icon.setIcon(create_tray_icon(32))
        self.tray_icon.setToolTip("AI Translator (Gboard cho Windows)")

        self.act_translate_selected = None
        self._create_menu()
        self.tray_icon.activated.connect(self._on_tray_activated)

    def _primary_hotkey_label(self) -> str:
        """Returns the main translate shortcut as the user would read it."""
        combo = self.config.get_hotkeys().get("translate", {}).get("key", "")
        return HotkeyManager.format_combo(combo) if combo else "phím tắt đã cấu hình"

    def _create_menu(self) -> None:
        self.menu = QMenu()

        # App Title Header
        title_action = QAction("AI Translator (Gboard Windows)", self.menu)
        font = QFont("Segoe UI", 9, QFont.Bold)
        title_action.setFont(font)
        title_action.setEnabled(False)
        self.menu.addAction(title_action)

        self.menu.addSeparator()

        # Action: Translate Selected Text
        act_sel = self.menu.addAction(
            f"Dịch văn bản đang chọn ({self._primary_hotkey_label()})"
        )
        act_sel.triggered.connect(self.on_translate_selected)
        self.act_translate_selected = act_sel

        # Action: Translate Clipboard
        act_clip = self.menu.addAction("Dịch nội dung Clipboard")
        act_clip.triggered.connect(self.on_translate_clipboard)

        self.menu.addSeparator()

        # Submenu: Target Language
        self.lang_menu = self.menu.addMenu("Ngôn ngữ đích")
        self.lang_group = QActionGroup(self.lang_menu)
        self.lang_group.setExclusive(True)

        current_tgt = self.config.get("target_language", "en")
        for code, name in SUPPORTED_LANGUAGES.items():
            if code == "auto":
                continue
            act = QAction(f"{name} ({code})", self.lang_menu)
            act.setCheckable(True)
            act.setData(code)
            if code == current_tgt:
                act.setChecked(True)
            act.triggered.connect(lambda checked, c=code: self._set_target_language(c))
            self.lang_group.addAction(act)
            self.lang_menu.addAction(act)

        # Submenu: Provider
        self.prov_menu = self.menu.addMenu("Dịch vụ dịch (Provider)")
        self.prov_group = QActionGroup(self.prov_menu)
        self.prov_group.setExclusive(True)

        current_prov = self.config.get("provider", "google")
        for prov_id, prov_name in PROVIDERS.items():
            act = QAction(prov_name, self.prov_menu)
            act.setCheckable(True)
            act.setData(prov_id)
            if prov_id == current_prov:
                act.setChecked(True)
            act.triggered.connect(lambda checked, p=prov_id: self._set_provider(p))
            self.prov_group.addAction(act)
            self.prov_menu.addAction(act)

        self.menu.addSeparator()

        # Windows
        act_settings = self.menu.addAction("Cài đặt...")
        act_settings.triggered.connect(self.open_settings)

        act_history = self.menu.addAction("Lịch sử dịch...")
        act_history.triggered.connect(self.open_history)

        act_about = self.menu.addAction("Giới thiệu...")
        act_about.triggered.connect(self._show_about)

        self.menu.addSeparator()

        # Exit
        act_exit = self.menu.addAction("Thoát ứng dụng")
        act_exit.triggered.connect(self.exit_app)

        self.tray_icon.setContextMenu(self.menu)

    def show(self) -> None:
        """Displays system tray icon."""
        self.tray_icon.show()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.DoubleClick:
            self.open_settings()

    def _set_target_language(self, code: str) -> None:
        self.config.set("target_language", code)
        logger.info("Target language switched from tray to: %s", code)

    def _set_provider(self, provider_id: str) -> None:
        self.config.set("provider", provider_id)
        logger.info("Translation provider switched from tray to: %s", provider_id)

    def open_settings(self) -> None:
        """Opens or activates the Settings window."""
        if self.settings_window is None or not self.settings_window.isVisible():
            self.settings_window = SettingsWindow()
            self.settings_window.settings_applied.connect(self._on_settings_applied)
            self.settings_window.show()
            self.settings_window.activateWindow()
        else:
            self.settings_window.activateWindow()
            self.settings_window.raise_()

    def _on_settings_applied(self) -> None:
        """Refreshes tray checkmarks and reloads hotkeys."""
        current_tgt = self.config.get("target_language", "en")
        for act in self.lang_group.actions():
            if act.data() == current_tgt:
                act.setChecked(True)
                break

        current_prov = self.config.get("provider", "google")
        for act in self.prov_group.actions():
            if act.data() == current_prov:
                act.setChecked(True)
                break

        # The menu spells out the shortcut, so it has to follow a hotkey change
        if self.act_translate_selected is not None:
            self.act_translate_selected.setText(
                f"Dịch văn bản đang chọn ({self._primary_hotkey_label()})"
            )

        self.on_reload_hotkeys()

    def open_history(self) -> None:
        """Opens or activates the History window."""
        if self.history_window is None or not self.history_window.isVisible():
            self.history_window = HistoryWindow()
            self.history_window.show()
            self.history_window.activateWindow()
        else:
            self.history_window.refresh_history()
            self.history_window.activateWindow()
            self.history_window.raise_()

    def _show_about(self) -> None:
        """Displays About informational dialog."""
        msg = (
            "<h3>AI Translator cho Windows v1.0</h3>"
            "<p>Công cụ dịch thuật tại chỗ tiện lợi tương tự <b>Gboard Dịch</b> trên điện thoại.</p>"
            "<p><b>Tính năng nổi bật:</b></p>"
            "<ul>"
            f"<li>Bôi đen văn bản trong bất kỳ ứng dụng nào và bấm <code>{self._primary_hotkey_label()}</code></li>"
            "<li>Tự động dịch và thay thế văn bản trực tiếp tại chỗ</li>"
            "<li>Bảo toàn nguyên vẹn nội dung Clipboard trước đó của bạn</li>"
            "<li>Hỗ trợ nhiều nguồn dịch (Google Translate miễn phí, Gemini, OpenAI)</li>"
            "<li>Chế độ viết lại văn phong AI (Tự nhiên, Trang trọng, Thân mật, Trau chuốt)</li>"
            "<li>Mã hóa lưu trữ API key an toàn trong Windows Credential Manager</li>"
            "</ul>"
            "<p style='color: #64748B;'>Phát triển bằng Python & PySide6.</p>"
        )
        QMessageBox.about(None, "Giới thiệu AI Translator", msg)

    def exit_app(self) -> None:
        """Exits the entire application cleanly."""
        logger.info("Application exit initiated by user from system tray")
        self.tray_icon.hide()
        self.app.quit()
