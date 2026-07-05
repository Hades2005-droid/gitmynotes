"""
GitMyNotes Asana Adapter.
Reports note synchronization and audit trail metrics to Asana.

Integrates with gitmynotes.py to capture sync success rates, note counts,
and audit trail events, then pushes them to Asana as tasks with technique
mastery tracking.
"""

import os
import json
from typing import Dict, Optional, List, Any, Tuple
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict

# Import shared connector
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from asana_connector import (
    AsanaClient,
    AsanaConfig,
    DataMapper,
)


@dataclass
class SyncMetrics:
    """Note synchronization metrics."""

    timestamp: str  # ISO format
    folder_name: str  # macOS Notes folder
    notes_processed: int  # Count of notes synced
    notes_failed: int  # Count that failed
    sync_duration_ms: float  # Milliseconds
    success: bool  # Overall success
    conflicts_found: int = 0
    conflicts_resolved: int = 0
    total_characters: int = 0
    git_commit_hash: Optional[str] = None
    error_message: Optional[str] = None


class GitMyNotesAsanaReporter:
    """
    Report note synchronization and audit trail metrics to Asana.

    Integration Points:
    - Hook into git_add_commit_push() for sync events
    - Capture audit trail from DEFAULT_AUDIT_FILE_ENDING
    - Track configuration complexity (technique mastery)
    - Real-time reporting per sync run
    """

    def __init__(self, config: Optional[AsanaConfig] = None):
        """
        Initialize gitmynotes reporter.

        Args:
            config: AsanaConfig instance (uses env vars if not provided)
        """
        self.config = config or AsanaConfig()
        self.client = AsanaClient(self.config.api_token, self.config.workspace_id)

        # Map field IDs from config (set during bootstrap)
        self.field_ids = self._load_field_ids()
        self.mapper = DataMapper(self.field_ids)

        self.project_id = self.config.project_ids.get("gitmynotes")
        if not self.project_id:
            raise ValueError("ASANA_PROJECT_GITMYNOTES not configured")

    def _load_field_ids(self) -> Dict[str, str]:
        """
        Load custom field IDs from environment or config.
        Set during bootstrap; must match Asana workspace.
        """
        return {
            "copy_technique_success": os.getenv("ASANA_FIELD_COPY_TECHNIQUE"),
            "technique_mastery": os.getenv("ASANA_FIELD_TECHNIQUE_MASTERY"),
            "soul_alignment": os.getenv("ASANA_FIELD_SOUL_ALIGNMENT"),
            "last_reported": os.getenv("ASANA_FIELD_LAST_REPORTED"),
            "metrics_json": os.getenv("ASANA_FIELD_METRICS_JSON"),
        }

    # ============ Sync Reporting ============

    def report_sync(
        self,
        metrics: SyncMetrics,
        audit_entries: Optional[List[str]] = None,
        include_in_aggregates: bool = True,
    ) -> Dict[str, Any]:
        """
        Report a note synchronization run to Asana.

        Args:
            metrics: SyncMetrics instance
            audit_entries: List of audit trail entries from this sync
            include_in_aggregates: Whether to include in rollup summaries

        Returns:
            Created Asana task data
        """
        success_rate = self._calculate_success_rate(
            metrics.notes_processed, metrics.notes_failed
        )

        task_name = f"Note Sync: {metrics.folder_name} - {metrics.timestamp[:10]}"
        task_description = self._build_sync_description(metrics, success_rate)

        # Map metrics to custom fields
        custom_fields = self._map_sync_metrics(metrics, success_rate)

        # Create task
        task = self.client.create_task(
            name=task_name,
            project_id=self.project_id,
            description=task_description,
            custom_fields=custom_fields,
        )

        task_id = task.get("gid")

        # Add metric summary comment
        metric_summary = self._format_metric_summary(
            metrics, "Note Sync", include_in_aggregates
        )
        self.client.add_task_comment(task_id, metric_summary)

        # Add audit trail as separate comment
        if audit_entries:
            audit_comment = self._format_audit_trail(audit_entries)
            self.client.add_task_comment(task_id, audit_comment)

        return task

    def _build_sync_description(self, metrics: SyncMetrics, success_rate: float) -> str:
        """Build detailed task description for sync."""
        status = "✅ Success" if metrics.success else "❌ Failed"
        mastery = self._score_to_mastery(success_rate)

        return f"""{status}

**Folder**: {metrics.folder_name}
**Timestamp**: {metrics.timestamp}
**Notes Processed**: {metrics.notes_processed}
**Notes Failed**: {metrics.notes_failed}
**Success Rate**: {success_rate:.1f}%
**Sync Duration**: {metrics.sync_duration_ms:.1f}ms
**Total Characters**: {metrics.total_characters}
**Technique Mastery**: {mastery}

{f"**Git Commit**: `{metrics.git_commit_hash}`" if metrics.git_commit_hash else ""}
{f"**Conflicts**: {metrics.conflicts_found} found, {metrics.conflicts_resolved} resolved" if metrics.conflicts_found > 0 else ""}
{f"**Error**: {metrics.error_message}" if metrics.error_message else ""}
"""

    def _map_sync_metrics(self, metrics: SyncMetrics, success_rate: float) -> Dict[str, Any]:
        """Map sync metrics to Asana custom fields."""
        return {
            **self.mapper.map_copy_technique_success(success_rate),
            **self.mapper.map_technique_mastery(self._score_to_mastery(success_rate)),
            **self.mapper.map_soul_alignment(
                "Synchronized Resonance" if success_rate >= 90 else "Harmonizing Technique"
            ),
            **self.mapper.map_metrics_json({
                "folder": metrics.folder_name,
                "notes_processed": metrics.notes_processed,
                "notes_failed": metrics.notes_failed,
                "success_rate": success_rate,
                "duration_ms": metrics.sync_duration_ms,
                "total_characters": metrics.total_characters,
                "conflicts_found": metrics.conflicts_found,
                "conflicts_resolved": metrics.conflicts_resolved,
                "git_commit": metrics.git_commit_hash,
            }),
            **self.mapper.map_last_reported(),
        }

    # ============ Audit Trail ============

    def report_audit_events(
        self,
        folder_name: str,
        audit_entries: List[str],
    ) -> None:
        """
        Create a detailed audit trail task.

        Args:
            folder_name: Folder name for context
            audit_entries: List of audit trail entries
        """
        if not audit_entries:
            return

        task_name = f"Audit Trail: {folder_name} - {datetime.now().strftime('%Y-%m-%d')}"
        task_description = f"""**Audit Trail Record**

**Folder**: {folder_name}
**Entries**: {len(audit_entries)}

This task documents the detailed audit trail for this sync operation.
See comment below for full audit entries."""

        task = self.client.create_task(
            name=task_name,
            project_id=self.project_id,
            description=task_description,
            custom_fields=self.mapper.map_last_reported(),
        )

        # Add full audit trail as comment
        audit_comment = self._format_audit_trail(audit_entries)
        self.client.add_task_comment(task.get("gid"), audit_comment)

    @staticmethod
    def _format_audit_trail(audit_entries: List[str]) -> str:
        """Format audit trail entries as a comment."""
        audit_text = "\n".join(f"- {entry}" for entry in audit_entries[:50])  # Limit to 50 entries
        truncation_note = (
            f"\n(+ {len(audit_entries) - 50} more entries)" if len(audit_entries) > 50 else ""
        )

        return f"""**Audit Trail**

{audit_text}{truncation_note}

_See `DEFAULT_AUDIT_FILE_ENDING` in gmn_config.yaml for full history._
"""

    # ============ Daily Summaries ============

    def create_daily_summary(self, date: str = None) -> Dict[str, Any]:
        """
        Create a daily aggregated summary task.

        Args:
            date: Date string (YYYY-MM-DD, defaults to today)

        Returns:
            Created summary task data
        """
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        task_name = f"Daily Sync Summary - {date}"
        task_description = f"""**GitMyNotes Daily Synchronization Report**

Date: {date}

_This is an automated aggregated summary of all note synchronization
activities for this day. Individual sync tasks are linked in the project._

See related tasks tagged with date `{date}`."""

        task = self.client.create_task(
            name=task_name,
            project_id=self.project_id,
            description=task_description,
            custom_fields=self.mapper.map_last_reported(),
        )

        return task

    # ============ Configuration Tracking ============

    def report_configuration_complexity(
        self,
        folder_count: int,
        batch_size: int,
        custom_folder_mappings: int,
        automation_enabled: bool,
    ) -> Dict[str, Any]:
        """
        Report configuration complexity as technique mastery.

        Args:
            folder_count: Number of monitored folders
            batch_size: Batch processing size
            custom_folder_mappings: Custom folder mappings configured
            automation_enabled: Is auto-sync enabled

        Returns:
            Created configuration task
        """
        complexity_score = self._calculate_complexity_score(
            folder_count, batch_size, custom_folder_mappings, automation_enabled
        )
        mastery = self._score_to_mastery(complexity_score)

        task_name = f"Configuration Mastery - {datetime.now().strftime('%Y-%m-%d')}"
        task_description = f"""**GitMyNotes Configuration**

**Complexity Score**: {complexity_score:.1f}/100
**Technique Mastery**: {mastery}

**Configuration Details**:
- Folders Monitored: {folder_count}
- Batch Size: {batch_size}
- Custom Mappings: {custom_folder_mappings}
- Auto-sync Enabled: {automation_enabled}

This reflects the complexity and optimization level of the current configuration."""

        return self.client.create_task(
            name=task_name,
            project_id=self.project_id,
            description=task_description,
            custom_fields={
                **self.mapper.map_technique_mastery(mastery),
                **self.mapper.map_resonance_score(complexity_score),
                **self.mapper.map_last_reported(),
            },
        )

    # ============ Utilities ============

    @staticmethod
    def _calculate_success_rate(processed: int, failed: int) -> float:
        """Calculate sync success rate percentage."""
        if processed == 0:
            return 0.0
        return (processed - failed) / processed * 100

    @staticmethod
    def _calculate_complexity_score(
        folder_count: int,
        batch_size: int,
        custom_mappings: int,
        automation: bool,
    ) -> float:
        """Calculate configuration complexity as a score 0-100."""
        base = min(20 + folder_count * 5, 40)  # Folder count contribution (max 40)
        batch_contrib = 20 if batch_size > 1 else 0  # Batching optimization
        mapping_contrib = min(custom_mappings * 3, 25)  # Custom mappings (max 25)
        automation_contrib = 15 if automation else 0  # Automation enabled
        return min(base + batch_contrib + mapping_contrib + automation_contrib, 100)

    @staticmethod
    def _score_to_mastery(score: float) -> str:
        """Convert numeric score to mastery level."""
        if score >= 95:
            return "Master"
        elif score >= 80:
            return "Expert"
        elif score >= 65:
            return "Adept"
        elif score >= 50:
            return "Novice"
        else:
            return "Novice"

    @staticmethod
    def _format_metric_summary(
        metrics: SyncMetrics,
        metric_type: str,
        include_in_aggregates: bool,
    ) -> str:
        """Format metrics as a comment on the task."""
        aggregate_note = (
            "📊 Included in daily/weekly aggregates"
            if include_in_aggregates
            else "📌 Standalone metric (not included in aggregates)"
        )

        return f"""**{metric_type} Metric Report**

{aggregate_note}

Raw Data (JSON):
```json
{json.dumps(asdict(metrics), indent=2, default=str)}
```
"""

    def health_check(self) -> bool:
        """Test that Asana connection and project are valid."""
        try:
            project = self.client.get_project(self.project_id)
            return bool(project and project.get("gid"))
        except Exception as e:
            print(f"⚠️ Health check failed: {e}")
            return False


