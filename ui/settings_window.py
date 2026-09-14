"""Settings Window for Windows AI Translation Tool.

Provides user interface for general settings, language defaults,
global hotkeys, and secure API Key management via Windows Credential Manager.
"""

from typing import Optional, Callable
from PySide6.QtWidgets import (
    QDialog, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QCheckBox, QComboBox, QLineEdit, QPushButton,
    QLabel, QGroupBox, QMessageBox, QSpacerItem, QSizePolicy,
    QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCompleter
from PySide6.QtGui import QFont

from config import (
    get_config,
    DEFAULT_CONFIG,
    SUPPORTED_LANGUAGES,
    TARGET_LANGUAGES,
    PROVIDERS,
    REWRITE_STYLES,
    DEFAULT_MODELS
)
from utils.startup import is_run_at_startup_enabled, set_run_at_startup
from utils.logger import set_privacy_mode, get_logger
from ui.resources import create_app_icon

logger = get_logger()

GLOSSARY_HINT = (
    "Từ khóa giữ nguyên khi dịch: tên thương hiệu, tên sản phẩm, biệt danh, thuật ngữ nội bộ.\n"
    "Để trống cột Dịch thành nếu muốn giữ nguyên từ gốc; "
    "điền vào nếu muốn ép một cách dịch cố định."
)



def _language_combo(languages: dict) -> QComboBox:
    """Builds a type-to-filter language picker.

    With 56 languages a plain dropdown means a long scroll, so the combo is
    editable and completes on the language name as the user types. It stays
    restricted to the listed languages — the edit box filters, it does not
    accept arbitrary input.
    """
    combo = QComboBox()
    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.NoInsert)
    combo.setMaxVisibleItems(16)
    for code, name in languages.items():
        combo.addItem(f"{name} ({code})", code)

    completer = combo.completer()
    if completer is not None:
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
    return combo


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

        # Tab 4: Per-application profiles
        self.tab_profiles = QWidget()
        self._init_tab_profiles()
        self.tab_widget.addTab(self.tab_profiles, "Theo ứng dụng")

        # Tab 5: Glossary
        self.tab_glossary = QWidget()
        self._init_tab_glossary()
        self.tab_widget.addTab(self.tab_glossary, "Thuật ngữ")

        # Tab 6: API Keys
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
        self.combo_src_lang = _language_combo(SUPPORTED_LANGUAGES)
        form.addRow("Ngôn ngữ nguồn:", self.combo_src_lang)

        # Target Language
        self.combo_tgt_lang = _language_combo(TARGET_LANGUAGES)
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

        # Two-way translation
        grp_auto = QGroupBox("Dịch hai chiều tự động")
        auto_layout = QVBoxLayout(grp_auto)
        auto_layout.setSpacing(9)

        self.chk_auto_swap = QCheckBox(
            "Tự chọn chiều dịch theo nội dung (một phím tắt cho cả hai chiều)"
        )
        auto_layout.addWidget(self.chk_auto_swap)

        pair_row = QHBoxLayout()
        pair_row.setSpacing(8)
        self.combo_auto_primary = _language_combo(TARGET_LANGUAGES)
        self.combo_auto_secondary = _language_combo(TARGET_LANGUAGES)
        pair_row.addWidget(QLabel("Cặp ngôn ngữ:"))
        pair_row.addWidget(self.combo_auto_primary)
        pair_row.addWidget(QLabel("⇄"))
        pair_row.addWidget(self.combo_auto_secondary)
        pair_row.addStretch()
        auto_layout.addLayout(pair_row)

        hint_auto = QLabel(
            "Gõ tiếng Việt thì ra ngôn ngữ còn lại, và ngược lại. "
            "Phím tắt gán cứng ngôn ngữ (Ctrl+Alt+E/C/J) không bị ảnh hưởng."
        )
        hint_auto.setWordWrap(True)
        hint_auto.setStyleSheet("color: #64748B; font-size: 11px;")
        auto_layout.addWidget(hint_auto)
        layout.addWidget(grp_auto)

        # Preview popup
        grp_preview = QGroupBox("Xem trước kết quả")
        preview_layout = QVBoxLayout(grp_preview)
        preview_layout.setSpacing(9)

        self.chk_preview = QCheckBox("Hiện popup xem trước thay vì thay chữ ngay lập tức")
        preview_layout.addWidget(self.chk_preview)

        timeout_row = QHBoxLayout()
        timeout_row.addWidget(QLabel("Tự đóng sau:"))
        self.spin_preview_timeout = QSpinBox()
        self.spin_preview_timeout.setRange(0, 120)
        self.spin_preview_timeout.setSuffix(" giây")
        self.spin_preview_timeout.setSpecialValueText("Không tự đóng")
        self.spin_preview_timeout.setFixedWidth(140)
        timeout_row.addWidget(self.spin_preview_timeout)
        timeout_row.addStretch()
        preview_layout.addLayout(timeout_row)
        layout.addWidget(grp_preview)

        layout.addStretch()

    def _init_tab_hotkeys(self) -> None:
        layout = QVBoxLayout(self.tab_hotkeys)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        info_lbl = QLabel(
            "Tùy chỉnh phím tắt toàn hệ thống (định dạng: <ctrl>+<alt>+t). "
            "Mỗi phím tắt cần ít nhất một phím bổ trợ."
        )
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

        # OCR
        self.edit_hk_ocr = QLineEdit()
        self.chk_hk_ocr = QCheckBox("Bật")
        hk_ocr_box = QHBoxLayout()
        hk_ocr_box.addWidget(self.edit_hk_ocr)
        hk_ocr_box.addWidget(self.chk_hk_ocr)
        form.addRow("Dịch vùng màn hình (OCR):", hk_ocr_box)

        layout.addLayout(form)
        layout.addStretch()

    def _init_tab_profiles(self) -> None:
        layout = QVBoxLayout(self.tab_profiles)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        info = QLabel(
            "Đặt ngôn ngữ và văn phong riêng cho từng ứng dụng. "
            "Nhập tên file chạy, ví dụ discord.exe, outlook.exe, code.exe.\n"
            "Ứng dụng không có trong danh sách sẽ dùng cài đặt chung."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #64748B; font-size: 11px;")
        layout.addWidget(info)

        self.table_profiles = QTableWidget(0, 4, self)
        self.table_profiles.setHorizontalHeaderLabels(
            ["Ứng dụng (.exe)", "Ngôn ngữ đích", "Chế độ", "Văn phong"]
        )
        self.table_profiles.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_profiles.verticalHeader().setVisible(False)
        self.table_profiles.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.table_profiles)

        buttons = QHBoxLayout()
        btn_add = QPushButton("Thêm ứng dụng")
        btn_add.clicked.connect(lambda: self._add_profile_row("", "en", "translate", "natural"))
        buttons.addWidget(btn_add)

        btn_current = QPushButton("Thêm ứng dụng đang mở")
        btn_current.clicked.connect(self._add_current_app)
        buttons.addWidget(btn_current)

        btn_remove = QPushButton("Xóa dòng")
        btn_remove.clicked.connect(lambda: self._remove_selected_rows(self.table_profiles))
        buttons.addWidget(btn_remove)
        buttons.addStretch()
        layout.addLayout(buttons)

    def _init_tab_glossary(self) -> None:
        layout = QVBoxLayout(self.tab_glossary)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        info = QLabel(GLOSSARY_HINT)
        info.setWordWrap(True)
        info.setStyleSheet("color: #64748B; font-size: 11px;")
        layout.addWidget(info)

        self.table_glossary = QTableWidget(0, 3, self)
        self.table_glossary.setHorizontalHeaderLabels(
            ["Từ gốc", "Dịch thành (để trống = giữ nguyên)", "Phân biệt hoa/thường"]
        )
        self.table_glossary.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_glossary.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_glossary.verticalHeader().setVisible(False)
        self.table_glossary.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.table_glossary)

        buttons = QHBoxLayout()
        btn_add = QPushButton("Thêm thuật ngữ")
        btn_add.clicked.connect(lambda: self._add_glossary_row("", "", False))
        buttons.addWidget(btn_add)

        btn_remove = QPushButton("Xóa dòng")
        btn_remove.clicked.connect(lambda: self._remove_selected_rows(self.table_glossary))
        buttons.addWidget(btn_remove)
        buttons.addStretch()
        layout.addLayout(buttons)

    # --- table row helpers ---
    def _add_profile_row(self, app_name: str, target: str, mode: str, style: str) -> None:
        row = self.table_profiles.rowCount()
        self.table_profiles.insertRow(row)
        self.table_profiles.setItem(row, 0, QTableWidgetItem(app_name))

        combo_lang = _language_combo(TARGET_LANGUAGES)
        index = combo_lang.findData(target)
        if index >= 0:
            combo_lang.setCurrentIndex(index)
        self.table_profiles.setCellWidget(row, 1, combo_lang)

        combo_mode = QComboBox()
        combo_mode.addItem("Dịch thuật", "translate")
        combo_mode.addItem("Viết lại", "rewrite")
        idx_mode = combo_mode.findData(mode)
        if idx_mode >= 0:
            combo_mode.setCurrentIndex(idx_mode)
        self.table_profiles.setCellWidget(row, 2, combo_mode)

        combo_style = QComboBox()
        for st in REWRITE_STYLES:
            combo_style.addItem(st.capitalize(), st)
        idx_style = combo_style.findData(style)
        if idx_style >= 0:
            combo_style.setCurrentIndex(idx_style)
        self.table_profiles.setCellWidget(row, 3, combo_style)

    def _add_current_app(self) -> None:
        """Fills in the application the user last had in front."""
        from core.app_context import get_foreground_app
        context = get_foreground_app()
        name = context.process_name
        if not name or name.startswith("python"):
            QMessageBox.information(
                self, "Không xác định được ứng dụng",
                "Hãy mở ứng dụng cần cấu hình, rồi quay lại đây và bấm lại nút này."
            )
            return
        self._add_profile_row(
            name,
            self.config.get("target_language", "en"),
            self.config.get("mode", "translate"),
            self.config.get("rewrite_style", "natural"),
        )

    def _add_glossary_row(self, term: str, replacement: str, match_case: bool) -> None:
        row = self.table_glossary.rowCount()
        self.table_glossary.insertRow(row)
        self.table_glossary.setItem(row, 0, QTableWidgetItem(term))
        self.table_glossary.setItem(row, 1, QTableWidgetItem(replacement))

        check = QCheckBox()
        check.setChecked(match_case)
        wrapper = QWidget()
        wrapper_layout = QHBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setAlignment(Qt.AlignCenter)
        wrapper_layout.addWidget(check)
        self.table_glossary.setCellWidget(row, 2, wrapper)

    @staticmethod
    def _remove_selected_rows(table: QTableWidget) -> None:
        for index in sorted({i.row() for i in table.selectedIndexes()}, reverse=True):
            table.removeRow(index)

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

        # Two-way translation
        auto = self.config.get_auto_swap()
        self.chk_auto_swap.setChecked(bool(auto.get("enabled", False)))
        for combo, key, default in (
            (self.combo_auto_primary, "primary", "vi"),
            (self.combo_auto_secondary, "secondary", "en"),
        ):
            idx = combo.findData(auto.get(key, default))
            if idx >= 0:
                combo.setCurrentIndex(idx)

        # Preview popup
        preview = self.config.get("preview_popup", {})
        self.chk_preview.setChecked(bool(preview.get("enabled", False)))
        self.spin_preview_timeout.setValue(int(preview.get("timeout_seconds", 12)))

        # Per-application profiles
        self.table_profiles.setRowCount(0)
        for app_name, profile in self.config.get_app_profiles().items():
            self._add_profile_row(
                app_name,
                profile.get("target_language", self.config.get("target_language", "en")),
                profile.get("mode", "translate"),
                profile.get("rewrite_style", "natural"),
            )

        # Glossary
        self.table_glossary.setRowCount(0)
        for entry in self.config.get_glossary():
            self._add_glossary_row(
                entry.get("term", ""),
                entry.get("replacement", ""),
                bool(entry.get("match_case", False)),
            )

        # Hotkeys
        hotkeys = self.config.get_hotkeys()
        hk_trans = hotkeys.get("translate", {})
        self.edit_hk_translate.setText(hk_trans.get("key", DEFAULT_CONFIG["hotkeys"]["translate"]["key"]))
        self.chk_hk_translate.setChecked(hk_trans.get("enabled", True))

        hk_en = hotkeys.get("translate_en", {})
        self.edit_hk_en.setText(hk_en.get("key", DEFAULT_CONFIG["hotkeys"]["translate_en"]["key"]))
        self.chk_hk_en.setChecked(hk_en.get("enabled", True))

        hk_zh = hotkeys.get("translate_zh", {})
        self.edit_hk_zh.setText(hk_zh.get("key", DEFAULT_CONFIG["hotkeys"]["translate_zh"]["key"]))
        self.chk_hk_zh.setChecked(hk_zh.get("enabled", True))

        hk_ja = hotkeys.get("translate_ja", {})
        self.edit_hk_ja.setText(hk_ja.get("key", DEFAULT_CONFIG["hotkeys"]["translate_ja"]["key"]))
        self.chk_hk_ja.setChecked(hk_ja.get("enabled", True))

        hk_ocr = hotkeys.get("translate_ocr", {})
        self.edit_hk_ocr.setText(hk_ocr.get("key", DEFAULT_CONFIG["hotkeys"]["translate_ocr"]["key"]))
        self.chk_hk_ocr.setChecked(hk_ocr.get("enabled", True))

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

    def _collect_profiles(self) -> dict:
        """Reads the per-application table back into config shape."""
        profiles = {}
        for row in range(self.table_profiles.rowCount()):
            name_item = self.table_profiles.item(row, 0)
            app_name = (name_item.text() if name_item else "").strip().lower()
            if not app_name:
                continue
            if not app_name.endswith(".exe"):
                app_name += ".exe"

            lang_widget = self.table_profiles.cellWidget(row, 1)
            mode_widget = self.table_profiles.cellWidget(row, 2)
            style_widget = self.table_profiles.cellWidget(row, 3)

            profiles[app_name] = {
                "enabled": True,
                "target_language": lang_widget.currentData() if lang_widget else "en",
                "mode": mode_widget.currentData() if mode_widget else "translate",
                "rewrite_style": style_widget.currentData() if style_widget else "natural",
            }
        return profiles

    def _collect_glossary(self) -> list:
        """Reads the glossary table back into config shape."""
        entries = []
        seen = set()
        for row in range(self.table_glossary.rowCount()):
            term_item = self.table_glossary.item(row, 0)
            term = (term_item.text() if term_item else "").strip()
            if not term or term.lower() in seen:
                continue
            seen.add(term.lower())

            repl_item = self.table_glossary.item(row, 1)
            wrapper = self.table_glossary.cellWidget(row, 2)
            check = wrapper.findChild(QCheckBox) if wrapper else None

            entries.append({
                "term": term,
                "replacement": (repl_item.text() if repl_item else "").strip(),
                "match_case": bool(check.isChecked()) if check else False,
                "enabled": True,
            })
        return entries

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

        # Two-way translation
        self.config.set("auto_swap", {
            "enabled": self.chk_auto_swap.isChecked(),
            "primary": self.combo_auto_primary.currentData(),
            "secondary": self.combo_auto_secondary.currentData(),
        })

        # Preview popup
        self.config.set("preview_popup", {
            "enabled": self.chk_preview.isChecked(),
            "timeout_seconds": self.spin_preview_timeout.value(),
        })

        self.config.set("app_profiles", self._collect_profiles())
        self.config.set("glossary", self._collect_glossary())

        # Hotkeys
        self.config.set_hotkey("translate", self.edit_hk_translate.text().strip(), self.chk_hk_translate.isChecked())
        self.config.set_hotkey("translate_en", self.edit_hk_en.text().strip(), self.chk_hk_en.isChecked())
        self.config.set_hotkey("translate_zh", self.edit_hk_zh.text().strip(), self.chk_hk_zh.isChecked())
        self.config.set_hotkey("translate_ja", self.edit_hk_ja.text().strip(), self.chk_hk_ja.isChecked())
        self.config.set_hotkey("translate_ocr", self.edit_hk_ocr.text().strip(), self.chk_hk_ocr.isChecked())

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
