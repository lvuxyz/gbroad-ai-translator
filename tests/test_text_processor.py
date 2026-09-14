"""Unit tests for text processor, spacing preservation, and code detection."""

import unittest
from core.text_processor import TextProcessor


class TestTextProcessor(unittest.TestCase):

    def setUp(self):
        self.processor = TextProcessor()

    def test_extract_and_apply_spacing(self):
        text = "   \nHello World!  \n\n"
        leading, body, trailing = self.processor.extract_spacing(text)
        self.assertEqual(leading, "   \n")
        self.assertEqual(body, "Hello World!")
        self.assertEqual(trailing, "  \n\n")

        reconstructed = self.processor.apply_spacing("Xin chào thế giới!", leading, trailing)
        self.assertEqual(reconstructed, "   \nXin chào thế giới!  \n\n")

    def test_is_likely_code(self):
        code_samples = [
            "def calculate_sum(a, b):\n    return a + b",
            "const user = { name: 'Alice', age: 30 };",
            "```python\nprint('hello')\n```",
            "SELECT * FROM users WHERE active = 1;",
        ]
        for sample in code_samples:
            self.assertTrue(self.processor.is_likely_code(sample), f"Should detect code in: {sample}")

        non_code = "Tôi đang học tiếng Nhật để đi du lịch."
        self.assertFalse(self.processor.is_likely_code(non_code))

    def test_clean_output(self):
        # Spurious outer quotes
        self.assertEqual(self.processor.clean_output("Hello", '"Hello"'), "Hello")
        self.assertEqual(self.processor.clean_output("Hello", "'Hello'"), "Hello")

        # Intentional outer quotes should remain
        self.assertEqual(self.processor.clean_output('"Hello"', '"Xin chào"'), '"Xin chào"')

        # Accidental markdown fences
        accidental_code = "```\nTranslated text\n```"
        self.assertEqual(self.processor.clean_output("Normal text", accidental_code), "Translated text")


if __name__ == "__main__":
    unittest.main()
