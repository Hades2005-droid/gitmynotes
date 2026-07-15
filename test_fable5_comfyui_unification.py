#!/usr/bin/env python
"""Unit tests for the Fable5 + ComfyUI unification pointer surface.

These tests make ZERO network calls -- the module under test has no network
code at all. They assert the pointer-only contract: fixed local endpoints,
recorded task IDs, role compatibility, and every safety invariant
(externalRequests=0, no training, no weight auto-download, media manifest_only
with approval required).
"""

import json
import os
import tempfile
import unittest

import fable5_comfyui_unification as u


class ManifestShapeTests(unittest.TestCase):
    def setUp(self):
        self.manifest = u.build_manifest()

    def test_build_is_pure_and_repeatable(self):
        self.assertEqual(u.build_manifest().to_dict(), self.manifest.to_dict())

    def test_surface_role_and_policy(self):
        self.assertEqual(self.manifest.surface, u.SURFACE_ROLE)
        self.assertEqual(self.manifest.policy, "no_scrape_pointer_only")

    def test_records_canonical_task_ids(self):
        d = self.manifest.to_dict()
        self.assertEqual(
            d["canonicalUnificationTaskId"], "37bce2fb-1ba6-471f-854f-3871d9c19947"
        )
        self.assertEqual(
            d["leadAssistantTaskId"], "2366bfee-b78c-4ddc-9f86-304c30c67c4d"
        )
        self.assertEqual(
            d["secondaryUnificationReviewTaskId"],
            "c6b14a5b-abd7-426c-9992-7095c20b8964",
        )
        self.assertEqual(d["secondaryReview"]["role"], "secondary_unification_review")
        self.assertEqual(d["secondaryReview"]["policy"], "pointer_only_no_scrape")

    def test_content_boundary_rejects_hallucinated_fusion_pipeline(self):
        boundary = self.manifest.to_dict()["contentBoundary"]
        self.assertEqual(
            boundary["domain"], "fictional_adult_18plus_simulation_game"
        )
        self.assertTrue(boundary["fictionalAdultSimOnly"])
        self.assertTrue(boundary["minorsProhibited"])
        self.assertFalse(boundary["realPersonLikenessEngine"])
        self.assertFalse(boundary["adultVideoSiteScrape"])
        self.assertFalse(boundary["recursiveImprovementLoops"])
        self.assertFalse(boundary["externalMediaExecutionHere"])
        self.assertIn("FABLE5_MEMORY_CORRECTION.md", boundary["correctionDoc"])

    def test_preserves_role_compatibility(self):
        roles = self.manifest.to_dict()["compatibleRoles"]
        self.assertIn("unification_target", roles)
        self.assertIn("fable5_comfyui_open_merge_target", roles)

    def test_pointer_only_integrations_present(self):
        by_name = {i["name"]: i for i in self.manifest.to_dict()["integrations"]}
        self.assertEqual(
            by_name["phantom_docs_mcp"]["policy"],
            "read_only_docs_no_wallet_action_here",
        )
        self.assertEqual(
            by_name["asuna_unified_chat"]["policy"], "manual_attach_no_auto_post"
        )

    def test_records_all_three_endpoints_with_ports(self):
        by_name = {e["name"]: e for e in self.manifest.to_dict()["endpoints"]}
        self.assertEqual(by_name["fable5"]["port"], 5619)
        self.assertEqual(by_name["comfyui"]["port"], 8188)
        self.assertEqual(by_name["eden"]["port"], 8791)

    def test_endpoints_are_loopback_only(self):
        for ep in self.manifest.to_dict()["endpoints"]:
            self.assertEqual(ep["host"], "127.0.0.1")
            self.assertTrue(ep["url"].startswith("http://127.0.0.1:"))

    def test_json_is_serializable_and_stable(self):
        payload = self.manifest.to_json()
        # Round-trips and is deterministic (sorted keys).
        self.assertEqual(json.loads(payload), self.manifest.to_dict())
        self.assertEqual(payload, self.manifest.to_json())


