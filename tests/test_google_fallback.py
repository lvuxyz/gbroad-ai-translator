"""Unit tests for the MyMemory fallback tier of the Google provider."""

import unittest
from unittest.mock import patch, MagicMock

from providers.base import TranslationError
from providers.google import GoogleTranslateProvider


def _response(payload, status_code=200):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = payload
    mock.raise_for_status.return_value = None
    return mock


class TestMyMemoryFallback(unittest.TestCase):

    def setUp(self):
        self.provider = GoogleTranslateProvider()

    def test_auto_source_is_detected_not_assumed(self):
        """Assuming a fixed source breaks translating *into* that language."""
        captured = {}

        def fake_get(url, params=None, **kwargs):
            captured["langpair"] = params["langpair"]
            return _response({
                "responseStatus": 200,
                "responseData": {"translatedText": "Tôi đang học"},
            })

        with patch("httpx.Client.get", side_effect=fake_get):
            result = self.provider._translate_mymemory("I am learning", "auto", "vi")

        self.assertEqual(captured["langpair"], "en|vi")
        self.assertEqual(result, "Tôi đang học")

    def test_same_source_and_target_returns_the_text_unchanged(self):
        """A vi->vi pair is rejected by the service and pointless anyway."""
        with patch("httpx.Client.get") as mock_get:
            result = self.provider._translate_mymemory("Tôi đang học lập trình", "auto", "vi")
        self.assertEqual(result, "Tôi đang học lập trình")
        mock_get.assert_not_called()

    def test_error_string_in_the_translation_field_is_rejected(self):
        """The service answers 200 with the error inside translatedText."""
        payload = {
            "responseStatus": 200,
            "responseData": {"translatedText": "PLEASE SELECT TWO DISTINCT LANGUAGES"},
        }
        with patch("httpx.Client.get", return_value=_response(payload)):
            with self.assertRaises(TranslationError) as ctx:
                self.provider._translate_mymemory("hello", "en", "vi")
        self.assertIn("PLEASE SELECT TWO DISTINCT LANGUAGES", str(ctx.exception))

    def test_other_error_markers_are_rejected(self):
        for marker in (
            "INVALID LANGUAGE PAIR",
            "QUERY LENGTH LIMIT EXCEEDED",
            "YOU USED ALL AVAILABLE FREE TRANSLATIONS FOR TODAY",
        ):
            payload = {"responseStatus": 200, "responseData": {"translatedText": marker}}
            with patch("httpx.Client.get", return_value=_response(payload)):
                with self.assertRaises(TranslationError, msg=marker):
                    self.provider._translate_mymemory("hello", "en", "vi")

    def test_non_200_response_status_is_rejected(self):
        payload = {
            "responseStatus": 403,
            "responseDetails": "INVALID EMAIL PROVIDED",
            "responseData": {"translatedText": "whatever"},
        }
        with patch("httpx.Client.get", return_value=_response(payload)):
            with self.assertRaises(TranslationError) as ctx:
                self.provider._translate_mymemory("hello", "en", "vi")
        self.assertIn("INVALID EMAIL PROVIDED", str(ctx.exception))

    def test_undetectable_source_raises_rather_than_guessing(self):
        with patch("httpx.Client.get") as mock_get:
            with self.assertRaises(TranslationError):
                self.provider._translate_mymemory("12345 !!!", "auto", "en")
        mock_get.assert_not_called()

    def test_a_normal_translation_passes_through(self):
        payload = {
            "responseStatus": 200,
            "responseData": {"translatedText": "I&#39;m learning"},
        }
        with patch("httpx.Client.get", return_value=_response(payload)):
            result = self.provider._translate_mymemory("Tôi đang học", "vi", "en")
        self.assertEqual(result, "I'm learning", "HTML entities should be unescaped")


if __name__ == "__main__":
    unittest.main()
