"""Tests for the APP INDEX Spacetime Ledger game mechanic.

Pure/local: no network, no advice. Asserts the deterministic reduction, full
1-42 coverage, master-number preservation, artifact quarantine, and the hard
safety exclusions (no medical advice, no real-person profiling, no minors).
"""

import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "eden"))

import app_index_codex as c


class ReductionTests(unittest.TestCase):
    def test_master_numbers_never_reduce(self):
        for m in (11, 22, 33):
            self.assertEqual(c._reduce(m), m)

    def test_basic_digit_sum(self):
        self.assertEqual(c._reduce(21), 3)
        self.assertEqual(c._reduce(19), 1)   # 1+9=10 -> 1
        self.assertEqual(c._reduce(42), 6)   # 4+2=6

    def test_reduction_stops_at_master_number(self):
        # 39 -> 12 -> ... 12 is not master, reduces to 3
        self.assertEqual(c._reduce(39), 3)


class LedgerCoverageTests(unittest.TestCase):
    def test_covers_1_through_42(self):
        for n in range(1, 43):
            self.assertIn(n, c.LEDGER)

    def test_known_archetypes(self):
        self.assertEqual(c.LEDGER[1][0], "The Magician")
        self.assertEqual(c.LEDGER[22][0], "The Master Builder")
        self.assertEqual(c.LEDGER[42][0], "Sovereign Anchor")


class ReadingTests(unittest.TestCase):
    def test_resolve_is_deterministic(self):
        d = date(2026, 7, 15)
        self.assertEqual(c.resolve_ledger(d), c.resolve_ledger(d))

    def test_micro_and_macro_math(self):
        # 4/26/2026: micro 4+2+6=12, macro +2+0+2+6 = 22 (master)
        res = c.resolve_ledger(date(2026, 4, 26))
        self.assertEqual(res["micro"]["raw"], 12)
        self.assertEqual(res["micro"]["reduced"], 3)
        self.assertEqual(res["macro"]["raw"], 22)
        self.assertEqual(res["macro"]["reduced"], 22)

    def test_time_reading_optional(self):
        res = c.resolve_ledger(date(2026, 7, 15), 21, 8)
        self.assertIn("time", res)
        self.assertEqual(res["time"]["raw"], 2 + 1 + 0 + 8)

    def test_bad_hour_rejected(self):
        with self.assertRaises(c.CodexError):
            c.resolve_ledger(date(2026, 7, 15), 24, 0)


class SafetyTests(unittest.TestCase):
    def test_codex_validates(self):
        c.validate_codex()

    def test_no_medical_or_profiling(self):
        exc = c.build_codex()["exclusions"]
        self.assertFalse(exc["medicalAdvice"])
        self.assertFalse(exc["realPersonProfiling"])
        self.assertTrue(exc["minorsProhibited"])

    def test_taboo_daemon_quarantined(self):
        by_name = {a.name: a.disposition for a in c.SOURCE_ARTIFACTS}
        self.assertEqual(
            by_name["Eden_x_Shadow_Gaden_-_Grok_LOVE_4f1c.pdf"], c.ARTIFACT_QUARANTINE
        )

    def test_all_four_artifacts_recorded(self):
        self.assertEqual(len(c.SOURCE_ARTIFACTS), 4)

    def test_tampering_medical_flag_rejected(self):
        codex = c.build_codex()
        codex["exclusions"]["medicalAdvice"] = True
        with self.assertRaises(c.CodexError):
            c.validate_codex(codex)


if __name__ == "__main__":
    unittest.main()
