"""Text processing, sanitization, and preservation utilities.

Handles whitespace preservation, code detection, markdown validation,
and ensures translation outputs maintain original formatting.
"""

import re
from typing import Tuple, Dict, Any


class TextProcessor:
    """Utilities for processing text before and after translation."""

    @staticmethod
    def extract_spacing(text: str) -> Tuple[str, str, str]:
        """Extracts leading whitespace, inner trimmed content, and trailing whitespace.

        Ensures that in-place text replacement preserves indentation and newlines.
        """
        if not text:
            return "", "", ""

        # Leading whitespace
        leading_match = re.match(r"^(\s*)", text)
        leading = leading_match.group(1) if leading_match else ""

        # Trailing whitespace
        trailing_match = re.search(r"(\s*)$", text)
        trailing = trailing_match.group(1) if trailing_match else ""

        # Body
        body = text[len(leading):len(text) - len(trailing) if trailing else len(text)]
        return leading, body, trailing

    @staticmethod
    def apply_spacing(translated_body: str, leading: str, trailing: str) -> str:
        """Reapplies original leading and trailing whitespace to translated text."""
        return f"{leading}{translated_body}{trailing}"

    @staticmethod
    def is_likely_code(text: str) -> bool:
        """Checks if text contains source code blocks or programming syntax."""
        code_patterns = [
            r"```[\w]*\n[\s\S]*?```",             # Markdown code fences
            r"(?:def|class|function|import|export|const|let|var|public|private)\s+[\w]+",
            r"(?:if|for|while)\s*\([^)]*\)\s*\{",  # C/JS style control flow
            r"SELECT\s+[\s\S]+\s+FROM\s+",         # SQL
            r"<[a-zA-Z][^>]*>[\s\S]*?</[a-zA-Z]>", # HTML/XML tags
        ]
        return any(re.search(p, text) for p in code_patterns)

    @staticmethod
    def clean_output(original: str, translated: str) -> str:
        """Cleans up translated text, removing spurious outer quotes or fences."""
        if not translated:
            return ""

        res = translated.strip()

        # If original was not quoted, but AI wrapped in quotes, strip them
        if not (original.startswith('"') and original.endswith('"')) and not (original.startswith("'") and original.endswith("'")):
            if (res.startswith('"') and res.endswith('"')) or (res.startswith("'") and res.endswith("'")):
                res = res[1:-1].strip()

        # If original did not start with code fences, remove accidental wrapper
        if not original.startswith("```") and res.startswith("```") and res.endswith("```"):
            lines = res.splitlines()
            if len(lines) >= 2:
                res = "\n".join(lines[1:-1]).strip()

        return res
