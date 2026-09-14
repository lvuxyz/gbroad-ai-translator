"""Floating non-intrusive Toast Notification for Windows AI Translation Tool.

Renders above the Windows taskbar without stealing window focus,
providing immediate visual feedback on translation status.
"""

from typing import Optional
from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout, QGraphicsDropShadowEffect
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QColor, QFont, QGuiApplication


class FloatingToast(QWidget):
    """Semi-transparent floating toast widget that doesn't steal focus."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # Frameless, stay on top, tool window (no taskbar item), do not accept focus
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint
            | Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

        # Layout
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(14, 10, 16, 10)
        self.layout.setSpacing(10)

        # Status indicator icon / dot
        self.indicator_label = QLabel(self)
        self.indicator_label.setFixedSize(12, 12)
        self.layout.addWidget(self.indicator_label)

        # Message label
        self.message_label = QLabel(self)
        self.message_label.setFont(QFont("Segoe UI", 10, QFont.Medium))
        self.message_label.setStyleSheet("color: #FFFFFF;")
        self.layout.addWidget(self.message_label)

        # Soft drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setColor(QColor(0, 0, 0, 120))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

    def _set_style(self, bg_color: str, border_color: str, dot_color: str) -> None:
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
            }}
        """)
        self.indicator_label.setStyleSheet(f"""
            background-color: {dot_color};
            border-radius: 6px;
            border: none;
        """)

    def _position_at_bottom_right(self) -> None:
        """Positions toast in bottom-right corner above Windows taskbar."""
        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.adjustSize()
            x = geo.x() + geo.width() - self.width() - 24
            y = geo.y() + geo.height() - self.height() - 24
            self.move(QPoint(x, y))

    def show_translating(self, message: str = "Đang dịch...") -> None:
        """Displays ongoing translation status."""
        self._timer.stop()
        self.message_label.setText(message)
        self._set_style(
            bg_color="rgba(24, 24, 27, 0.94)",
            border_color="rgba(14, 165, 233, 0.6)",
            dot_color="#0284C7"  # Sky blue
        )
        self._position_at_bottom_right()
        self.show()

    def show_success(self, message: str, duration_ms: int = 2500) -> None:
        """Displays success status and auto-hides."""
        self.message_label.setText(message)
        self._set_style(
            bg_color="rgba(24, 24, 27, 0.94)",
            border_color="rgba(34, 197, 94, 0.6)",
            dot_color="#22C55E"  # Green
        )
        self._position_at_bottom_right()
        self.show()
        self._timer.start(duration_ms)

    def show_error(self, message: str, duration_ms: int = 4000) -> None:
        """Displays error feedback and auto-hides."""
        self.message_label.setText(message)
        self._set_style(
            bg_color="rgba(24, 24, 27, 0.96)",
            border_color="rgba(239, 68, 68, 0.7)",
            dot_color="#EF4444"  # Red
        )
        self._position_at_bottom_right()
        self.show()
        self._timer.start(duration_ms)

    def show_info(self, message: str, duration_ms: int = 2500) -> None:
        """Displays informational message."""
        self.message_label.setText(message)
        self._set_style(
            bg_color="rgba(24, 24, 27, 0.94)",
            border_color="rgba(168, 85, 247, 0.6)",
            dot_color="#A855F7"  # Purple
        )
        self._position_at_bottom_right()
        self.show()
        self._timer.start(duration_ms)


# Singleton instance
_toast_instance: Optional[FloatingToast] = None


def get_toast() -> FloatingToast:
    """Gets or initializes the global FloatingToast instance."""
    global _toast_instance
    if _toast_instance is None:
        _toast_instance = FloatingToast()
    return _toast_instance
