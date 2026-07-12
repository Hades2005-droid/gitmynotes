#!/usr/bin/env python
"""Unit tests for the local-only persona/provenance pointer contract.

Zero network calls -- the module under test has no network code. These tests
assert: discovered persona IDs are preserved; Minnie/Sarah/Sophie exist as bare
identifiers with no biographies; the deterministic telemetry classifier; opaque
read-only social pointers; 9-point schema pointer metadata; and the pointer-only
controls (no_scrape_pointer_only + manifest_only).
"""

import json
import os
import tempfile
import unittest

import persona_provenance as pp


class ManifestShapeTests(unittest.TestCase):
    def setUp(self):
        self.manifest = pp.build_persona_manifest()
        self.by_id = {p["id"]: p for p in self.manifest.to_dict()["personas"]}

    def test_build_is_pure_and_repeatable(self):
        self.assertEqual(pp.build_persona_manifest().to_dict(), self.manifest.to_dict())

    def test_preserves_all_discovered_persona_ids(self):
        for pid in pp.DISCOVERED_PERSONA_IDS:
            self.assertIn(pid, self.by_id)

    def test_explicit_ids_present(self):
        for pid in ("minnie", "sarah", "sophie"):
            self.assertIn(pid, self.by_id)

    def test_explicit_ids_have_no_invented_biography(self):
        # Bare identifiers: no sources, no canon, no schema binding, no socials.
        for pid in ("minnie", "sarah", "sophie"):
            p = self.by_id[pid]
            self.assertEqual(p["sources"], [])
            self.assertIsNone(p["canon"])
            self.assertEqual(p["ninePointSchema"], [])
            self.assertEqual(p["socialPointers"], [])

    def test_all_personas_symbolic_only(self):
        for p in self.by_id.values():
            self.assertTrue(p["symbolicOnly"])

    def test_json_round_trips(self):
        payload = self.manifest.to_json()
        self.assertEqual(json.loads(payload), self.manifest.to_dict())
        self.assertEqual(payload, self.manifest.to_json())

    def test_telemetry_classes_listed(self):
        self.assertEqual(
            self.manifest.to_dict()["telemetryClasses"],
            ["primordial", "canonical", "corroborated", "provisional", "quarantine"],
        )


class NinePointSchemaTests(unittest.TestCase):
    def setUp(self):
        self.manifest = pp.build_persona_manifest()

    def test_schema_pointer_has_nine_points(self):
        schema = self.manifest.to_dict()["ninePointSchemaPointer"]
        self.assertEqual(schema["doc"], "docs/9-points-angela-framework.md")
        self.assertEqual([pt["point"] for pt in schema["points"]], list(range(1, 10)))
        for pt in schema["points"]:
            self.assertTrue(pt["symbolicOnly"])

    def test_named_points_come_from_doc(self):
        schema = {pt["point"]: pt["name"] for pt in self.manifest.to_dict()["ninePointSchemaPointer"]["points"]}
        self.assertEqual(schema[9], "9-Point Orchestrator")
        self.assertEqual(schema[4], "Sovereign")

    def test_persona_schema_binding_is_symbolic(self):
        by_id = {p["id"]: p for p in self.manifest.to_dict()["personas"]}
        angela = by_id["angela"]["ninePointSchema"]
        self.assertEqual(angela[0]["point"], 9)
        self.assertTrue(angela[0]["symbolicOnly"])


class ClassifyTests(unittest.TestCase):
    def test_expected_seed_classifications(self):
        by_id = {p.id: p for p in pp.build_persona_manifest().personas}
        self.assertEqual(pp.classify(by_id["angela"]), "primordial")
        self.assertEqual(pp.classify(by_id["fred"]), "corroborated")
        self.assertEqual(pp.classify(by_id["asuna"]), "canonical")
        self.assertEqual(pp.classify(by_id["echo-girl"]), "provisional")
        self.assertEqual(pp.classify(by_id["minnie"]), "provisional")

    def test_flagged_is_quarantined(self):
        p = pp.Persona(id="x", name="X", flagged=True, sources=("a", "b"), canon="c", primordial=True)
        self.assertEqual(pp.classify(p), "quarantine")

    def test_social_pointer_without_source_is_quarantined(self):
        p = pp.Persona(id="x", name="X", social_pointers=(pp.SocialPointer("x", "https://x.com/opaque"),))
        self.assertEqual(pp.classify(p), "quarantine")

    def test_social_pointer_with_source_is_not_quarantined(self):
        p = pp.Persona(
            id="x", name="X",
            sources=("docs/a.md",),
            social_pointers=(pp.SocialPointer("instagram", "https://instagram.com/opaque"),),
        )
        self.assertEqual(pp.classify(p), "provisional")

    def test_two_sources_is_corroborated(self):
        p = pp.Persona(id="x", name="X", sources=("a.md", "b.md"))
        self.assertEqual(pp.classify(p), "corroborated")

    def test_classification_is_deterministic(self):
        p = pp.Persona(id="x", name="X", sources=("a.md",))
        self.assertEqual(pp.classify(p), pp.classify(p))


