#!/usr/bin/env python
"""Unit tests for the optional Asana connector.

By default these tests make ZERO live network calls -- every HTTP interaction
goes through an injected stub transport. A single live smoke test is gated
behind RUN_LIVE_ASANA_TESTS=1 and is skipped otherwise, so `pytest` (or
`python -m unittest`) is always safe to run offline and with no credentials.
"""

import json
import os
import unittest

import asana_connector as ac


class StubTransport:
    """Records requests and replays canned (status, body) responses."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def __call__(self, method, url, headers, body):
        parsed = json.loads(body.decode("utf-8")) if body else None
        self.calls.append(
            {"method": method, "url": url, "headers": headers, "body": parsed}
        )
        status, payload = self._responses.pop(0)
        return status, json.dumps(payload).encode("utf-8")


def make_config(**overrides):
    base = dict(
        access_token="test-token-not-a-secret",
        workspace_id="12345",
        project_gid="99999",
        base_url=ac.DEFAULT_BASE_URL,
        enabled=True,
    )
    base.update(overrides)
    return ac.AsanaConfig(**base)


class ConfigTests(unittest.TestCase):
    def test_from_env_disabled_without_flag(self):
        cfg = ac.AsanaConfig.from_env({ac.ENV_ACCESS_TOKEN: "tok"})
        self.assertFalse(cfg.is_enabled)

    def test_from_env_enabled_requires_token(self):
        cfg = ac.AsanaConfig.from_env({ac.ENV_ENABLED: "1"})
        self.assertFalse(cfg.is_enabled)  # flag set but no token
        cfg2 = ac.AsanaConfig.from_env(
            {ac.ENV_ENABLED: "true", ac.ENV_ACCESS_TOKEN: "tok"}
        )
        self.assertTrue(cfg2.is_enabled)

    def test_is_configured_requires_project(self):
        cfg = ac.AsanaConfig.from_env(
            {ac.ENV_ENABLED: "yes", ac.ENV_ACCESS_TOKEN: "tok"}
        )
        self.assertTrue(cfg.is_enabled)
        self.assertFalse(cfg.is_configured)  # no project gid
        cfg2 = ac.AsanaConfig.from_env(
            {
                ac.ENV_ENABLED: "on",
                ac.ENV_ACCESS_TOKEN: "tok",
                ac.ENV_PROJECT_GID: "42",
            }
        )
        self.assertTrue(cfg2.is_configured)

    def test_describe_redacts_token(self):
        cfg = make_config(access_token="supersecrettoken1234")
        described = cfg.describe()
        self.assertEqual(described["token"], "****1234")
        self.assertNotIn("supersecrettoken", json.dumps(described))

    def test_redact_helper(self):
        self.assertEqual(ac._redact(None), "<unset>")
        self.assertEqual(ac._redact("abcd"), "****")
        self.assertEqual(ac._redact("abcdef"), "****cdef")


class SyncReportTests(unittest.TestCase):
    def test_resonance_clean_success(self):
        r = ac.SyncReport(folder="Notes", success=True, notes_processed=4)
        self.assertEqual(r.sync_resonance(), 100.0)
        self.assertEqual(r.technique_mastery(), "Grandmaster")

    def test_resonance_failure_is_zero(self):
        r = ac.SyncReport(folder="Notes", success=False)
        self.assertEqual(r.sync_resonance(), 0.0)
        self.assertEqual(r.technique_mastery(), "Novice")

    def test_resonance_partial_and_conflicts(self):
        r = ac.SyncReport(
            folder="Notes", success=True, partial=True, conflicts=2, notes_processed=0
        )
        # base 55 - (2*8=16) + 0 = 39 -> Apprentice
        self.assertEqual(r.sync_resonance(), 39.0)
        self.assertEqual(r.technique_mastery(), "Apprentice")

    def test_conflict_penalty_capped(self):
        r = ac.SyncReport(folder="Notes", success=True, conflicts=99)
        # 100 - min(40, 792) + 0 = 60
        self.assertEqual(r.sync_resonance(), 60.0)

    def test_duration_seconds(self):
        r = ac.SyncReport(
            folder="Notes",
            success=True,
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:30+00:00",
        )
        self.assertEqual(r.duration_seconds(), 30.0)

    def test_duration_none_on_unparseable(self):
        r = ac.SyncReport(folder="Notes", success=True, started_at="nope")
        self.assertIsNone(r.duration_seconds())

    def test_notes_body_contains_metrics_and_audit(self):
        r = ac.SyncReport(
            folder="Ideas",
            success=True,
            notes_processed=3,
            char_count=1200,
            audit_events=["moved 3 notes", "pushed to github"],
        )
        body = r.to_asana_notes()
        self.assertIn("Folder: Ideas", body)
        self.assertIn("Characters: 1200", body)
        self.assertIn("Sync Resonance:", body)
        self.assertIn("moved 3 notes", body)

    def test_to_dict_roundtrips_json(self):
        r = ac.SyncReport(folder="Notes", success=True, notes_processed=1)
        json.dumps(r.to_dict())  # must be serializable


class ConnectorTests(unittest.TestCase):
    def test_report_sync_creates_task_and_comment(self):
        transport = StubTransport(
            [
                (201, {"data": {"gid": "task-1", "permalink_url": "https://asana/task-1"}}),
                (201, {"data": {"gid": "story-1"}}),
            ]
        )
        connector = ac.AsanaConnector(config=make_config(), transport=transport)
        report = ac.SyncReport(
            folder="Notes",
            success=True,
            notes_processed=2,
            audit_events=["exported", "committed"],
        )
        result = connector.report_sync(report)
        self.assertEqual(result["task_gid"], "task-1")
        self.assertTrue(result["commented"])
        self.assertEqual(len(transport.calls), 2)
        # Task creation targets /tasks with our project + workspace.
        task_call = transport.calls[0]
        self.assertTrue(task_call["url"].endswith("/tasks"))
        self.assertEqual(task_call["body"]["data"]["projects"], ["99999"])
        self.assertEqual(task_call["body"]["data"]["workspace"], "12345")
        # Auth header carries a bearer token (value is a test dummy).
        self.assertTrue(task_call["headers"]["Authorization"].startswith("Bearer "))

    def test_report_sync_no_comment_without_audit(self):
        transport = StubTransport([(201, {"data": {"gid": "t2"}})])
        connector = ac.AsanaConnector(config=make_config(), transport=transport)
        result = connector.report_sync(ac.SyncReport(folder="N", success=True))
        self.assertFalse(result["commented"])
        self.assertEqual(len(transport.calls), 1)

    def test_report_sync_raises_when_unconfigured(self):
        connector = ac.AsanaConnector(config=make_config(project_gid=None))
        with self.assertRaises(ac.AsanaError):
            connector.report_sync(ac.SyncReport(folder="N", success=True))

    def test_api_error_surfaces_message(self):
        transport = StubTransport(
            [(403, {"errors": [{"message": "Not Authorized"}]})]
        )
        connector = ac.AsanaConnector(config=make_config(), transport=transport)
        with self.assertRaises(ac.AsanaError) as ctx:
            connector.report_sync(ac.SyncReport(folder="N", success=True))
        self.assertIn("Not Authorized", str(ctx.exception))
        self.assertEqual(ctx.exception.status, 403)


class SafeReportTests(unittest.TestCase):
    def test_disabled_config_skips(self):
        connector = ac.AsanaConnector(config=make_config(enabled=False))
        result = connector.safe_report_sync(ac.SyncReport(folder="N", success=True))
        self.assertFalse(result["reported"])
        self.assertEqual(result["reason"], "disabled")

    def test_unconfigured_skips(self):
        connector = ac.AsanaConnector(config=make_config(project_gid=None))
        result = connector.safe_report_sync(ac.SyncReport(folder="N", success=True))
        self.assertFalse(result["reported"])
        self.assertEqual(result["reason"], "unconfigured")

    def test_api_failure_is_non_fatal(self):
        transport = StubTransport([(500, {"errors": [{"message": "boom"}]})])
        connector = ac.AsanaConnector(config=make_config(), transport=transport)
        result = connector.safe_report_sync(ac.SyncReport(folder="N", success=True))
        self.assertFalse(result["reported"])
        self.assertIn("boom", result["error"])

    def test_success_path_reports(self):
        transport = StubTransport([(201, {"data": {"gid": "t9"}})])
        connector = ac.AsanaConnector(config=make_config(), transport=transport)
        result = connector.safe_report_sync(ac.SyncReport(folder="N", success=True))
        self.assertTrue(result["reported"])
        self.assertEqual(result["task_gid"], "t9")


class BuildReportTests(unittest.TestCase):
    def test_build_from_outcome_success(self):
        outcome = {"folder": "Notes", "partial": False, "notes_processed": 5, "loop_count": 1}
        report = ac.build_report_from_outcome(outcome, char_count=500)
        self.assertEqual(report.folder, "Notes")
        self.assertTrue(report.success)
        self.assertFalse(report.partial)
        self.assertEqual(report.notes_processed, 5)
        self.assertEqual(report.files_written, 5)
        self.assertEqual(report.char_count, 500)
        self.assertIsNotNone(report.finished_at)

    def test_build_from_outcome_partial(self):
        outcome = {"folder": "N", "partial": True, "notes_processed": 2, "loop_count": 1}
        report = ac.build_report_from_outcome(outcome)
        self.assertTrue(report.partial)
        self.assertTrue(report.success)  # partial is still a completed run

    def test_build_from_outcome_aborted(self):
        outcome = {"folder": "N", "aborted_by_user": True, "notes_processed": 0}
        report = ac.build_report_from_outcome(outcome)
        self.assertFalse(report.success)


@unittest.skipUnless(
    os.environ.get(ac.ENV_LIVE_TESTS) == "1",
    "live Asana test disabled (set RUN_LIVE_ASANA_TESTS=1 and real env vars to enable)",
)
class LiveAsanaSmokeTest(unittest.TestCase):
    def test_live_create_task(self):
        config = ac.AsanaConfig.from_env()
        self.assertTrue(
            config.is_configured,
            "RUN_LIVE_ASANA_TESTS=1 requires ASANA_ACCESS_TOKEN + "
            "ASANA_PROJECT_GITMYNOTES (+ optional workspace) in the env.",
        )
        connector = ac.AsanaConnector(config=config)
        report = ac.SyncReport(
            folder="__gitmynotes_live_test__",
            success=True,
            notes_processed=0,
            audit_events=["live smoke test"],
        )
        result = connector.report_sync(report)
        self.assertIsNotNone(result["task_gid"])


if __name__ == "__main__":
    unittest.main()
