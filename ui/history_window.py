"""Translation History Window for Windows AI Translation Tool.

Provides searchable history list, detailed text inspector,
clipboard copying, record deletion, and database clearing.
"""

from typing import Optional, List, Dict, Any
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QPlainTextEdit, QLabel, QMessageBox, QAbstractItemView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
import pyperclip

from database import get_database
from ui.resources import create_app_icon
from utils.logger import get_logger

logger = get_logger()


class HistoryWindow(QDialog):
    """Dialog displaying historical translation queries and outputs."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = get_database()
        self._current_records: List[Dict[str, Any]] = []

        self.setWindowTitle("AI Translator - Lịch sử dịch thuật")
        self.setWindowIcon(create_app_icon(32))
        self.resize(800, 520)
        self.setMinimumSize(640, 400)

        self._init_ui()
        self.refresh_history()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Top Bar: Search & Clear
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Tìm kiếm nội dung hoặc mã ngôn ngữ (vd: vi, en)...")
        self.search_edit.textChanged.connect(self._on_search_changed)
        top_bar.addWidget(self.search_edit, stretch=1)

        self.btn_refresh = QPushButton("Làm mới", self)
        self.btn_refresh.clicked.connect(self.refresh_history)
        top_bar.addWidget(self.btn_refresh)

        self.btn_clear = QPushButton("Xóa toàn bộ lịch sử", self)
        self.btn_clear.setStyleSheet("color: #EF4444; font-weight: 500;")
        self.btn_clear.clicked.connect(self._clear_all_history)
        top_bar.addWidget(self.btn_clear)

        main_layout.addLayout(top_bar)

        # Middle Splitter: Table on left/top, Detail preview on right/bottom
        splitter = QSplitter(Qt.Vertical, self)

        # Table
        self.table = QTableWidget(self)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Văn bản gốc", "Bản dịch", "Ngôn ngữ", "Thời gian"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        splitter.addWidget(self.table)

        # Detail Pane
        detail_widget = QWidget(self)
        detail_layout = QHBoxLayout(detail_widget)
        detail_layout.setContentsMargins(0, 8, 0, 0)
        detail_layout.setSpacing(12)

        # Left detail: Original
        orig_box = QVBoxLayout()
        orig_box.addWidget(QLabel("<b>Văn bản gốc:</b>", self))
        self.orig_text_edit = QPlainTextEdit(self)
        self.orig_text_edit.setReadOnly(True)
        orig_box.addWidget(self.orig_text_edit)
        detail_layout.addLayout(orig_box)

        # Right detail: Translation
        trans_box = QVBoxLayout()
        trans_box.addWidget(QLabel("<b>Bản dịch:</b>", self))
        self.trans_text_edit = QPlainTextEdit(self)
        self.trans_text_edit.setReadOnly(True)
        trans_box.addWidget(self.trans_text_edit)
        detail_layout.addLayout(trans_box)

        splitter.addWidget(detail_widget)
        splitter.setSizes([300, 160])
        main_layout.addWidget(splitter, stretch=1)

        # Bottom Bar: Actions
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(10)

        self.btn_copy_trans = QPushButton("Sao chép bản dịch", self)
        self.btn_copy_trans.clicked.connect(self._copy_translation)
        bottom_bar.addWidget(self.btn_copy_trans)

        self.btn_copy_orig = QPushButton("Sao chép bản gốc", self)
        self.btn_copy_orig.clicked.connect(self._copy_original)
        bottom_bar.addWidget(self.btn_copy_orig)

        self.btn_delete_item = QPushButton("Xóa dòng này", self)
        self.btn_delete_item.clicked.connect(self._delete_selected)
        bottom_bar.addWidget(self.btn_delete_item)

        bottom_bar.addStretch()

        self.lbl_count = QLabel("0 mục", self)
        self.lbl_count.setStyleSheet("color: #64748B;")
        bottom_bar.addWidget(self.lbl_count)

        self.btn_close = QPushButton("Đóng", self)
        self.btn_close.clicked.connect(self.accept)
        bottom_bar.addWidget(self.btn_close)

        main_layout.addLayout(bottom_bar)

    def refresh_history(self) -> None:
        """Loads entries from SQLite database matching current search term."""
        query = self.search_edit.text().strip()
        self._current_records = self.db.search_translations(query=query, limit=200)

        self.table.setRowCount(len(self._current_records))
        for row_idx, rec in enumerate(self._current_records):
            item_id = QTableWidgetItem(str(rec["id"]))
            item_src = QTableWidgetItem(rec["source_text"][:80].replace("\n", " "))
            item_tgt = QTableWidgetItem(rec["translated_text"][:80].replace("\n", " "))
            lang_str = f"{rec['source_language']} → {rec['target_language']}"
            item_lang = QTableWidgetItem(lang_str)
            item_time = QTableWidgetItem(str(rec["created_at"])[:16])

            self.table.setItem(row_idx, 0, item_id)
            self.table.setItem(row_idx, 1, item_src)
            self.table.setItem(row_idx, 2, item_tgt)
            self.table.setItem(row_idx, 3, item_lang)
            self.table.setItem(row_idx, 4, item_time)

        self.lbl_count.setText(f"{len(self._current_records)} mục")
        if self._current_records:
            self.table.selectRow(0)
        else:
            self.orig_text_edit.clear()
            self.trans_text_edit.clear()

    def _on_search_changed(self) -> None:
        self.refresh_history()

    def _on_selection_changed(self) -> None:
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return

        row = selected_rows[0].row()
        if 0 <= row < len(self._current_records):
            rec = self._current_records[row]
            self.orig_text_edit.setPlainText(rec["source_text"])
            self.trans_text_edit.setPlainText(rec["translated_text"])

    def _copy_translation(self) -> None:
        text = self.trans_text_edit.toPlainText()
        if text:
            pyperclip.copy(text)
            logger.info("Copied translation to clipboard from history")

    def _copy_original(self) -> None:
        text = self.orig_text_edit.toPlainText()
        if text:
            pyperclip.copy(text)
            logger.info("Copied original text to clipboard from history")

    def _delete_selected(self) -> None:
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return

        row = selected_rows[0].row()
        if 0 <= row < len(self._current_records):
            rec = self._current_records[row]
            item_id = rec["id"]
            self.db.delete_translation(item_id)
            self.refresh_history()

    def _clear_all_history(self) -> None:
        reply = QMessageBox.question(
            self,
            "Xóa lịch sử",
            "Bạn có chắc chắn muốn xóa vĩnh viễn toàn bộ lịch sử dịch không?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.db.clear_history()
            self.refresh_history()
