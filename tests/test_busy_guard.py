"""Unit tests for the translation concurrency guard.

The guard is exercised through the real ApplicationController methods bound to a
lightweight stub, so no QApplication is needed to test the locking behaviour.
"""

import time
import threading
import unittest
from types import SimpleNamespace

from main import ApplicationController, MIN_TRIGGER_INTERVAL_S


def _make_guard(last_trigger_time: float = 0.0) -> SimpleNamespace:
    """Builds a stub carrying only the state the guard touches."""
    stub = SimpleNamespace(
        _busy_lock=threading.Lock(),
        _is_busy=False,
        _last_trigger_time=last_trigger_time,
    )
    stub.acquire = ApplicationController._acquire_busy.__get__(stub)
    stub.release = ApplicationController._release_busy.__get__(stub)
    return stub


class TestBusyGuard(unittest.TestCase):

    def test_first_acquire_succeeds(self):
        guard = _make_guard()
        self.assertTrue(guard.acquire())
        self.assertTrue(guard._is_busy)

    def test_second_acquire_is_refused_while_busy(self):
        guard = _make_guard()
        self.assertTrue(guard.acquire())
        self.assertFalse(guard.acquire(), "A second pipeline must not start while one runs")

    def test_release_allows_a_later_acquire(self):
        guard = _make_guard()
        self.assertTrue(guard.acquire())
        guard.release()
        self.assertFalse(guard._is_busy)

        # Past the bounce window, the next trigger is accepted
        guard._last_trigger_time = time.monotonic() - (MIN_TRIGGER_INTERVAL_S * 2)
        self.assertTrue(guard.acquire())

    def test_key_bounce_is_rejected_even_after_release(self):
        """Two presses milliseconds apart are one intent, not two."""
        guard = _make_guard()
        self.assertTrue(guard.acquire())
        guard.release()
        self.assertFalse(guard.acquire(), "A trigger inside the bounce window must be dropped")

    def test_only_one_of_many_racing_threads_wins(self):
        """The original bug: the flag was set inside the worker, so two
        threads could both pass the check and both drive the clipboard."""
        guard = _make_guard()
        winners = []
        barrier = threading.Barrier(12)

        def contend():
            barrier.wait()
            if guard.acquire():
                winners.append(threading.current_thread().name)

        threads = [threading.Thread(target=contend) for _ in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(winners), 1, f"Expected exactly one winner, got {len(winners)}")


if __name__ == "__main__":
    unittest.main()
