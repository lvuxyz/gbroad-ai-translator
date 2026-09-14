"""Unit tests for foreground application detection and profile matching."""

import unittest
from core.app_context import (
    AppContext,
    EMPTY_CONTEXT,
    get_foreground_app,
    get_cursor_position,
    match_profile,
)


class TestAppContext(unittest.TestCase):

    def test_foreground_app_is_readable(self):
        context = get_foreground_app()
        self.assertIsInstance(context, AppContext)
        self.assertIsInstance(context.process_name, str)
        self.assertIsInstance(context.window_title, str)
        if context.process_name:
            self.assertTrue(context.process_name.endswith(".exe"))
            self.assertEqual(context.process_name, context.process_name.lower())

    def test_cursor_position_is_a_point(self):
        position = get_cursor_position()
        self.assertIsNotNone(position)
        x, y = position
        self.assertIsInstance(x, int)
        self.assertIsInstance(y, int)

    def test_empty_context_is_not_known(self):
        self.assertFalse(EMPTY_CONTEXT.is_known)
        self.assertTrue(AppContext("chrome.exe", "").is_known)


class TestProfileMatching(unittest.TestCase):

    def setUp(self):
        self.profiles = {
            "discord.exe": {"enabled": True, "target_language": "en", "rewrite_style": "casual"},
            "outlook.exe": {"enabled": True, "target_language": "en", "rewrite_style": "formal"},
            "code.exe": {"enabled": False, "target_language": "en"},
        }

    def test_matching_profile_is_returned(self):
        profile = match_profile(AppContext("discord.exe", "chat"), self.profiles)
        self.assertIsNotNone(profile)
        self.assertEqual(profile["rewrite_style"], "casual")

    def test_disabled_profile_does_not_apply(self):
        self.assertIsNone(match_profile(AppContext("code.exe", "editor"), self.profiles))

    def test_unlisted_application_falls_through(self):
        self.assertIsNone(match_profile(AppContext("zalo.exe", "chat"), self.profiles))

    def test_unknown_context_falls_through(self):
        self.assertIsNone(match_profile(EMPTY_CONTEXT, self.profiles))

    def test_empty_profile_table_falls_through(self):
        self.assertIsNone(match_profile(AppContext("discord.exe", "chat"), {}))

    def test_window_title_does_not_affect_matching(self):
        """Titles change constantly, so they must not drive profile selection."""
        first = match_profile(AppContext("discord.exe", "#general"), self.profiles)
        second = match_profile(AppContext("discord.exe", "#random"), self.profiles)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
