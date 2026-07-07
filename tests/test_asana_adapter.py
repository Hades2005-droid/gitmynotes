"""Unit tests for GitMyNotes Asana adapter with mocked HTTP responses."""

import unittest
from unittest.mock import patch
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from adapters.asana_adapter import GitMyNotesAsanaReporter, SyncMetrics
from asana_connector.config import AsanaConfig


class MockAsanaClient:
    """Mock Asana API client for testing."""

    def __init__(self, api_token, workspace_id):
        self.api_token = api_token
        self.workspace_id = workspace_id

    def create_task(self, name, project_id, description=None, custom_fields=None):
        return {"gid": "mock-task-1", "name": name}

    def add_task_comment(self, task_id, text):
        return {"gid": "mock-comment-1", "text": text}

    def get_project(self, project_id):
        return {"gid": project_id, "name": "Mock Project"}

    def test_connection(self):
        return True


class TestGitMyNotesConfig(unittest.TestCase):
    """Test configuration for GitMyNotes Asana integration."""

    def test_config_from_env(self):
        """Test loading config from environment variables."""
        with patch.dict(
            os.environ,
            {
                "ASANA_API_TOKEN": "test-token",
                "ASANA_WORKSPACE_ID": "test-workspace",
                "ASANA_PROJECT_GITMYNOTES": "test-project",
            },
        ):
            config = AsanaConfig()
            self.assertEqual(config.api_token, "test-token")


class TestSyncMetrics(unittest.TestCase):
    """Test sync metrics dataclass."""

    def test_metrics_creation(self):
        """Test creating sync metrics."""
        metrics = SyncMetrics(
            timestamp="2026-07-05T12:00:00Z",
            folder_name="Work Notes",
            notes_processed=42,
            notes_failed=0,
            sync_duration_ms=1500.0,
            success=True,
        )
        self.assertEqual(metrics.folder_name, "Work Notes")
        self.assertEqual(metrics.notes_processed, 42)
        self.assertTrue(metrics.success)

    def test_failed_sync_metrics(self):
        """Test metrics for failed sync."""
        metrics = SyncMetrics(
            timestamp="2026-07-05T12:00:00Z",
            folder_name="Work Notes",
            notes_processed=30,
            notes_failed=5,
            sync_duration_ms=2000.0,
            success=False,
            error_message="Conflict resolution failed",
        )
        self.assertFalse(metrics.success)
        self.assertGreater(metrics.notes_failed, 0)


class TestGitMyNotesReporter(unittest.TestCase):
    """Test GitMyNotesAsanaReporter with mocked client."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = AsanaConfig(
            api_token="test-token",
            workspace_id="test-workspace",
            project_ids={"gitmynotes": "test-project-id"},
        )

    @patch("adapters.asana_adapter.AsanaClient", MockAsanaClient)
    def test_report_sync(self):
        """Test reporting sync metrics."""
        reporter = GitMyNotesAsanaReporter(self.config)
        reporter.field_ids = {
            "copy_technique_success": "field-1",
            "technique_mastery": "field-2",
            "soul_alignment": "field-3",
            "last_reported": "field-4",
            "metrics_json": "field-5",
        }

        metrics = SyncMetrics(
            timestamp="2026-07-05T12:00:00Z",
            folder_name="Work Notes",
            notes_processed=42,
            notes_failed=0,
            sync_duration_ms=1500.0,
            success=True,
        )

        task = reporter.report_sync(metrics)
        self.assertIsNotNone(task)

    @patch("adapters.asana_adapter.AsanaClient", MockAsanaClient)
    def test_configuration_complexity(self):
        """Test reporting configuration complexity."""
        reporter = GitMyNotesAsanaReporter(self.config)
        reporter.field_ids = {
            "technique_mastery": "field-2",
            "resonance_score": "field-1",
            "last_reported": "field-4",
        }

        task = reporter.report_configuration_complexity(
            folder_count=5, batch_size=10, custom_folder_mappings=3, automation_enabled=True
        )
        self.assertIsNotNone(task)

    def test_success_rate_calculation(self):
        """Test success rate calculation utility."""
        rate = GitMyNotesAsanaReporter._calculate_success_rate(100, 5)
        self.assertEqual(rate, 95.0)

        rate_zero = GitMyNotesAsanaReporter._calculate_success_rate(0, 0)
        self.assertEqual(rate_zero, 0.0)

    def test_no_secrets_in_adapter(self):
        """Verify no hardcoded secrets in adapter code."""
        adapter_file = Path(__file__).parent.parent / "adapters" / "asana_adapter.py"
        content = adapter_file.read_text()
        self.assertNotIn("Bearer ", content)


if __name__ == "__main__":
    unittest.main()