class SocialPointerTests(unittest.TestCase):
    def test_social_pointer_is_opaque_read_only(self):
        d = pp.SocialPointer("x", "https://x.com/some-handle").to_dict()
        self.assertEqual(d["actionTaken"], "none")
        self.assertFalse(d["scraped"])
        self.assertFalse(d["fetched"])
        self.assertFalse(d["write"])

    def test_validation_rejects_unknown_platform(self):
        import dataclasses

        m = pp.build_persona_manifest()
        bad = pp.Persona(id="z", name="Z", sources=("a.md",), social_pointers=(pp.SocialPointer("facebook", "u"),))
        broken = dataclasses.replace(m, personas=m.personas + (bad,))
        with self.assertRaises(pp.PersonaPolicyError):
            pp.validate_persona_manifest(broken)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.manifest = pp.build_persona_manifest()

    def test_default_manifest_validates(self):
        pp.validate_persona_manifest(self.manifest)

    def test_controls_are_pointer_only(self):
        c = self.manifest.to_dict()["controls"]
        self.assertEqual(c["policy"], "no_scrape_pointer_only")
        self.assertEqual(c["mode"], "manifest_only")
        self.assertEqual(c["externalRequests"], 0)
        for k in ("scraped", "fetched", "externalWrites", "credentialsUsed", "trainingAllowed"):
            self.assertFalse(c[k], k)

    def test_scraped_flag_rejected(self):
        import dataclasses

        with self.assertRaises(pp.PersonaPolicyError):
            pp.validate_persona_manifest(dataclasses.replace(self.manifest, scraped=True))

    def test_external_writes_rejected(self):
        import dataclasses

        with self.assertRaises(pp.PersonaPolicyError):
            pp.validate_persona_manifest(dataclasses.replace(self.manifest, external_writes=True))

    def test_credentials_used_rejected(self):
        import dataclasses

        with self.assertRaises(pp.PersonaPolicyError):
            pp.validate_persona_manifest(dataclasses.replace(self.manifest, credentials_used=True))

    def test_dropping_discovered_id_rejected(self):
        import dataclasses

        trimmed = tuple(p for p in self.manifest.personas if p.id != "asuna")
        with self.assertRaises(pp.PersonaPolicyError):
            pp.validate_persona_manifest(dataclasses.replace(self.manifest, personas=trimmed))

    def test_dropping_explicit_id_rejected(self):
        import dataclasses

        trimmed = tuple(p for p in self.manifest.personas if p.id != "minnie")
        with self.assertRaises(pp.PersonaPolicyError):
            pp.validate_persona_manifest(dataclasses.replace(self.manifest, personas=trimmed))

    def test_non_symbolic_persona_rejected(self):
        import dataclasses

        real = pp.Persona(id="real", name="Real", symbolic_only=False, sources=("a.md",))
        with self.assertRaises(pp.PersonaPolicyError):
            pp.validate_persona_manifest(dataclasses.replace(self.manifest, personas=self.manifest.personas + (real,)))

    def test_out_of_range_schema_point_rejected(self):
        import dataclasses

        bad = pp.Persona(id="oob", name="Oob", sources=("a.md",), schema_points=(12,))
        with self.assertRaises(pp.PersonaPolicyError):
            pp.validate_persona_manifest(dataclasses.replace(self.manifest, personas=self.manifest.personas + (bad,)))

    def test_duplicate_ids_rejected(self):
        import dataclasses

        dup = pp.Persona(id="minnie", name="Minnie2")
        with self.assertRaises(pp.PersonaPolicyError):
            pp.validate_persona_manifest(dataclasses.replace(self.manifest, personas=self.manifest.personas + (dup,)))


class CliTests(unittest.TestCase):
    def test_validate_flag_returns_zero(self):
        self.assertEqual(pp.main(["--validate"]), 0)

    def test_writes_manifest_to_local_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "persona.json")
            self.assertEqual(pp.main(["--out", path]), 0)
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertEqual(data["controls"]["policy"], "no_scrape_pointer_only")


class NoNetworkTests(unittest.TestCase):
    def test_module_imports_no_network_libraries(self):
        with open(pp.__file__, encoding="utf-8") as fh:
            src = fh.read()
        for banned in ("import socket", "import urllib", "import requests", "import http.client"):
            self.assertNotIn(banned, src, f"unexpected network import: {banned}")


if __name__ == "__main__":
    unittest.main()
