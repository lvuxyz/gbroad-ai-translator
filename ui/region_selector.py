"""Full-screen overlay for dragging out a screen region to translate.

Spans every monitor as one surface so a region can be dragged across a monitor
boundary. Escape or a right-click cancels; a drag smaller than a few pixels is
treated as a misclick rather than an empty selection.
"""

from typing import Optional, Tuple, Callable

from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, QRect, QPoint, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QGuiApplication, QFont, QCursor

from utils.logger import get_logger

logger = get_logger()

MIN_REGION_PX = 8


class RegionSelector(QWidget):
    """Translucent overlay that reports the rectangle the user drags."""

    region_selected = Signal(int, int, int, int)  # left, top, width, height
    selection_cancelled = Signal()

    def __init__(self):
        super().__init__()

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(QCursor(Qt.CrossCursor))

        self._origin: Optional[QPoint] = None
        self._current: Optional[QPoint] = None
        self._finished = False

        # One window covering the union of every screen
        geometry = self._virtual_geometry()
        self.setGeometry(geometry)
        self._virtual_origin = geometry.topLeft()

    @staticmethod
    def _virtual_geometry() -> QRect:
        """Returns the rectangle enclosing all monitors."""
        combined = QRect()
        for screen in QGuiApplication.screens():
            combined = combined.united(screen.geometry())
        if combined.isNull():
            primary = QGuiApplication.primaryScreen()
            combined = primary.geometry() if primary else QRect(0, 0, 1920, 1080)
        return combined

    # --- painting ---
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        overlay = QColor(12, 17, 23, 110)
        selection = self._selection_rect()

        if selection is None or selection.isEmpty():
            painter.fillRect(self.rect(), overlay)
            self._draw_hint(painter)
            return

        # Dim everything except the chosen rectangle
        for band in (
            QRect(0, 0, self.width(), selection.top()),
            QRect(0, selection.bottom() + 1, self.width(), self.height() - selection.bottom() - 1),
            QRect(0, selection.top(), selection.left(), selection.height()),
            QRect(selection.right() + 1, selection.top(),
                  self.width() - selection.right() - 1, selection.height()),
        ):
            if band.isValid():
                painter.fillRect(band, overlay)

        pen = QPen(QColor("#38BDF8"), 1.5)
        painter.setPen(pen)
        painter.drawRect(selection.adjusted(0, 0, -1, -1))

        self._draw_size_badge(painter, selection)

    def _draw_hint(self, painter: QPainter) -> None:
        painter.setPen(QColor(233, 240, 246))
        painter.setFont(QFont("Segoe UI", 13))
        painter.drawText(
            self.rect(),
            Qt.AlignCenter,
            "Kéo chuột để chọn vùng cần dịch  ·  Esc để hủy"
        )

    def _draw_size_badge(self, painter: QPainter, selection: QRect) -> None:
        label = f"{selection.width()} × {selection.height()}"
        painter.setFont(QFont("Segoe UI", 9))
        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(label)
        badge = QRect(selection.left(), selection.top() - 24, text_width + 14, 20)

        # Keep the badge on screen when the selection starts at the very top
        if badge.top() < 0:
            badge.moveTop(selection.top() + 4)

        painter.fillRect(badge, QColor(12, 17, 23, 220))
        painter.setPen(QColor(233, 240, 246))
        painter.drawText(badge, Qt.AlignCenter, label)

    # --- interaction ---
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.RightButton:
            self._cancel()
            return
        if event.button() == Qt.LeftButton:
            self._origin = event.position().toPoint()
            self._current = self._origin
            self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._origin is not None:
            self._current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.LeftButton or self._origin is None:
            return

        self._current = event.position().toPoint()
        selection = self._selection_rect()
        self._origin = None

        if selection is None or selection.width() < MIN_REGION_PX or selection.height() < MIN_REGION_PX:
            logger.info("Region selection discarded as too small")
            self._cancel()
            return

        # Widget coordinates back to desktop coordinates
        left = selection.left() + self._virtual_origin.x()
        top = selection.top() + self._virtual_origin.y()

        self._finished = True
        self.close()
        logger.info("Region selected: %dx%d at (%d, %d)", selection.width(), selection.height(), left, top)
        self.region_selected.emit(left, top, selection.width(), selection.height())

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self._cancel()

    def closeEvent(self, event) -> None:
        # Closing by any other route still counts as a cancellation
        if not self._finished:
            self._finished = True
            self.selection_cancelled.emit()
        super().closeEvent(event)

    def _cancel(self) -> None:
        if self._finished:
            return
        self._finished = True
        self.close()
        logger.info("Region selection cancelled")
        self.selection_cancelled.emit()

    def _selection_rect(self) -> Optional[QRect]:
        if self._origin is None or self._current is None:
            return None
        return QRect(self._origin, self._current).normalized()


def select_region(
    on_selected: Callable[[int, int, int, int], None],
    on_cancelled: Optional[Callable[[], None]] = None
) -> RegionSelector:
    """Shows the overlay and reports the chosen rectangle.

    The selector is returned so the caller can keep a reference; dropping it
    would let Python collect the window mid-selection.
    """
    selector = RegionSelector()
    selector.region_selected.connect(on_selected)
    if on_cancelled is not None:
        selector.selection_cancelled.connect(on_cancelled)

    selector.showFullScreen()
    selector.raise_()
    selector.activateWindow()
    return selector