class SafetyInvariantTests(unittest.TestCase):
    def setUp(self):
        self.manifest = u.build_manifest()

    def test_default_manifest_validates(self):
        # Should not raise.
        u.validate_manifest(self.manifest)

    def test_top_level_safety_flags(self):
        d = self.manifest.to_dict()
        self.assertEqual(d["externalRequests"], 0)
        self.assertFalse(d["trainingAllowed"])
        self.assertFalse(d["weightAutoDownload"])
        self.assertFalse(d["broadcasting"])
        self.assertFalse(d["externalWrites"])

    def test_media_defaults_are_manifest_only_and_gated(self):
        for perm in self.manifest.to_dict()["mediaPermissions"]:
            self.assertEqual(perm["mode"], "manifest_only")
            self.assertTrue(perm["approveRequired"])
            self.assertEqual(perm["externalRequests"], 0)
            self.assertFalse(perm["trainingAllowed"])
            self.assertFalse(perm["weightAutoDownload"])

    def test_all_media_types_present(self):
        types = {p["mediaType"] for p in self.manifest.to_dict()["mediaPermissions"]}
        self.assertEqual(types, {"image", "video", "audio"})

    def test_external_requests_rejected(self):
        import dataclasses

        bad = dataclasses.replace(self.manifest, external_requests=1)
        with self.assertRaises(u.UnificationPolicyError):
            u.validate_manifest(bad)

    def test_training_allowed_rejected(self):
        import dataclasses

        bad = dataclasses.replace(self.manifest, training_allowed=True)
        with self.assertRaises(u.UnificationPolicyError):
            u.validate_manifest(bad)

    def test_weight_auto_download_rejected(self):
        import dataclasses

        bad = dataclasses.replace(self.manifest, weight_auto_download=True)
        with self.assertRaises(u.UnificationPolicyError):
            u.validate_manifest(bad)

    def test_broadcasting_and_external_writes_rejected(self):
        import dataclasses

        for kwargs in ({"broadcasting": True}, {"external_writes": True}):
            bad = dataclasses.replace(self.manifest, **kwargs)
            with self.assertRaises(u.UnificationPolicyError):
                u.validate_manifest(bad)

    def test_dropping_a_required_role_rejected(self):
        import dataclasses

        bad = dataclasses.replace(self.manifest, compatible_roles=("unification_target",))
        with self.assertRaises(u.UnificationPolicyError):
            u.validate_manifest(bad)

    def test_non_loopback_endpoint_rejected(self):
        import dataclasses

        remote = u.EndpointContract(name="evil", port=5619, role=u.ROLE_UNIFICATION_TARGET, host="10.0.0.1")
        bad = dataclasses.replace(self.manifest, endpoints=(remote,))
        with self.assertRaises(u.UnificationPolicyError):
            u.validate_manifest(bad)

    def test_media_promoted_past_manifest_only_rejected(self):
        import dataclasses

        loose = u.MediaPermission(media_type="image", mode="live")
        bad = dataclasses.replace(self.manifest, media_permissions=(loose,))
        with self.assertRaises(u.UnificationPolicyError):
            u.validate_manifest(bad)

    def test_content_boundary_tamper_rejected(self):
        import dataclasses

        bad_boundary = dict(self.manifest.content_boundary)
        bad_boundary["adultVideoSiteScrape"] = True
        bad = dataclasses.replace(self.manifest, content_boundary=bad_boundary)
        with self.assertRaises(u.UnificationPolicyError):
            u.validate_manifest(bad)

    def test_wrong_secondary_task_id_rejected(self):
        import dataclasses

        bad = dataclasses.replace(
            self.manifest,
            secondary_unification_review_task_id="00000000-0000-0000-0000-000000000000",
        )
        with self.assertRaises(u.UnificationPolicyError):
            u.validate_manifest(bad)

    def test_asuna_auto_post_rejected(self):
        import dataclasses

        loose = dict(u.INTEGRATIONS[1])
        loose["policy"] = "auto_post"
        bad = dataclasses.replace(self.manifest, integrations=(u.INTEGRATIONS[0], loose))
        with self.assertRaises(u.UnificationPolicyError):
            u.validate_manifest(bad)

    def test_phantom_wallet_action_rejected(self):
        import dataclasses

        loose = dict(u.INTEGRATIONS[0])
        loose["policy"] = "wallet_signing_enabled"
        bad = dataclasses.replace(self.manifest, integrations=(loose, u.INTEGRATIONS[1]))
        with self.assertRaises(u.UnificationPolicyError):
            u.validate_manifest(bad)


class MediaRequestGateTests(unittest.TestCase):
    def test_unapproved_request_is_manifest_only(self):
        res = u.resolve_media_request("image")
        self.assertEqual(res["mode"], "manifest_only")
        self.assertFalse(res["approved"])
        self.assertFalse(res["executedHere"])
        self.assertEqual(res["externalRequests"], 0)
        self.assertTrue(res["pointers"])

    def test_approved_request_never_executes_here(self):
        res = u.resolve_media_request("video", approval_token="approved-by-operator")
        self.assertTrue(res["approved"])
        # Even approved, this surface never runs media or opens a socket.
        self.assertFalse(res["executedHere"])
        self.assertEqual(res["externalRequests"], 0)

    def test_unknown_media_type_rejected(self):
        with self.assertRaises(u.UnificationPolicyError):
            u.resolve_media_request("hologram")


class CliTests(unittest.TestCase):
    def test_validate_flag_returns_zero(self):
        self.assertEqual(u.main(["--validate"]), 0)

    def test_writes_manifest_to_local_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "manifest.json")
            rc = u.main(["--out", path])
            self.assertEqual(rc, 0)
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertEqual(data["policy"], "no_scrape_pointer_only")
            self.assertEqual(data["externalRequests"], 0)


class NoNetworkImportTests(unittest.TestCase):
    def test_module_imports_no_network_libraries(self):
        # Pointer-only surface: it must not pull in HTTP/socket stacks.
        import sys

        with open(u.__file__, encoding="utf-8") as fh:
            src = fh.read()
        for banned in ("import socket", "import urllib", "import requests", "import http.client"):
            self.assertNotIn(banned, src, f"unexpected network import: {banned}")
        self.assertNotIn("socket", getattr(sys.modules[u.__name__], "__dict__", {}))


if __name__ == "__main__":
    unittest.main()
