"""Unit tests for glossary term protection."""

import unittest
from core.glossary import build_entries, protect, restore, SENTINEL_OPEN, SENTINEL_CLOSE


def _entries(*rows):
    return build_entries(list(rows))


class TestGlossary(unittest.TestCase):

    def test_term_survives_a_round_trip(self):
        entries = _entries({"term": "Zalo"})
        masked, restorations = protect("Gui qua Zalo nhe", entries)
        self.assertNotIn("Zalo", masked)
        self.assertEqual(restore(masked, restorations), "Gui qua Zalo nhe")

    def test_replacement_forces_a_chosen_rendering(self):
        entries = _entries({"term": "deadline", "replacement": "hạn chót"})
        masked, restorations = protect("Truoc deadline nhe", entries)
        self.assertEqual(restore(masked, restorations), "Truoc hạn chót nhe")

    def test_longer_terms_win_over_shorter_ones(self):
        """Without longest-first ordering, 'Claude' would eat 'Claude Code'."""
        entries = _entries({"term": "Claude"}, {"term": "Claude Code"})
        masked, restorations = protect("I use Claude Code daily", entries)
        self.assertEqual(restore(masked, restorations), "I use Claude Code daily")
        self.assertEqual(len(restorations), 1)

    def test_word_boundaries_prevent_matches_inside_words(self):
        entries = _entries({"term": "AI"})
        masked, restorations = protect("He said it plainly", entries)
        self.assertEqual(masked, "He said it plainly")
        self.assertEqual(restorations, {})

    def test_case_insensitive_by_default_and_keeps_the_original_casing(self):
        entries = _entries({"term": "iPhone"})
        masked, restorations = protect("my iphone and my IPHONE", entries)
        self.assertEqual(restore(masked, restorations), "my iphone and my IPHONE")

    def test_match_case_restricts_to_exact_casing(self):
        entries = _entries({"term": "IT", "match_case": True})
        masked, restorations = protect("The IT team and it works", entries)
        self.assertEqual(len(restorations), 1)
        self.assertEqual(restore(masked, restorations), "The IT team and it works")

    def test_disabled_rows_are_skipped(self):
        entries = _entries({"term": "Zalo", "enabled": False})
        self.assertEqual(entries, [])
        masked, restorations = protect("Gui qua Zalo", entries)
        self.assertEqual(restorations, {})

    def test_sentinels_survive_surrounding_whitespace_changes(self):
        """Engines sometimes pad the sentinel; restoration must still match."""
        entries = _entries({"term": "Zalo"})
        masked, restorations = protect("Qua Zalo", entries)
        mangled = masked.replace(
            f"{SENTINEL_OPEN}0{SENTINEL_CLOSE}",
            f"{SENTINEL_OPEN} 0 {SENTINEL_CLOSE}"
        )
        self.assertEqual(restore(mangled, restorations), "Qua Zalo")

    def test_a_lost_sentinel_does_not_leave_debris(self):
        entries = _entries({"term": "Zalo"})
        masked, restorations = protect("Qua Zalo", entries)
        lost = masked.replace(f"{SENTINEL_OPEN}0{SENTINEL_CLOSE}", "")
        self.assertNotIn(SENTINEL_OPEN, restore(lost, restorations))

    def test_multiple_occurrences_each_get_a_slot(self):
        entries = _entries({"term": "Zalo"})
        masked, restorations = protect("Zalo va Zalo va Zalo", entries)
        self.assertEqual(len(restorations), 3)
        self.assertEqual(restore(masked, restorations), "Zalo va Zalo va Zalo")

    def test_empty_inputs_are_handled(self):
        self.assertEqual(protect("", _entries({"term": "Zalo"})), ("", {}))
        self.assertEqual(protect("text", []), ("text", {}))
        self.assertEqual(restore("text", {}), "text")

    def test_regex_metacharacters_in_a_term_are_literal(self):
        entries = _entries({"term": "C++"})
        masked, restorations = protect("I write C++ code", entries)
        self.assertEqual(restore(masked, restorations), "I write C++ code")

    def test_blank_terms_are_dropped(self):
        self.assertEqual(build_entries([{"term": "   "}, {"term": ""}]), [])


if __name__ == "__main__":
    unittest.main()
