"""Script-based language detection.

Deliberately heuristic rather than statistical. The only question this module
has to answer is "which side of the user's language pair is this?", and it has
to answer during a hotkey press, so a script-range check beats loading a model.

Vietnamese is the case that matters most here and is also the easiest to be
sure about: its diacritic set is unique among Latin-script languages, so a
single accented character is decisive.
"""

import re
import unicodedata
from typing import Dict, Optional, Tuple

# Characters that appear in Vietnamese and in no other Latin-script language.
# Horn (ơ ư) and the combination of tone marks with â/ê/ô are the giveaways.
VIETNAMESE_CHARS = set(
    "ăâđêôơưĂÂĐÊÔƠƯ"
    "áàảãạắằẳẵặấầẩẫậÁÀẢÃẠẮẰẲẴẶẤẦẨẪẬ"
    "éèẻẽẹếềểễệÉÈẺẼẸẾỀỂỄỆ"
    "íìỉĩịÍÌỈĨỊ"
    "óòỏõọốồổỗộớờởỡợÓÒỎÕỌỐỒỔỖỘỚỜỞỠỢ"
    "úùủũụứừửữựÚÙỦŨỤỨỪỬỮỰ"
    "ýỳỷỹỵÝỲỶỸỴ"
)

# Unicode ranges that identify a script outright
SCRIPT_RANGES: Tuple[Tuple[int, int, str], ...] = (
    (0x3040, 0x309F, "ja"),      # Hiragana
    (0x30A0, 0x30FF, "ja"),      # Katakana
    (0xAC00, 0xD7AF, "ko"),      # Hangul syllables
    (0x1100, 0x11FF, "ko"),      # Hangul jamo
    (0x4E00, 0x9FFF, "zh-CN"),   # CJK unified ideographs
    (0x3400, 0x4DBF, "zh-CN"),   # CJK extension A
    (0x0E00, 0x0E7F, "th"),      # Thai
    (0x0E80, 0x0EFF, "lo"),      # Lao
    (0x1780, 0x17FF, "km"),      # Khmer
    (0x0400, 0x04FF, "ru"),      # Cyrillic
    (0x0590, 0x05FF, "he"),      # Hebrew
    (0x0600, 0x06FF, "ar"),      # Arabic
    (0x0900, 0x097F, "hi"),      # Devanagari
    (0x0980, 0x09FF, "bn"),      # Bengali
    (0x0A80, 0x0AFF, "gu"),      # Gujarati
    (0x0B80, 0x0BFF, "ta"),      # Tamil
    (0x0C00, 0x0C7F, "te"),      # Telugu
    (0x0C80, 0x0CFF, "kn"),      # Kannada
    (0x0D00, 0x0D7F, "ml"),      # Malayalam
    (0x0D80, 0x0DFF, "si"),      # Sinhala
    (0x1000, 0x109F, "my"),      # Burmese
    (0x0370, 0x03FF, "el"),      # Greek
)

# Text is stripped of these before counting, so a URL or a code identifier does
# not drag the verdict toward whatever script its punctuation resembles.
_NOISE = re.compile(
    r"https?://\S+"          # URLs
    r"|www\.\S+"
    r"|\S+@\S+\.\S+"         # email addresses
    r"|`[^`]*`"              # inline code
    r"|```[\s\S]*?```"       # fenced code
    r"|[@#]\w+"              # mentions and hashtags
    r"|:\w+:"                # emoji shortcodes
)


def _strip_noise(text: str) -> str:
    """Removes spans that carry no language signal."""
    return _NOISE.sub(" ", text)


def detect_language(text: str) -> Optional[str]:
    """Returns a best-guess language code, or None when the text says nothing.

    "Nothing" covers pure punctuation, digits, emoji, and text so short that a
    guess would be worse than deferring to the configured source language.
    """
    if not text:
        return None

    cleaned = _strip_noise(text)

    # Vietnamese first: one unambiguous character settles it
    if any(ch in VIETNAMESE_CHARS for ch in cleaned):
        return "vi"

    script_hits: Dict[str, int] = {}
    latin_letters = 0

    for ch in cleaned:
        if not ch.isalpha():
            continue

        code_point = ord(ch)
        matched = False
        for start, end, lang in SCRIPT_RANGES:
            if start <= code_point <= end:
                script_hits[lang] = script_hits.get(lang, 0) + 1
                matched = True
                break

        if not matched and code_point < 0x0250:
            latin_letters += 1

    if script_hits:
        # Japanese text mixes kana with kanji; any kana means Japanese, not Chinese
        if script_hits.get("ja"):
            return "ja"
        return max(script_hits.items(), key=lambda kv: kv[1])[0]

    if latin_letters >= 2:
        # Latin script with no Vietnamese diacritics. Treating this as English
        # is right for the pair this tool serves, and the provider's own
        # detection corrects it when it is not.
        return "en"

    return None


def is_vietnamese(text: str) -> bool:
    """True when the text carries Vietnamese diacritics."""
    return bool(text) and any(ch in VIETNAMESE_CHARS for ch in _strip_noise(text))


def resolve_auto_target(
    text: str,
    primary: str,
    secondary: str,
    fallback: str
) -> str:
    """Picks the target language for a two-way pair.

    Text detected as `primary` goes to `secondary` and anything else goes to
    `primary`, which is what makes one hotkey translate in both directions.
    `fallback` is returned when the text gives no usable signal.
    """
    detected = detect_language(text)
    if detected is None:
        return fallback

    if _same_language(detected, primary):
        return secondary
    if _same_language(detected, secondary):
        return primary

    # A third language: send it to the primary, which is the user's own
    return primary


def _same_language(a: str, b: str) -> bool:
    """Compares codes ignoring region (zh-CN and zh-TW both match zh)."""
    return a.split("-")[0].lower() == b.split("-")[0].lower()
