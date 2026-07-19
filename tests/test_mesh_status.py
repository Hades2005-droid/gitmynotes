"""Tests for the offline Grok/xAI mesh readiness cue.

Asserts: offline (no network imports), env var NAMES only (secret VALUES never
leak into output), metadata-only pointer reads that degrade gracefully when
absent, and the documented schema/role/policy.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "eden"))

import mesh_status as m


class ShapeTests(unittest.TestCase):
    def setUp(self):
        self.status = m.mesh_status()

    def test_schema_role_policy(self):
        self.assertEqual(self.status["schema"], "wha_spell_simulator.mesh_status.v1")
        self.assertEqual(self.status["role"], "opt_in_playtest_cue")
        self.assertTrue(self.status["offline"])
        self.assertEqual(self.status["secretsPolicy"], "env_names_only_never_values")

    def test_runtime_surface_pointers_are_loopback(self):
        rs = self.status["runtimeSurfacePointers"]
        self.assertIn("127.0.0.1:5619", rs["fable5_game"])
        self.assertIn("127.0.0.1:8188", rs["comfyui"])

    def test_grok_cli_shape(self):
        grok = self.status["grokCli"]
        self.assertIn("present", grok)
        self.assertIsInstance(grok["present"], bool)

    def test_json_serializable(self):
        json.dumps(self.status)


class SecretsPolicyTests(unittest.TestCase):
    def test_env_names_only_boolean(self):
        xai = m.xai_env_ready()
        self.assertEqual(xai["env_names"], ["XAI_API_KEY"])
        for v in xai["by_name"].values():
            self.assertIsInstance(v, bool)

    def test_secret_value_never_leaks(self):
        secret = "sk-DO-NOT-LEAK-abc123"
        old = os.environ.get("XAI_API_KEY")
        os.environ["XAI_API_KEY"] = secret
        try:
            dumped = json.dumps(m.mesh_status())
            self.assertNotIn(secret, dumped)
            # name is reported present (True), value is not
            self.assertTrue(json.loads(dumped)["xaiEnv"]["by_name"]["XAI_API_KEY"])
        finally:
            if old is None:
                os.environ.pop("XAI_API_KEY", None)
            else:
                os.environ["XAI_API_KEY"] = old


class PointerReadTests(unittest.TestCase):
    def test_absent_pointer_is_ok_false(self):
        res = m.jing_power_pointer(Path("/no/such/file.json"))
        self.assertFalse(res["ok"])
        self.assertIn("pointer", res)

    def test_metadata_only_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "jing.json"
            p.write_text(json.dumps({
                "jing_power": 42, "sampled_at": "2026-07-15", "secret": "should-not-be-selected"
            }))
            res = m.jing_power_pointer(p)
            self.assertTrue(res["ok"])
            self.assertEqual(res["jing_power"], 42)
            # only whitelisted fields are surfaced
            self.assertNotIn("secret", res)

    def test_asuna_pointer_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "asuna.json"
            p.write_text(json.dumps({"schema": "x", "generated_at": "t", "phase": "0"}))
            res = m.asuna_point0_pointer(p)
            self.assertTrue(res["ok"])
            self.assertEqual(res["phase"], "0")


class OfflineTests(unittest.TestCase):
    def test_no_network_imports(self):
        with open(m.__file__, encoding="utf-8") as fh:
            src = fh.read()
        for banned in ("import socket", "import urllib", "import requests", "http.client"):
            self.assertNotIn(banned, src)


if __name__ == "__main__":
    unittest.main()