# ============ Convenience Functions ============

def report_sync_metrics(
    folder_name: str,
    notes_processed: int,
    notes_failed: int = 0,
    sync_duration_ms: float = 0.0,
    total_characters: int = 0,
    success: bool = True,
    git_commit: str = None,
    audit_entries: List[str] = None,
) -> Dict[str, Any]:
    """
    Convenience function to report note sync metrics.

    Usage:
        from adapters.asana_adapter import report_sync_metrics
        report_sync_metrics(
            folder_name="Work Notes",
            notes_processed=42,
            notes_failed=0,
            sync_duration_ms=1500.0,
            total_characters=50000,
            git_commit="abc123def456",
        )
    """
    reporter = GitMyNotesAsanaReporter()
    metrics = SyncMetrics(
        timestamp=datetime.now().isoformat(),
        folder_name=folder_name,
        notes_processed=notes_processed,
        notes_failed=notes_failed,
        sync_duration_ms=sync_duration_ms,
        success=success,
        total_characters=total_characters,
        git_commit_hash=git_commit,
    )
    return reporter.report_sync(metrics, audit_entries)


def report_configuration(
    folder_count: int,
    batch_size: int = 1,
    custom_mappings: int = 0,
    automation: bool = False,
) -> Dict[str, Any]:
    """
    Convenience function to report configuration complexity.

    Usage:
        from adapters.asana_adapter import report_configuration
        report_configuration(
            folder_count=5,
            batch_size=10,
            custom_mappings=3,
            automation=True,
        )
    """
    reporter = GitMyNotesAsanaReporter()
    return reporter.report_configuration_complexity(
        folder_count, batch_size, custom_mappings, automation
    )
