"""Protects terms that must survive translation unchanged.

Brand names, product names, handles and internal jargon otherwise come back
rendered differently on every run — the same term translated three ways across
three messages.

The mechanism is placeholder substitution rather than a prompt instruction:
each protected term is swapped for a sentinel before the text leaves, and the
sentinel is swapped back afterwards. A prompt instruction would only work on
the AI providers, and Google Translate is the default here.

Sentinels use mathematical white square brackets (U+27E6/U+27E7). They carry no
linguistic meaning, so translation engines pass them through, and they are rare
enough in real text that a collision is not a practical concern.
"""

import re
from typing import Dict, List, Tuple, Any, Optional

from utils.logger import get_logger

logger = get_logger()

SENTINEL_OPEN = "⟦"   # ⟦
SENTINEL_CLOSE = "⟧"  # ⟧

# Tolerates whitespace a translator may introduce inside the sentinel
_SENTINEL_RE = re.compile(
    re.escape(SENTINEL_OPEN) + r"\s*(\d+)\s*" + re.escape(SENTINEL_CLOSE)
)

# Scripts without spaces between words cannot use word boundaries
_WORD_BOUNDARY_SAFE = re.compile(r"^[\w\s\-'.&+]+$", re.UNICODE)


class GlossaryEntry:
    """One protected term and how it should come out the other side."""

    __slots__ = ("term", "replacement", "match_case")

    def __init__(self, term: str, replacement: str = "", match_case: bool = False):
        self.term = term
        # An empty replacement means "leave the term exactly as written"
        self.replacement = replacement or term
        self.match_case = match_case


def build_entries(raw_entries: List[Dict[str, Any]]) -> List[GlossaryEntry]:
    """Turns stored glossary rows into usable entries, longest term first.

    Longest-first matters: without it, a glossary holding both "Claude" and
    "Claude Code" would match the shorter term inside the longer one and leave
    a dangling "Code" behind.
    """
    entries = []
    for row in raw_entries or []:
        if not row.get("enabled", True):
            continue
        term = (row.get("term") or "").strip()
        if not term:
            continue
        entries.append(GlossaryEntry(
            term=term,
            replacement=(row.get("replacement") or "").strip(),
            match_case=bool(row.get("match_case", False)),
        ))

    entries.sort(key=lambda e: len(e.term), reverse=True)
    return entries


def protect(text: str, entries: List[GlossaryEntry]) -> Tuple[str, Dict[int, str]]:
    """Replaces every glossary term with a sentinel.

    Returns the masked text and the mapping needed to restore it.
    """
    if not text or not entries:
        return text, {}

    restorations: Dict[int, str] = {}
    masked = text
    next_index = 0

    for entry in entries:
        pattern = _compile_term(entry)
        if pattern is None:
            continue

        # Each distinct occurrence gets its own slot so casing is preserved
        def substitute(match: re.Match) -> str:
            nonlocal next_index
            index = next_index
            next_index += 1
            restorations[index] = _resolve_replacement(entry, match.group(0))
            return f"{SENTINEL_OPEN}{index}{SENTINEL_CLOSE}"

        masked = pattern.sub(substitute, masked)

    if restorations:
        logger.debug("Glossary protected %d occurrence(s)", len(restorations))

    return masked, restorations


def restore(text: str, restorations: Dict[int, str]) -> str:
    """Puts the protected terms back where the sentinels are."""
    if not text or not restorations:
        return text

    unseen = set(restorations)

    def substitute(match: re.Match) -> str:
        index = int(match.group(1))
        unseen.discard(index)
        # A sentinel the glossary does not know about is dropped rather than shown
        return restorations.get(index, "")

    result = _SENTINEL_RE.sub(substitute, text)

    if unseen:
        # The engine swallowed a sentinel; the term is simply absent rather than
        # corrupted, which is the least damaging outcome available here.
        logger.warning(
            "Glossary sentinels lost in translation: %s",
            ", ".join(restorations[i] for i in sorted(unseen))
        )

    return result


def _compile_term(entry: GlossaryEntry) -> Optional[re.Pattern]:
    """Builds the match pattern for one term."""
    flags = 0 if entry.match_case else re.IGNORECASE

    escaped = re.escape(entry.term)
    if _WORD_BOUNDARY_SAFE.match(entry.term):
        # Word boundaries stop "AI" matching inside "said"
        pattern = r"(?<!\w)" + escaped + r"(?!\w)"
    else:
        pattern = escaped

    try:
        return re.compile(pattern, flags)
    except re.error as e:
        logger.warning("Could not compile glossary term %r: %s", entry.term, e)
        return None


def _resolve_replacement(entry: GlossaryEntry, matched_text: str) -> str:
    """Chooses what the sentinel becomes.

    A term with no explicit replacement keeps the casing the user typed, so
    "iphone" at the start of a sentence is not forced to "iPhone".
    """
    if entry.replacement != entry.term:
        return entry.replacement
    return matched_text
