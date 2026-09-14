"""Caret-anchored preview of a translation, shown before anything is replaced.

Replacing the selection outright leaves no way back: the target application's
undo rarely restores a programmatic paste cleanly, and the original text is
gone. Showing the result first turns the hotkey from a gamble into a decision.

The window must never take focus. Stealing it would move the caret out of the
text box the translation is destined for, which is the whole reason the earlier
toast was built the same way.
"""

from typing import Optional, Callable, Tuple

from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QGraphicsDropShadowEffect, QComboBox, QSizePolicy, QFrame
)
from PySide6.QtCore import Qt, QTimer, QPoint, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication

from utils.logger import get_logger

logger = get_logger()

MAX_WIDTH = 460
MIN_WIDTH = 360
MAX_PREVIEW_CHARS = 600


class PreviewPopup(QWidget):
    """Shows a translation with Replace / Copy / Retarget actions."""

    replace_requested = Signal()
    copy_requested = Signal()
    retranslate_requested = Signal(str)   # target language code
    dismissed = Signal()

    def __init__(self):
        super().__init__()

        self.setWindowFlags(
            Qt.WindowStaysOnTopHint
            | Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMaximumWidth(MAX_WIDTH)
        self.setMinimumWidth(MIN_WIDTH)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)
        self._languages: list = []
        self._suppress_language_signal = False

        self._build_ui()

    def _build_ui(self) -> None:
        # The top-level window stays transparent so the card can have rounded
        # corners and a shadow. A bare QWidget does not paint its own
        # stylesheet background, which is why the card is a QFrame.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 12)

        self.card = QFrame(self)
        self.card.setObjectName("previewCard")
        outer.addWidget(self.card)

        root = QVBoxLayout(self.card)
        root.setContentsMargins(16, 13, 16, 13)
        root.setSpacing(9)

        self.source_label = QLabel(self.card)
        self.source_label.setWordWrap(True)
        self.source_label.setFont(QFont("Segoe UI", 8))
        self.source_label.setStyleSheet("color: #7C8FA3; background: transparent; border: none;")
        root.addWidget(self.source_label)

        self.result_label = QLabel(self.card)
        self.result_label.setWordWrap(True)
        self.result_label.setFont(QFont("Segoe UI", 11))
        self.result_label.setStyleSheet(
            "color: #F1F5F9; background: transparent; border: none;"
        )
        self.result_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        root.addWidget(self.result_label)

        actions = QHBoxLayout()
        actions.setSpacing(7)

        self.language_combo = QComboBox(self.card)
        self.language_combo.setFont(QFont("Segoe UI", 9))
        self.language_combo.setObjectName("previewLanguage")
        # Applied directly rather than inherited, so the native Windows style
        # cannot win the background back.
        self.language_combo.setStyleSheet(
            "QComboBox { background-color: #1E293B; color: #E2E8F0;"
            " border: 1px solid #334155; border-radius: 4px; padding: 4px 7px; }"
            "QComboBox::drop-down { border: none; width: 16px; }"
            "QComboBox QAbstractItemView { background-color: #1E293B; color: #E2E8F0;"
            " selection-background-color: #0284C7; border: 1px solid #334155; }"
        )
        self.language_combo.setFixedWidth(140)
        self.language_combo.setFocusPolicy(Qt.NoFocus)
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)
        actions.addWidget(self.language_combo)

        actions.addStretch()

        self.btn_copy = self._make_button("Chép", primary=False)
        self.btn_copy.clicked.connect(self._on_copy)
        actions.addWidget(self.btn_copy)

        self.btn_replace = self._make_button("Thay thế", primary=True)
        self.btn_replace.clicked.connect(self._on_replace)
        actions.addWidget(self.btn_replace)

        root.addLayout(actions)

        self.hint_label = QLabel("", self.card)
        self.hint_label.setFont(QFont("Segoe UI", 8))
        self.hint_label.setStyleSheet("color: #64748B; background: transparent; border: none;")
        root.addWidget(self.hint_label)

        self.setStyleSheet("""
            QFrame#previewCard {
                background-color: #0F172A;
                border: 1px solid #38BDF8;
                border-radius: 10px;
            }
            QComboBox#previewLanguage {
                background-color: #1E293B;
                color: #E2E8F0;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 7px;
            }
            QComboBox#previewLanguage::drop-down { border: none; width: 16px; }
            QComboBox#previewLanguage QAbstractItemView {
                background-color: #1E293B;
                color: #E2E8F0;
                selection-background-color: #0284C7;
                border: 1px solid #334155;
            }
        """)

        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(26)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 5)
        self.card.setGraphicsEffect(shadow)

    def _make_button(self, text: str, primary: bool) -> QPushButton:
        button = QPushButton(text, self.card)
        button.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        button.setCursor(Qt.PointingHandCursor)
        button.setFocusPolicy(Qt.NoFocus)
        if primary:
            button.setStyleSheet("""
                QPushButton { background: #0284C7; color: white;
                              border: none; border-radius: 4px; padding: 5px 15px; }
                QPushButton:hover { background: #0369A1; }
            """)
        else:
            button.setStyleSheet("""
                QPushButton { background: #1E293B; color: #CBD5E1;
                              border: 1px solid #334155; border-radius: 4px; padding: 5px 13px; }
                QPushButton:hover { background: #283548; }
            """)
        return button

    # --- public API ---
    def show_translation(
        self,
        source_text: str,
        translated_text: str,
        target_language: str,
        languages: dict,
        anchor: Optional[Tuple[int, int]] = None,
        timeout_seconds: int = 12,
    ) -> None:
        """Displays a result and starts the dismissal timer."""
        self._timer.stop()

        self.source_label.setText(self._elide(source_text, 140))
        self.result_label.setText(self._elide(translated_text, MAX_PREVIEW_CHARS))
        self._populate_languages(languages, target_language)
        self.hint_label.setText(
            f"Tự đóng sau {timeout_seconds} giây" if timeout_seconds > 0
            else "Chọn một hành động để đóng"
        )

        self.adjustSize()
        self._position_near(anchor)
        self.show()
        self.raise_()

        if timeout_seconds > 0:
            self._timer.start(timeout_seconds * 1000)

    def dismiss(self) -> None:
        """Hides the popup without emitting an action."""
        self._timer.stop()
        self.hide()

    # --- internals ---
    def _populate_languages(self, languages: dict, current: str) -> None:
        self._suppress_language_signal = True
        try:
            if self._languages != list(languages.items()):
                self.language_combo.clear()
                self._languages = list(languages.items())
                for code, name in self._languages:
                    self.language_combo.addItem(name, code)

            index = self.language_combo.findData(current)
            if index >= 0:
                self.language_combo.setCurrentIndex(index)
        finally:
            self._suppress_language_signal = False

    @staticmethod
    def _elide(text: str, limit: int) -> str:
        collapsed = " ".join(text.split())
        if len(collapsed) <= limit:
            return collapsed
        return collapsed[:limit].rstrip() + "…"

    def _position_near(self, anchor: Optional[Tuple[int, int]]) -> None:
        """Places the popup below the caret, kept inside the screen."""
        screen = QGuiApplication.screenAt(QPoint(*anchor)) if anchor else None
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        available = screen.availableGeometry()

        if anchor is None:
            x = available.x() + available.width() - self.width() - 24
            y = available.y() + available.height() - self.height() - 24
        else:
            x, y = anchor
            y += 22  # clear the line the caret sits on

            # Flip above the caret when there is no room below
            if y + self.height() > available.bottom():
                y = anchor[1] - self.height() - 12
            x = max(available.left() + 8, min(x, available.right() - self.width() - 8))
            y = max(available.top() + 8, min(y, available.bottom() - self.height() - 8))

        self.move(QPoint(int(x), int(y)))

    def _on_replace(self) -> None:
        self._timer.stop()
        self.hide()
        self.replace_requested.emit()

    def _on_copy(self) -> None:
        self._timer.stop()
        self.hide()
        self.copy_requested.emit()

    def _on_language_changed(self, index: int) -> None:
        if self._suppress_language_signal or index < 0:
            return
        code = self.language_combo.itemData(index)
        if code:
            self._timer.stop()
            self.retranslate_requested.emit(code)

    def _on_timeout(self) -> None:
        self.hide()
        self.dismissed.emit()


_popup_instance: Optional[PreviewPopup] = None


def get_preview_popup() -> PreviewPopup:
    """Gets or initializes the global PreviewPopup instance."""
    global _popup_instance
    if _popup_instance is None:
        _popup_instance = PreviewPopup()
    return _popup_instance
