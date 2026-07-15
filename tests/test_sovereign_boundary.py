"""Tests for the sovereign boundary truth line (two-door federation policy).

Asserts internal = open_door_default (auto), external = closed_door_default
(per-action confirm, never blanket), external actions default to a contained
dry-run into the Asuna 0-point chamber, and this surface never performs a write.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "eden"))

import sovereign_boundary as b


class ShapeTests(unittest.TestCase):
    def setUp(self):
        self.boundary = b.build_boundary()

    def test_internal_is_open_door_auto(self):
        internal = self.boundary["internal"]
        self.assertTrue(internal["openDoorDefault"])
        self.assertEqual(internal["default"], "auto")
        self.assertIn("read", internal["actions"])
        self.assertIn("catalog_insertion", internal["actions"])

    def test_external_is_closed_door_confirm_no_blanket(self):
        external = self.boundary["external"]
        self.assertTrue(external["closedDoorDefault"])
        self.assertEqual(external["default"], "confirm")
        self.assertFalse(external["blanketGrant"])
        self.assertTrue(external["perActionConfirm"])
        for a in ("grok_send", "qdrant_upsert", "github_push", "atlassian_write", "x_write", "slack_write"):
            self.assertIn(a, external["actions"])

    def test_tensegrity_vector_11(self):
        self.assertEqual(self.boundary["tensegrityVector"], 11)

    def test_chamber_is_wuji_no_default_write(self):
        self.assertEqual(self.boundary["chamber"]["name"], "asuna_0_point_chamber")
        self.assertFalse(self.boundary["chamber"]["externalWriteByDefault"])


class DecisionTests(unittest.TestCase):
    def test_internal_action_auto_allowed(self):
        d = b.decide("read")
        self.assertEqual(d["side"], "internal")
        self.assertTrue(d["allowed"])
        self.assertFalse(d["requiresConfirm"])

    def test_external_action_defaults_to_chamber_dry_run(self):
        d = b.decide("grok_send")
        self.assertEqual(d["side"], "external")
        self.assertFalse(d["allowed"])
        self.assertTrue(d["dryRun"])
        self.assertEqual(d["chamber"], "asuna_0_point_chamber")
        self.assertFalse(d["externalWritePerformed"])

    def test_confirmed_external_still_performs_no_write_here(self):
        d = b.decide("github_push", confirm_token="operator-ok")
        self.assertTrue(d["allowed"])
        self.assertFalse(d["dryRun"])
        self.assertFalse(d["externalWritePerformed"])  # deferred to a runtime, never here

    def test_unknown_action_treated_as_external(self):
        self.assertEqual(b.classify("mystery_action"), "external")
        self.assertFalse(b.decide("mystery_action")["allowed"])


class ValidationTests(unittest.TestCase):
    def test_default_validates(self):
        b.validate_boundary()

    def test_blanket_grant_rejected(self):
        bad = b.build_boundary()
        bad["external"]["blanketGrant"] = True
        with self.assertRaises(b.BoundaryError):
            b.validate_boundary(bad)

    def test_external_open_default_rejected(self):
        bad = b.build_boundary()
        bad["external"]["default"] = "auto"
        bad["external"]["closedDoorDefault"] = False
        with self.assertRaises(b.BoundaryError):
            b.validate_boundary(bad)

    def test_internal_must_stay_open(self):
        bad = b.build_boundary()
        bad["internal"]["openDoorDefault"] = False
        with self.assertRaises(b.BoundaryError):
            b.validate_boundary(bad)

    def test_no_network_imports(self):
        with open(b.__file__, encoding="utf-8") as fh:
            src = fh.read()
        for banned in ("import socket", "import urllib", "import requests", "http.client"):
            self.assertNotIn(banned, src)


if __name__ == "__main__":
    unittest.main()
