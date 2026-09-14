"""Unit tests for script-based language detection and two-way targeting."""

import unittest
from core.language_detect import detect_language, is_vietnamese, resolve_auto_target


class TestLanguageDetection(unittest.TestCase):

    def test_vietnamese_is_recognised_by_its_diacritics(self):
        for text in [
            "Tôi đang học lập trình",
            "Xin chào các bạn",
            "Cảm ơn bạn rất nhiều",
            "Hôm nay trời đẹp quá",
            "Đây là một câu tiếng Việt",
        ]:
            self.assertEqual(detect_language(text), "vi", text)
            self.assertTrue(is_vietnamese(text))

    def test_a_single_vietnamese_character_is_enough(self):
        self.assertEqual(detect_language("Hello anh ơi"), "vi")

    def test_unaccented_latin_reads_as_english(self):
        for text in ["I am learning programming", "Hello world", "Good morning"]:
            self.assertEqual(detect_language(text), "en", text)
            self.assertFalse(is_vietnamese(text))

    def test_cjk_and_other_scripts(self):
        cases = {
            "日本語を勉強しています": "ja",
            "こんにちは": "ja",
            "カタカナ": "ja",
            "我正在学习编程": "zh-CN",
            "안녕하세요": "ko",
            "สวัสดีครับ": "th",
            "Привет мир": "ru",
            "مرحبا بالعالم": "ar",
            "Γειά σου κόσμε": "el",
        }
        for text, expected in cases.items():
            self.assertEqual(detect_language(text), expected, text)

    def test_kana_wins_over_kanji(self):
        """Japanese text is mostly shared characters plus a little kana."""
        self.assertEqual(detect_language("私は学生です"), "ja")

    def test_text_without_a_signal_returns_none(self):
        for text in ["", "   ", "123 456", "!!! ???", "😊🎉✨", "42"]:
            self.assertIsNone(detect_language(text), repr(text))

    def test_urls_and_handles_do_not_decide_the_language(self):
        self.assertIsNone(detect_language("https://example.com/docs?lang=vi"))
        self.assertIsNone(detect_language("@user #trending"))
        self.assertEqual(detect_language("Gửi cho https://example.com nhé"), "vi")

    def test_code_fences_are_ignored(self):
        self.assertIsNone(detect_language("```\nx = 1\n```"))


class TestAutoTarget(unittest.TestCase):

    def test_pair_resolves_in_both_directions(self):
        self.assertEqual(resolve_auto_target("Tôi muốn đi ăn", "vi", "en", "en"), "en")
        self.assertEqual(resolve_auto_target("I want to eat", "vi", "en", "en"), "vi")

    def test_third_language_goes_to_the_primary(self):
        self.assertEqual(resolve_auto_target("こんにちは", "vi", "en", "en"), "vi")

    def test_unrecognisable_text_uses_the_fallback(self):
        self.assertEqual(resolve_auto_target("12345", "vi", "en", "ja"), "ja")

    def test_region_variants_match_their_base_language(self):
        """zh-CN text with a zh-TW pair member must still resolve."""
        self.assertEqual(resolve_auto_target("我正在学习", "zh-TW", "en", "en"), "en")

    def test_pair_other_than_vietnamese_english(self):
        self.assertEqual(resolve_auto_target("こんにちは", "ja", "en", "en"), "en")
        self.assertEqual(resolve_auto_target("Hello there", "ja", "en", "en"), "ja")


if __name__ == "__main__":
    unittest.main()
