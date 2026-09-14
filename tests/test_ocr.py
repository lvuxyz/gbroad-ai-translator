"""Unit tests for screen-region OCR.

Recognition runs against a bitmap this test draws itself with GDI, so the
assertions do not depend on whatever happens to be on screen.
"""

import unittest

from core import ocr


def _render_text_bitmap(text: str, width: int = 800, height: int = 140) -> bytes:
    """Draws text into an off-screen bitmap and returns it as BMP bytes."""
    import os
    import tempfile
    import win32con
    import win32gui
    import win32ui

    screen_handle = win32gui.GetDC(0)
    screen_dc = win32ui.CreateDCFromHandle(screen_handle)
    mem_dc = screen_dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(screen_dc, width, height)
    mem_dc.SelectObject(bitmap)
    mem_dc.FillSolidRect((0, 0, width, height), 0xFFFFFF)
    mem_dc.SelectObject(win32ui.CreateFont({"name": "Segoe UI", "height": 38}))
    mem_dc.SetTextColor(0x000000)
    mem_dc.SetBkMode(win32con.TRANSPARENT)
    mem_dc.TextOut(24, 45, text)

    handle, path = tempfile.mkstemp(suffix=".bmp")
    os.close(handle)
    try:
        bitmap.SaveBitmapFile(mem_dc, path)
        with open(path, "rb") as f:
            return f.read()
    finally:
        os.unlink(path)
        win32gui.DeleteObject(bitmap.GetHandle())
        mem_dc.DeleteDC()
        screen_dc.DeleteDC()
        win32gui.ReleaseDC(0, screen_handle)


@unittest.skipUnless(ocr.is_available(), "OCR engine or capture support unavailable")
class TestOcr(unittest.TestCase):

    def test_recognises_rendered_text(self):
        image = _render_text_bitmap("Hello world 2026")
        self.assertIn("Hello", ocr.recognize(image))

    def test_blank_image_yields_no_text(self):
        image = _render_text_bitmap("")
        self.assertEqual(ocr.recognize(image).strip(), "")

    def test_capture_region_returns_a_bitmap(self):
        data = ocr.capture_region(0, 0, 120, 80)
        self.assertGreater(len(data), 0)
        self.assertEqual(data[:2], b"BM", "Expected a BMP header")

    def test_capture_rejects_an_empty_region(self):
        with self.assertRaises(ValueError):
            ocr.capture_region(0, 0, 0, 50)
        with self.assertRaises(ValueError):
            ocr.capture_region(0, 0, 50, -1)

    def test_unknown_language_falls_back_instead_of_failing(self):
        """A missing language pack must not turn into an exception."""
        image = _render_text_bitmap("Fallback check")
        self.assertIn("Fallback", ocr.recognize(image, language="xx-XX"))


class TestOcrAvailability(unittest.TestCase):

    def test_availability_reports_a_reason_when_unavailable(self):
        if ocr.is_available():
            self.assertEqual(ocr.unavailable_reason(), "")
        else:
            self.assertIn("OCR", ocr.unavailable_reason())


if __name__ == "__main__":
    unittest.main()
