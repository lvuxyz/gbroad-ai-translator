"""Settings Window for Windows AI Translation Tool.

Provides user interface for general settings, language defaults,
global hotkeys, and secure API Key management via Windows Credential Manager.
"""

from typing import Optional, Callable
from PySide6.QtWidgets import (
    QDialog, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QCheckBox, QComboBox, QLineEdit, QPushButton,
    QLabel, QGroupBox, QMessageBox, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from config import (
    get_config,
    SUPPORTED_LANGUAGES,
    PROVIDERS,
    REWRITE_STYLES,
    DEFAULT_MODELS
)
from utils.startup import is_run_at_startup_enabled, set_run_at_startup
from utils.logger import set_privacy_mode, get_logger
from ui.resources import create_app_icon

logger = get_logger()


class SettingsWindow(QDialog):
    """Configuration dialog with tabbed settings interface."""

    settings_applied = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.config = get_config()

        self.setWindowTitle("AI Translator - Cài đặt")
        self.setWindowIcon(create_app_icon(32))
        self.resize(580, 500)
        self.setMinimumSize(520, 440)

        self._init_ui()
        self.load_values()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)

        self.tab_widget = QTabWidget(self)
        main_layout.addWidget(self.tab_widget)

        # Tab 1: Chung
        self.tab_general = QWidget()
        self._init_tab_general()
        self.tab_widget.addTab(self.tab_general, "Cài đặt chung")

        # Tab 2: Dịch thuật
        self.tab_translation = QWidget()
        self._init_tab_translation()
        self.tab_widget.addTab(self.tab_translation, "Dịch thuật & AI")

        # Tab 3: Phím tắt
        self.tab_hotkeys = QWidget()
        self._init_tab_hotkeys()
        self.tab_widget.addTab(self.tab_hotkeys, "Phím tắt")

        # Tab 4: API Keys
        self.tab_keys = QWidget()
        self._init_tab_keys()
        self.tab_widget.addTab(self.tab_keys, "Tài khoản API")

        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_reset = QPushButton("Khôi phục mặc định", self)
        self.btn_reset.clicked.connect(self._reset_defaults)
        btn_layout.addWidget(self.btn_reset)

        btn_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.btn_cancel = QPushButton("Hủy bỏ", self)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Lưu & Áp dụng", self)
        self.btn_save.setDefault(True)
        self.btn_save.setStyleSheet("background-color: #0284C7; color: white; font-weight: bold; padding: 6px 18px; border-radius: 4px;")
        self.btn_save.clicked.connect(self.save_values)
        btn_layout.addWidget(self.btn_save)

        main_layout.addLayout(btn_layout)

    def _init_tab_general(self) -> None:
        layout = QVBoxLayout(self.tab_general)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        grp_startup = QGroupBox("Khởi động & Trải nghiệm")
        grp_layout = QVBoxLayout(grp_startup)
        grp_layout.setSpacing(10)

        self.chk_startup = QCheckBox("Tự động khởi động cùng Windows")
        self.chk_minimize_tray = QCheckBox("Thu nhỏ xuống khay hệ thống khi mở")
        self.chk_restore_clipboard = QCheckBox("Khôi phục Clipboard gốc sau khi dịch xong tại chỗ")
        self.chk_notifications = QCheckBox("Hiện thông báo nổi khi dịch (Translating / Success)")

        grp_layout.addWidget(self.chk_startup)
        grp_layout.addWidget(self.chk_minimize_tray)
        grp_layout.addWidget(self.chk_restore_clipboard)
        grp_layout.addWidget(self.chk_notifications)
        layout.addWidget(grp_startup)

        grp_privacy = QGroupBox("Bảo mật & Lịch sử dịch")
        grp_privacy_layout = QVBoxLayout(grp_privacy)
        grp_privacy_layout.setSpacing(10)

        self.chk_history = QCheckBox("Lưu lại lịch sử các đoạn văn bản đã dịch")
        self.chk_privacy = QCheckBox("Chế độ riêng tư (Không lưu lịch sử & không ghi log nội dung)")

        grp_privacy_layout.addWidget(self.chk_history)
        grp_privacy_layout.addWidget(self.chk_privacy)
        layout.addWidget(grp_privacy)

        layout.addStretch()

    def _init_tab_translation(self) -> None:
        layout = QVBoxLayout(self.tab_translation)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(12)

        # Source Language
        self.combo_src_lang = QComboBox()
        for code, name in SUPPORTED_LANGUAGES.items():
            self.combo_src_lang.addItem(f"{name} ({code})", code)
        form.addRow("Ngôn ngữ nguồn:", self.combo_src_lang)

        # Target Language
        self.combo_tgt_lang = QComboBox()
        for code, name in SUPPORTED_LANGUAGES.items():
            if code != "auto":
                self.combo_tgt_lang.addItem(f"{name} ({code})", code)
        form.addRow("Ngôn ngữ đích mặc định:", self.combo_tgt_lang)

        # Provider
        self.combo_provider = QComboBox()
        for prov_id, prov_name in PROVIDERS.items():
            self.combo_provider.addItem(prov_name, prov_id)
        self.combo_provider.currentIndexChanged.connect(self._on_provider_changed)
        form.addRow("Nguồn dịch (Provider):", self.combo_provider)

        # Model
        self.edit_model = QLineEdit()
        form.addRow("Mô hình AI (Model):", self.edit_model)

        # Mode
        self.combo_mode = QComboBox()
        self.combo_mode.addItem("Dịch thuật (Translate)", "translate")
        self.combo_mode.addItem("Viết lại / Trau chuốt câu (AI Rewrite)", "rewrite")
        form.addRow("Chế độ xử lý:", self.combo_mode)

        # Rewrite Style
        style_display = {
            "natural": "Tự nhiên (Khuyên dùng)",
            "formal": "Trang trọng / Lịch sự",
            "casual": "Thân mật / Giao tiếp",
            "polish": "Trau chuốt / Chuẩn ngữ pháp",
        }
        self.combo_style = QComboBox()
        for style in REWRITE_STYLES:
            self.combo_style.addItem(style_display.get(style, style.capitalize()), style)
        form.addRow("Văn phong viết lại:", self.combo_style)

        layout.addLayout(form)
        layout.addStretch()

    def _init_tab_hotkeys(self) -> None:
        layout = QVBoxLayout(self.tab_hotkeys)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        info_lbl = QLabel("Tùy chỉnh phím tắt toàn hệ thống (định dạng: <ctrl>+<shift>+t):")
        info_lbl.setStyleSheet("color: #64748B; font-size: 11px;")
        layout.addWidget(info_lbl)

        form = QFormLayout()
        form.setSpacing(12)

        # Main Translate
        self.edit_hk_translate = QLineEdit()
        self.chk_hk_translate = QCheckBox("Bật")
        hk_trans_box = QHBoxLayout()
        hk_trans_box.addWidget(self.edit_hk_translate)
        hk_trans_box.addWidget(self.chk_hk_translate)
        form.addRow("Dịch văn bản bôi đen:", hk_trans_box)

        # English
        self.edit_hk_en = QLineEdit()
        self.chk_hk_en = QCheckBox("Bật")
        hk_en_box = QHBoxLayout()
        hk_en_box.addWidget(self.edit_hk_en)
        hk_en_box.addWidget(self.chk_hk_en)
        form.addRow("Dịch nhanh sang Tiếng Anh:", hk_en_box)

        # Chinese
        self.edit_hk_zh = QLineEdit()
        self.chk_hk_zh = QCheckBox("Bật")
        hk_zh_box = QHBoxLayout()
        hk_zh_box.addWidget(self.edit_hk_zh)
        hk_zh_box.addWidget(self.chk_hk_zh)
        form.addRow("Dịch nhanh sang Tiếng Trung:", hk_zh_box)

        # Japanese
        self.edit_hk_ja = QLineEdit()
        self.chk_hk_ja = QCheckBox("Bật")
        hk_ja_box = QHBoxLayout()
        hk_ja_box.addWidget(self.edit_hk_ja)
        hk_ja_box.addWidget(self.chk_hk_ja)
        form.addRow("Dịch nhanh sang Tiếng Nhật:", hk_ja_box)

        layout.addLayout(form)
        layout.addStretch()

    def _init_tab_keys(self) -> None:
        layout = QVBoxLayout(self.tab_keys)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        info_lbl = QLabel(
            "API Key được mã hóa và lưu an toàn trong Windows Credential Manager.\n"
            "Google Translate hoạt động miễn phí tức thì mà không cần bất kỳ API key nào."
        )
        info_lbl.setStyleSheet("color: #64748B; font-size: 11px;")
        layout.addWidget(info_lbl)

        form = QFormLayout()
        form.setSpacing(12)

        # Gemini
        self.edit_key_gemini = QLineEdit()
        self.edit_key_gemini.setEchoMode(QLineEdit.Password)
        self.edit_key_gemini.setPlaceholderText("Nhập Google Gemini API Key (AIza...)")
        self.lbl_status_gemini = QLabel("Chưa cài đặt")
        self.lbl_status_gemini.setStyleSheet("color: #94A3B8;")
        gemini_box = QHBoxLayout()
        gemini_box.addWidget(self.edit_key_gemini)
        gemini_box.addWidget(self.lbl_status_gemini)
        form.addRow("Gemini API Key:", gemini_box)

        # OpenAI
        self.edit_key_openai = QLineEdit()
        self.edit_key_openai.setEchoMode(QLineEdit.Password)
        self.edit_key_openai.setPlaceholderText("Nhập OpenAI API Key (sk-...)")
        self.lbl_status_openai = QLabel("Chưa cài đặt")
        self.lbl_status_openai.setStyleSheet("color: #94A3B8;")
        openai_box = QHBoxLayout()
        openai_box.addWidget(self.edit_key_openai)
        openai_box.addWidget(self.lbl_status_openai)
        form.addRow("OpenAI API Key:", openai_box)

        # Google Cloud
        self.edit_key_google = QLineEdit()
        self.edit_key_google.setEchoMode(QLineEdit.Password)
        self.edit_key_google.setPlaceholderText("Tùy chọn - Google Cloud Translation API Key")
        self.lbl_status_google = QLabel("Đang dùng miễn phí (OK)")
        self.lbl_status_google.setStyleSheet("color: #22C55E;")
        google_box = QHBoxLayout()
        google_box.addWidget(self.edit_key_google)
        google_box.addWidget(self.lbl_status_google)
        form.addRow("Google Cloud Key:", google_box)

        layout.addLayout(form)
        layout.addStretch()

    def _on_provider_changed(self) -> None:
        prov_id = self.combo_provider.currentData()
        if prov_id == "gemini":
            self.edit_model.setText(self.config.get("gemini_model", "gemini-2.5-flash"))
        elif prov_id == "openai":
            self.edit_model.setText(self.config.get("openai_model", "gpt-4o-mini"))
        elif prov_id == "google":
            self.edit_model.setText("google-translate-v2")

    def load_values(self) -> None:
        """Populates UI controls with current configuration values."""
        # General
        self.chk_startup.setChecked(is_run_at_startup_enabled())
        self.chk_minimize_tray.setChecked(self.config.get("minimize_to_tray", True))
        self.chk_restore_clipboard.setChecked(self.config.get("restore_clipboard", True))
        self.chk_notifications.setChecked(self.config.get("show_notifications", True))
        self.chk_privacy.setChecked(self.config.get("privacy_mode", False))
        self.chk_history.setChecked(self.config.get("history_enabled", True))

        # Translation
        src = self.config.get("source_language", "auto")
        idx = self.combo_src_lang.findData(src)
        if idx >= 0:
            self.combo_src_lang.setCurrentIndex(idx)

        tgt = self.config.get("target_language", "en")
        idx = self.combo_tgt_lang.findData(tgt)
        if idx >= 0:
            self.combo_tgt_lang.setCurrentIndex(idx)

        prov = self.config.get("provider", "gemini")
        idx = self.combo_provider.findData(prov)
        if idx >= 0:
            self.combo_provider.setCurrentIndex(idx)

        mode = self.config.get("mode", "translate")
        idx = self.combo_mode.findData(mode)
        if idx >= 0:
            self.combo_mode.setCurrentIndex(idx)

        style = self.config.get("rewrite_style", "natural")
        idx = self.combo_style.findData(style)
        if idx >= 0:
            self.combo_style.setCurrentIndex(idx)

        self._on_provider_changed()

        # Hotkeys
        hotkeys = self.config.get_hotkeys()
        hk_trans = hotkeys.get("translate", {})
        self.edit_hk_translate.setText(hk_trans.get("key", "<ctrl>+<shift>+t"))
        self.chk_hk_translate.setChecked(hk_trans.get("enabled", True))

        hk_en = hotkeys.get("translate_en", {})
        self.edit_hk_en.setText(hk_en.get("key", "<ctrl>+<shift>+e"))
        self.chk_hk_en.setChecked(hk_en.get("enabled", True))

        hk_zh = hotkeys.get("translate_zh", {})
        self.edit_hk_zh.setText(hk_zh.get("key", "<ctrl>+<shift>+c"))
        self.chk_hk_zh.setChecked(hk_zh.get("enabled", True))

        hk_ja = hotkeys.get("translate_ja", {})
        self.edit_hk_ja.setText(hk_ja.get("key", "<ctrl>+<shift>+j"))
        self.chk_hk_ja.setChecked(hk_ja.get("enabled", True))

        # API Keys
        key_gemini = self.config.get_api_key("gemini")
        if key_gemini:
            self.edit_key_gemini.setText(key_gemini)
            self.lbl_status_gemini.setText("Đã cài đặt")
            self.lbl_status_gemini.setStyleSheet("color: #22C55E;")
        else:
            self.lbl_status_gemini.setText("Chưa cài đặt")
            self.lbl_status_gemini.setStyleSheet("color: #94A3B8;")

        key_openai = self.config.get_api_key("openai")
        if key_openai:
            self.edit_key_openai.setText(key_openai)
            self.lbl_status_openai.setText("Đã cài đặt")
            self.lbl_status_openai.setStyleSheet("color: #22C55E;")
        else:
            self.lbl_status_openai.setText("Chưa cài đặt")
            self.lbl_status_openai.setStyleSheet("color: #94A3B8;")

        key_google = self.config.get_api_key("google")
        if key_google:
            self.edit_key_google.setText(key_google)
            self.lbl_status_google.setText("Đã có Google Cloud Key")
            self.lbl_status_google.setStyleSheet("color: #22C55E;")
        else:
            self.lbl_status_google.setText("Đang dùng miễn phí (OK)")
            self.lbl_status_google.setStyleSheet("color: #22C55E;")

    def save_values(self) -> None:
        """Saves values from UI to configuration and Windows Credential Manager."""
        # General
        start_with_win = self.chk_startup.isChecked()
        set_run_at_startup(start_with_win)
        self.config.set("start_with_windows", start_with_win)
        self.config.set("minimize_to_tray", self.chk_minimize_tray.isChecked())
        self.config.set("restore_clipboard", self.chk_restore_clipboard.isChecked())
        self.config.set("show_notifications", self.chk_notifications.isChecked())

        privacy_on = self.chk_privacy.isChecked()
        self.config.set("privacy_mode", privacy_on)
        set_privacy_mode(privacy_on)

        self.config.set("history_enabled", self.chk_history.isChecked())

        # Translation
        self.config.set("source_language", self.combo_src_lang.currentData())
        self.config.set("target_language", self.combo_tgt_lang.currentData())
        prov = self.combo_provider.currentData()
        self.config.set("provider", prov)
        self.config.set("mode", self.combo_mode.currentData())
        self.config.set("rewrite_style", self.combo_style.currentData())

        model_val = self.edit_model.text().strip()
        if prov == "gemini":
            self.config.set("gemini_model", model_val or "gemini-2.5-flash")
        elif prov == "openai":
            self.config.set("openai_model", model_val or "gpt-4o-mini")

        # Hotkeys
        self.config.set_hotkey("translate", self.edit_hk_translate.text().strip(), self.chk_hk_translate.isChecked())
        self.config.set_hotkey("translate_en", self.edit_hk_en.text().strip(), self.chk_hk_en.isChecked())
        self.config.set_hotkey("translate_zh", self.edit_hk_zh.text().strip(), self.chk_hk_zh.isChecked())
        self.config.set_hotkey("translate_ja", self.edit_hk_ja.text().strip(), self.chk_hk_ja.isChecked())

        # API Keys (Stored in Windows Credential Manager)
        gemini_k = self.edit_key_gemini.text().strip()
        self.config.set_api_key("gemini", gemini_k)

        openai_k = self.edit_key_openai.text().strip()
        self.config.set_api_key("openai", openai_k)

        google_k = self.edit_key_google.text().strip()
        self.config.set_api_key("google", google_k)

        self.config.save()
        self.settings_applied.emit()
        logger.info("Settings saved and applied successfully")
        self.accept()

    def _reset_defaults(self) -> None:
        """Prompts user and restores default settings."""
        reply = QMessageBox.question(
            self,
            "Khôi phục mặc định",
            "Bạn có chắc chắn muốn khôi phục toàn bộ cài đặt về mặc định ban đầu không?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.config.reset_defaults()
            self.load_values()
