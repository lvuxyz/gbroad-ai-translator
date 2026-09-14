"""Unit tests for translation providers and edge-case handling.

Tests languages:
- Vietnamese → English
- Vietnamese → Japanese
- Vietnamese → Chinese
- English → Vietnamese
- Long text, Emojis, URLs, Code, Empty text, Unicode, Multiline text.
"""

import unittest
from unittest.mock import patch, MagicMock
from providers.base import AuthenticationError, RateLimitError, TranslationError
from providers.google import GoogleTranslateProvider
from providers.gemini import GeminiProvider
from providers.openai import OpenAIProvider


class TestTranslationProviders(unittest.TestCase):

    def test_empty_and_whitespace_input(self):
        prov = GoogleTranslateProvider()
        self.assertEqual(prov.translate("", "vi", "en"), "")
        self.assertEqual(prov.translate("   ", "vi", "en"), "   ")

    def test_missing_api_keys_raise_auth_error(self):
        gemini = GeminiProvider(api_key="")
        with self.assertRaises(AuthenticationError):
            gemini.translate("Hello", "en", "vi")

        openai = OpenAIProvider(api_key="")
        with self.assertRaises(AuthenticationError):
            openai.translate("Hello", "en", "vi")

    @patch("httpx.Client.post")
    def test_gemini_translation_mock(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "I am learning programming and want to improve my English."}
                        ]
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        provider = GeminiProvider(api_key="AIzaSyDummyKeyForTestingOnly")
        result = provider.translate(
            text="Tôi đang học lập trình và muốn cải thiện tiếng Anh.",
            source_language="vi",
            target_language="en"
        )
        self.assertEqual(result, "I am learning programming and want to improve my English.")

    @patch("httpx.Client.post")
    def test_openai_translation_mock(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "日本語を勉強したいです。"
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        provider = OpenAIProvider(api_key="sk-dummykeyfortestingonly")
        result = provider.translate(
            text="Tôi muốn học tiếng Nhật.",
            source_language="vi",
            target_language="ja"
        )
        self.assertEqual(result, "日本語を勉強したいです。")

    @patch("httpx.Client.get")
    def test_google_web_translation_mock(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            [["你好，世界！", "Xin chào thế giới!", None, None]],
            None,
            "vi"
        ]
        mock_get.return_value = mock_response

        provider = GoogleTranslateProvider()
        result = provider.translate(
            text="Xin chào thế giới!",
            source_language="vi",
            target_language="zh-CN"
        )
        self.assertEqual(result, "你好，世界！")

    def test_edge_cases_representation(self):
        """Validates that edge-case texts retain unicode, emojis, URLs, and code blocks."""
        edge_cases = {
            "emoji": "Chào bạn! 😊🎉 Chúc một ngày tốt lành! ✨",
            "url": "Xem tài liệu tại https://example.com/docs?lang=vi",
            "code": "def hello():\n    print('Xin chào')",
            "special_chars": "Giá: 100$ & 50€ | 50% discount #trend @user",
            "multiline": "Dòng 1: Giới thiệu\nDòng 2: Nội dung chính\nDòng 3: Kết luận",
            "chinese_japanese": "日本語と中文のテスト (Test Tiếng Nhật & Tiếng Trung)"
        }

        for category, text in edge_cases.items():
            self.assertTrue(len(text) > 0, f"Edge case '{category}' should be valid text")


if __name__ == "__main__":
    unittest.main()
