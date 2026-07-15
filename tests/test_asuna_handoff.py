"""Tests for the bounded Asuna/Perplexity handoff builder.

Asserts the bundle is single-shot, pointer-only, and carries no network/broadcast
posture -- the safe form of "loop this in from Cursor".
"""

import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "eden"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asuna_handoff as h


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.bundle = h.build_handoff(date(2026, 7, 15))

    def test_bounded_single_shot_no_broadcast(self):
        self.assertEqual(self.bundle["bounded"], "single_bundle_no_loop")
        self.assertEqual(self.bundle["webSearch"], "disabled")
        self.assertEqual(self.bundle["broadcast"], "none")
        self.assertEqual(self.bundle["externalWrites"], "none")

    def test_targets_are_pointer_only(self):
        targets = self.bundle["handoffTargets"]
        self.assertEqual(targets["asunaUnifiedChat"]["policy"], "manual_attach_no_auto_post")
        self.assertEqual(targets["perplexityReview"]["policy"], "pointer_only_no_scrape")
        self.assertEqual(
            targets["phantomDocs"]["policy"], "read_only_docs_no_wallet_action_here"
        )

    def test_embeds_validated_manifest_and_codex(self):
        self.assertEqual(self.bundle["unificationManifest"]["policy"], "no_scrape_pointer_only")
        self.assertEqual(self.bundle["appIndexCodex"]["ledgerSize"], 42)

    def test_today_reading_present(self):
        self.assertIn("micro", self.bundle["todayReading"])
        self.assertIn("macro", self.bundle["todayReading"])

    def test_no_network_imports(self):
        with open(h.__file__, encoding="utf-8") as fh:
            src = fh.read()
        for banned in ("import socket", "import urllib", "import requests", "http.client"):
            self.assertNotIn(banned, src)


if __name__ == "__main__":
    unittest.main()
