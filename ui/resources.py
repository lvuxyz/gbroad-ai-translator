"""Programmatic application icons and resources using PySide6 QPainter.

Provides crisp high-DPI icons for system tray, windows, and installer
without requiring external image asset dependencies.
"""

from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QPen, QFont
from PySide6.QtCore import Qt, QRectF
from pathlib import Path


def create_app_icon(size: int = 64) -> QIcon:
    """Generates a modern stylized Translation icon."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # Background rounded rectangle with gradient-like solid color
    rect = QRectF(2, 2, size - 4, size - 4)
    painter.setBrush(QBrush(QColor(14, 116, 144)))  # Teal-700
    painter.setPen(QPen(QColor(6, 182, 212), max(1, size // 32)))  # Cyan-500 border
    painter.drawRoundedRect(rect, size * 0.22, size * 0.22)

    # Foreground 'AI' / Translation glyph
    painter.setPen(QColor(255, 255, 255))
    font = QFont("Segoe UI", max(8, int(size * 0.38)), QFont.Bold)
    painter.setFont(font)
    painter.drawText(rect, Qt.AlignCenter, "AI")

    painter.end()
    return QIcon(pixmap)


def create_tray_icon(size: int = 32) -> QIcon:
    """Generates a crisp high-contrast icon for the Windows system tray."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # Inner circular badge
    rect = QRectF(2, 2, size - 4, size - 4)
    painter.setBrush(QBrush(QColor(2, 132, 199)))  # Sky-600
    painter.setPen(QPen(QColor(255, 255, 255), 1.5))
    painter.drawEllipse(rect)

    # 'T' glyph for Translate
    painter.setPen(QColor(255, 255, 255))
    font = QFont("Segoe UI", max(8, int(size * 0.50)), QFont.Black)
    painter.setFont(font)
    painter.drawText(rect, Qt.AlignCenter, "T")

    painter.end()
    return QIcon(pixmap)


def save_icon_to_file(path: Path, size: int = 64) -> None:
    """Saves the programmatic icon to disk as a PNG or ICO file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    icon = create_app_icon(size)
    pixmap = icon.pixmap(size, size)
    pixmap.save(str(path))
