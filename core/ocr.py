"""Screen-region OCR using the Windows built-in recognizer.

Some applications draw their own text — canvas-based editors, remote desktop
sessions, full-screen games, images inside a chat — and offer nothing the
clipboard can copy. Reading the pixels is the only route into that text.

Windows.Media.Ocr runs entirely on the machine, so this costs no API quota and
works offline. Recognition of a selection-sized region takes roughly 10 ms.

Two Windows details shape this module:

* The WinRT runtime must be initialised in a multi-threaded apartment, and Qt
  has already put the main thread in a single-threaded one. All OCR therefore
  runs on its own thread with its own apartment and its own event loop.
* Recognition quality depends on which language packs the user has installed.
  Missing packs are a configuration problem, not a failure, so they surface as
  a clear message rather than an exception.
"""

import asyncio
import ctypes
import threading
from ctypes import wintypes
from typing import Optional, List, Tuple

from utils.logger import get_logger

logger = get_logger()

_import_error: Optional[str] = None

try:
    import win32con
    import win32gui
    import win32ui
    OCR_CAPTURE_AVAILABLE = True
except ImportError as e:  # pragma: no cover - pywin32 is a hard requirement
    OCR_CAPTURE_AVAILABLE = False
    _import_error = str(e)

try:
    from winrt.runtime import init_apartment, ApartmentType
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.globalization import Language
    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.storage.streams import InMemoryRandomAccessStream, DataWriter
    OCR_ENGINE_AVAILABLE = True
except ImportError as e:
    OCR_ENGINE_AVAILABLE = False
    _import_error = str(e)


class OcrUnavailableError(RuntimeError):
    """Raised when OCR cannot run on this machine."""


def is_available() -> bool:
    """True when both screen capture and the OCR engine can be used."""
    return OCR_CAPTURE_AVAILABLE and OCR_ENGINE_AVAILABLE


def unavailable_reason() -> str:
    """Explains, in the user's terms, why OCR cannot run."""
    if is_available():
        return ""
    return (
        "Không dùng được OCR trên máy này. "
        f"Thiếu thư viện: {_import_error or 'không rõ'}. "
        "Cài lại bằng: python -m pip install -r requirements.txt"
    )


def capture_region(left: int, top: int, width: int, height: int) -> bytes:
    """Grabs a screen rectangle and returns it as BMP bytes.

    GDI BitBlt is used rather than a Qt screen grab so the capture does not
    depend on a Qt screen object, and so it can run off the GUI thread.
    """
    if not OCR_CAPTURE_AVAILABLE:
        raise OcrUnavailableError(unavailable_reason())

    if width <= 0 or height <= 0:
        raise ValueError("Capture region must have a positive width and height")

    screen_handle = win32gui.GetDC(0)
    screen_dc = win32ui.CreateDCFromHandle(screen_handle)
    mem_dc = None
    bitmap = None
    try:
        mem_dc = screen_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(screen_dc, width, height)
        mem_dc.SelectObject(bitmap)
        mem_dc.BitBlt((0, 0), (width, height), screen_dc, (left, top), win32con.SRCCOPY)

        # SaveBitmapFile is the only BMP serialiser pywin32 exposes, so the
        # bytes travel through a temporary file.
        import tempfile
        import os
        handle, path = tempfile.mkstemp(suffix=".bmp")
        os.close(handle)
        try:
            bitmap.SaveBitmapFile(mem_dc, path)
            with open(path, "rb") as f:
                return f.read()
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
    finally:
        if bitmap is not None:
            win32gui.DeleteObject(bitmap.GetHandle())
        if mem_dc is not None:
            mem_dc.DeleteDC()
        screen_dc.DeleteDC()
        win32gui.ReleaseDC(0, screen_handle)


def recognize(image_bytes: bytes, language: Optional[str] = None) -> str:
    """Runs OCR over encoded image bytes and returns the recognised text.

    Blocks until recognition finishes, so call it from a worker thread.
    """
    if not OCR_ENGINE_AVAILABLE:
        raise OcrUnavailableError(unavailable_reason())

    result: List[object] = [None]

    def worker() -> None:
        try:
            # A fresh apartment per thread; Qt owns an STA on the main thread
            try:
                init_apartment(ApartmentType.MULTI_THREADED)
            except Exception:
                pass  # Already initialised on this thread
            result[0] = asyncio.run(_recognize_async(image_bytes, language))
        except Exception as e:  # Carried across the thread boundary
            result[0] = e

    thread = threading.Thread(target=worker, name="OcrWorker", daemon=True)
    thread.start()
    thread.join(timeout=30.0)

    if thread.is_alive():
        raise OcrUnavailableError("OCR không phản hồi sau 30 giây.")

    outcome = result[0]
    if isinstance(outcome, BaseException):
        raise OcrUnavailableError(f"OCR thất bại: {outcome}") from outcome
    return outcome or ""


async def _recognize_async(image_bytes: bytes, language: Optional[str]) -> str:
    """Decodes the image and hands it to the recognizer."""
    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream.get_output_stream_at(0))
    writer.write_bytes(image_bytes)
    await writer.store_async()

    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()

    engine = _create_engine(language)
    if engine is None:
        raise OcrUnavailableError(
            "Windows chưa cài gói ngôn ngữ nào cho OCR. "
            "Vào Settings > Time & Language > Language & region, "
            "chọn ngôn ngữ và bật thành phần Optical character recognition."
        )

    logger.info("Running OCR with recognizer language: %s", engine.recognizer_language.language_tag)
    ocr_result = await engine.recognize_async(bitmap)
    return (ocr_result.text or "").strip()


def _create_engine(language: Optional[str]):
    """Builds a recognizer, preferring the requested language."""
    if language and language != "auto":
        try:
            candidate = Language(language)
            if OcrEngine.is_language_supported(candidate):
                return OcrEngine.try_create_from_language(candidate)
            logger.warning("No OCR language pack installed for '%s'; using user profile", language)
        except Exception as e:
            logger.warning("Could not select OCR language '%s': %s", language, e)

    return OcrEngine.try_create_from_user_profile_languages()


def capture_and_recognize(
    region: Tuple[int, int, int, int],
    language: Optional[str] = None
) -> str:
    """Captures a screen rectangle and returns the text found in it."""
    left, top, width, height = region
    image = capture_region(left, top, width, height)
    logger.info("Captured %dx%d region for OCR (%d bytes)", width, height, len(image))
    return recognize(image, language)
