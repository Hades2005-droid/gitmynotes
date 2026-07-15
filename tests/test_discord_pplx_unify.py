"""Tests for the Discord x Perplexity unify pointer catalog.

Asserts it is pointer-only: no API calls, no tokens, no broadcast, webhook stays
ARMED_AWAITING_TOKEN, social SDK deferred, and no network imports.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "eden"))

import discord_pplx_unify as d


class UnifyShapeTests(unittest.TestCase):
    def setUp(self):
        self.unify = d.build_unify()

    def test_pointer_only_flags(self):
        self.assertEqual(self.unify["externalRequests"], 0)
        self.assertFalse(self.unify["broadcast"])
        self.assertFalse(self.unify["tokensRequired"])
        self.assertEqual(self.unify["webhookMode"], "ARMED_AWAITING_TOKEN")

    def test_central_task_is_pointer(self):
        self.assertEqual(
            self.unify["perplexityCentralTaskId"], "2366bfee-b78c-4ddc-9f86-304c30c67c4d"
        )
        self.assertEqual(self.unify["discordDocsIndex"], "https://docs.discord.com/llms.txt")

    def test_all_five_lanes_present(self):
        lanes = {l["lane"] for l in self.unify["lanes"]}
        self.assertEqual(
            lanes,
            {"webhooks", "bots_apps", "activities_party", "social_layer", "policy_safety"},
        )

    def test_markdown_handoff_renders(self):
        md = d.render_markdown(self.unify)
        self.assertIn("Discord Developer Platform x Perplexity unify", md)
        self.assertIn("DISCORD_PPLX_UNIFY.md", md)


class UnifyValidationTests(unittest.TestCase):
    def test_default_validates(self):
        d.validate_unify()

    def test_live_webhook_rejected(self):
        bad = d.build_unify()
        bad["webhookMode"] = "LIVE"
        with self.assertRaises(d.DiscordUnifyError):
            d.validate_unify(bad)

    def test_broadcast_rejected(self):
        bad = d.build_unify()
        bad["broadcast"] = True
        with self.assertRaises(d.DiscordUnifyError):
            d.validate_unify(bad)

    def test_external_requests_rejected(self):
        bad = d.build_unify()
        bad["externalRequests"] = 1
        with self.assertRaises(d.DiscordUnifyError):
            d.validate_unify(bad)

    def test_social_layer_must_stay_deferred(self):
        bad = d.build_unify()
        for lane in bad["lanes"]:
            if lane["lane"] == "social_layer":
                lane["phase"] = "live"
        with self.assertRaises(d.DiscordUnifyError):
            d.validate_unify(bad)

    def test_no_network_imports(self):
        with open(d.__file__, encoding="utf-8") as fh:
            src = fh.read()
        for banned in ("import socket", "import urllib", "import requests", "http.client"):
            self.assertNotIn(banned, src)


if __name__ == "__main__":
    unittest.main()
