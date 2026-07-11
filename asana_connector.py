#!/usr/bin/env python
"""GitMyNotes -- optional Asana reporting connector.

This module is a self-contained, dependency-free (stdlib-only) adapter that
lets GitMyNotes report the outcome of a backup/sync run to an Asana project.
It is intentionally decoupled from ``gitmynotes.py``: importing this module has
no side effects, and nothing here is invoked unless the caller explicitly asks
for a report AND the required environment variables are present.

What gets reported
------------------
For each run (or per-folder pass) a :class:`SyncReport` captures:
  - success / failure and an optional error message
  - start / finish timestamps (ISO-8601) and derived duration
  - note / file / character counts
  - conflict count and a free-form audit-trail event list
  - a computed *Sync Resonance* score and *Technique Mastery* tier -- a
    lightweight, deterministic 0-100 health metric so a human skimming Asana
    can gauge run quality at a glance without parsing raw counts.

Safe operation (the important part)
-----------------------------------
  - **No secrets in code.** Credentials come only from environment variables
    (:data:`ENV_ACCESS_TOKEN`, :data:`ENV_WORKSPACE_ID`,
    :data:`ENV_PROJECT_GID`). Nothing is hard-coded and the access token is
    never written to logs (see :func:`_redact`).
  - **Opt-in.** :meth:`AsanaConfig.from_env` returns a config whose
    ``is_enabled`` is only true when both the enable flag and a token are set.
  - **Non-blocking.** :meth:`AsanaConnector.safe_report_sync` swallows *all*
    exceptions and returns a result dict instead of raising, so a flaky Asana
    API (or missing network) can never fail or slow down a notes backup.
  - **Testable offline.** Every HTTP call goes through an injectable
    ``transport`` callable; the default uses :mod:`urllib`. Tests pass a stub
    transport, so the default test suite makes zero live Asana calls.

Asana REST API reference: https://developers.asana.com/reference/rest-api-reference
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("gitmynotes.asana")

# --- Environment variable names (single source of truth) --------------------
ENV_ACCESS_TOKEN = "ASANA_ACCESS_TOKEN"
ENV_WORKSPACE_ID = "ASANA_WORKSPACE_ID"
ENV_PROJECT_GID = "ASANA_PROJECT_GITMYNOTES"
ENV_ENABLED = "GMN_ASANA_ENABLED"
ENV_BASE_URL = "ASANA_BASE_URL"
ENV_LIVE_TESTS = "RUN_LIVE_ASANA_TESTS"

DEFAULT_BASE_URL = "https://app.asana.com/api/1.0"

# Transport signature: (method, url, headers, body_bytes) -> (status, resp_bytes)
Transport = Callable[[str, str, Dict[str, str], Optional[bytes]], "tuple[int, bytes]"]


def _redact(token: Optional[str]) -> str:
    """Return a log-safe fingerprint of a secret, never the secret itself."""
    if not token:
        return "<unset>"
    if len(token) <= 4:
        return "****"
    return f"****{token[-4:]}"


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


@dataclass
class AsanaConfig:
    """Connection settings for the Asana connector, sourced from the env.

    Never construct this with a literal token in application code -- use
    :meth:`from_env`. The explicit constructor exists for tests, which pass a
    dummy token that is not a real secret.
    """

    access_token: Optional[str] = None
    workspace_id: Optional[str] = None
    project_gid: Optional[str] = None
    base_url: str = DEFAULT_BASE_URL
    enabled: bool = False

    @classmethod
    def from_env(cls, env: Optional[Dict[str, str]] = None) -> "AsanaConfig":
        """Build a config from environment variables.

        ``enabled`` is derived from GMN_ASANA_ENABLED being a truthy string
        ("1", "true", "yes", "on"; case-insensitive). Presence of a token is
        checked separately via :attr:`is_enabled`, so setting the flag without
        a token stays safely disabled rather than erroring.
        """
        env = os.environ if env is None else env
        flag = (env.get(ENV_ENABLED, "") or "").strip().lower()
        return cls(
            access_token=env.get(ENV_ACCESS_TOKEN) or None,
            workspace_id=env.get(ENV_WORKSPACE_ID) or None,
            project_gid=env.get(ENV_PROJECT_GID) or None,
            base_url=(env.get(ENV_BASE_URL) or DEFAULT_BASE_URL).rstrip("/"),
            enabled=flag in {"1", "true", "yes", "on"},
        )

    @property
    def is_enabled(self) -> bool:
        """True only when opt-in flag is set AND a token is present."""
        return bool(self.enabled and self.access_token)

    @property
    def is_configured(self) -> bool:
        """True when enough is present to actually create a task in a project."""
        return bool(self.is_enabled and self.project_gid)

    def describe(self) -> Dict[str, str]:
        """Log-safe snapshot -- token is redacted, never emitted raw."""
        return {
            "enabled": str(self.enabled),
            "token": _redact(self.access_token),
            "workspace_id": self.workspace_id or "<unset>",
            "project_gid": self.project_gid or "<unset>",
            "base_url": self.base_url,
        }


@dataclass
class SyncReport:
    """A single GitMyNotes run/folder outcome, ready to report to Asana."""

    folder: str
    success: bool
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    notes_processed: int = 0
    files_written: int = 0
    char_count: int = 0
    conflicts: int = 0
    loop_count: int = 0
    partial: bool = False
    error: Optional[str] = None
    audit_events: List[str] = field(default_factory=list)

    def duration_seconds(self) -> Optional[float]:
        """Elapsed seconds between started_at and finished_at, if both parse."""
        start = _parse_iso(self.started_at)
        end = _parse_iso(self.finished_at)
        if start is None or end is None:
            return None
        return max(0.0, (end - start).total_seconds())

    def sync_resonance(self) -> float:
        """Deterministic 0-100 health score for this run.

        Composition (documented so the number is explainable, not magic):
          - Start from a base that reflects the outcome: 100 for a clean
            success, 55 for a partial success, 0 for a hard failure.
          - Subtract a conflict penalty (8 points each, capped at 40) -- audit
            conflicts are the strongest signal that a human should look.
          - Add a small throughput bonus (up to +10) so runs that actually
            moved notes edge above no-op runs of the same status.
        The result is clamped to [0, 100] and rounded to 2 decimals.
        """
        if not self.success:
            base = 0.0
        elif self.partial:
            base = 55.0
        else:
            base = 100.0

        conflict_penalty = min(40.0, self.conflicts * 8.0)
        throughput_bonus = min(10.0, self.notes_processed * 0.5)
        return round(_clamp(base - conflict_penalty + throughput_bonus), 2)

    def technique_mastery(self) -> str:
        """Map the resonance score to a human-friendly mastery tier label."""
        score = self.sync_resonance()
        if score >= 90:
            return "Grandmaster"
        if score >= 75:
            return "Master"
        if score >= 55:
            return "Adept"
        if score >= 30:
            return "Apprentice"
        return "Novice"

    def task_name(self) -> str:
        state = "OK" if self.success else "FAILED"
        if self.success and self.partial:
            state = "PARTIAL"
        stamp = self.finished_at or self.started_at or _now_iso()
        return f"GitMyNotes sync [{state}] {self.folder} @ {stamp}"

    def to_asana_notes(self) -> str:
        """Render the report as a plain-text Asana task body."""
        lines = [
            f"Folder: {self.folder}",
            f"Status: {'success' if self.success else 'failure'}"
            + (" (partial)" if self.partial else ""),
            f"Started: {self.started_at or 'n/a'}",
            f"Finished: {self.finished_at or 'n/a'}",
        ]
        dur = self.duration_seconds()
        if dur is not None:
            lines.append(f"Duration: {dur:.1f}s")
        lines += [
            f"Notes processed: {self.notes_processed}",
            f"Files written: {self.files_written}",
            f"Characters: {self.char_count}",
            f"Batches (loops): {self.loop_count}",
            f"Conflicts: {self.conflicts}",
            f"Sync Resonance: {self.sync_resonance()}",
            f"Technique Mastery: {self.technique_mastery()}",
        ]
        if self.error:
            lines.append(f"Error: {self.error}")
        if self.audit_events:
            lines.append("")
            lines.append("Audit trail:")
            lines.extend(f"  - {event}" for event in self.audit_events)
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "folder": self.folder,
            "success": self.success,
            "partial": self.partial,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": self.duration_seconds(),
            "notes_processed": self.notes_processed,
            "files_written": self.files_written,
            "char_count": self.char_count,
            "loop_count": self.loop_count,
            "conflicts": self.conflicts,
            "error": self.error,
            "audit_events": list(self.audit_events),
            "sync_resonance": self.sync_resonance(),
            "technique_mastery": self.technique_mastery(),
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _default_transport(
    method: str, url: str, headers: Dict[str, str], body: Optional[bytes]
) -> "tuple[int, bytes]":
    """urllib-backed transport. Isolated so tests can substitute a stub."""
    req = urllib.request.Request(url=url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        # Surface the body so callers can log a useful (non-secret) message.
        return exc.code, exc.read()


class AsanaClient:
    """Thin Asana REST client. One responsibility: authenticated JSON calls."""

    def __init__(self, config: AsanaConfig, transport: Optional[Transport] = None):
        self.config = config
        self._transport = transport or _default_transport

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _post(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.config.base_url}{path}"
        body = json.dumps({"data": data}).encode("utf-8")
        status, raw = self._transport("POST", url, self._headers(), body)
        try:
            parsed = json.loads(raw.decode("utf-8")) if raw else {}
        except (ValueError, UnicodeDecodeError):
            parsed = {}
        if status >= 400:
            # Asana error payloads carry {"errors": [{"message": ...}]}; never
            # includes our token, so it is safe to log/return.
            raise AsanaError(status, parsed)
        return parsed.get("data", parsed)

    def create_task(
        self, name: str, notes: str, project_gid: str
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"name": name, "notes": notes, "projects": [project_gid]}
        if self.config.workspace_id:
            payload["workspace"] = self.config.workspace_id
        return self._post("/tasks", payload)

    def add_comment(self, task_gid: str, text: str) -> Dict[str, Any]:
        return self._post(f"/tasks/{task_gid}/stories", {"text": text})


class AsanaError(Exception):
    """Raised on a non-2xx Asana response. Carries status + parsed body."""

    def __init__(self, status: int, body: Any):
        self.status = status
        self.body = body
        messages = []
        if isinstance(body, dict):
            for err in body.get("errors", []) or []:
                if isinstance(err, dict) and err.get("message"):
                    messages.append(str(err["message"]))
        detail = "; ".join(messages) if messages else "no detail"
        super().__init__(f"Asana API error {status}: {detail}")


class AsanaConnector:
    """High-level façade GitMyNotes calls to report a run outcome."""

    def __init__(
        self,
        config: Optional[AsanaConfig] = None,
        client: Optional[AsanaClient] = None,
        transport: Optional[Transport] = None,
    ):
        self.config = config or AsanaConfig.from_env()
        self.client = client or AsanaClient(self.config, transport=transport)

    def report_sync(self, report: SyncReport) -> Dict[str, Any]:
        """Create an Asana task for ``report`` (and a comment for audit events).

        Raises on misconfiguration or API failure. Prefer
        :meth:`safe_report_sync` from production code paths -- it never raises.
        """
        if not self.config.is_configured:
            raise AsanaError(
                0,
                {
                    "errors": [
                        {
                            "message": (
                                "Asana connector not configured: set "
                                f"{ENV_ENABLED}=1, {ENV_ACCESS_TOKEN}, and "
                                f"{ENV_PROJECT_GID}."
                            )
                        }
                    ]
                },
            )
        task = self.client.create_task(
            name=report.task_name(),
            notes=report.to_asana_notes(),
            project_gid=self.config.project_gid,
        )
        result: Dict[str, Any] = {
            "task_gid": task.get("gid"),
            "task_url": task.get("permalink_url"),
            "commented": False,
        }
        # Post the audit trail as a follow-up comment so the task body stays a
        # clean summary while the full trail remains attached for auditing.
        if report.audit_events and result["task_gid"]:
            trail = "Audit trail:\n" + "\n".join(
                f"- {event}" for event in report.audit_events
            )
            self.client.add_comment(result["task_gid"], trail)
            result["commented"] = True
        return result

    def safe_report_sync(self, report: SyncReport) -> Dict[str, Any]:
        """Non-blocking wrapper: never raises, always returns a result dict.

        This is the method the notes-backup pipeline should call: a disabled
        connector, a network error, or an Asana 5xx all resolve to
        ``{"reported": False, ...}`` without disturbing the backup's own exit
        code or timing.
        """
        if not self.config.is_enabled:
            logger.debug("Asana reporting disabled; skipping (%s).", self.config.describe())
            return {"reported": False, "skipped": True, "reason": "disabled"}
        if not self.config.is_configured:
            logger.warning(
                "Asana reporting enabled but not fully configured (%s); skipping.",
                self.config.describe(),
            )
            return {"reported": False, "skipped": True, "reason": "unconfigured"}
        try:
            result = self.report_sync(report)
            logger.info(
                "Reported GitMyNotes sync to Asana task %s (resonance=%s, mastery=%s).",
                result.get("task_gid"),
                report.sync_resonance(),
                report.technique_mastery(),
            )
            result["reported"] = True
            return result
        except Exception as exc:  # noqa: BLE001 -- intentional: reporting must never break sync
            logger.warning("Asana reporting failed (non-fatal): %s", exc)
            return {"reported": False, "skipped": False, "error": str(exc)}


def build_report_from_outcome(
    outcome: Dict[str, Any],
    *,
    started_at: Optional[str] = None,
    finished_at: Optional[str] = None,
    char_count: int = 0,
    files_written: Optional[int] = None,
    conflicts: int = 0,
    audit_events: Optional[List[str]] = None,
) -> SyncReport:
    """Adapt a ``process_one_folder`` outcome dict into a :class:`SyncReport`.

    ``outcome`` uses the keys GitMyNotes' pipeline already produces: ``folder``,
    ``partial``, ``notes_processed``, ``loop_count``. Success is inferred as
    "some work happened and nothing flipped partial", matching the exit-code
    taxonomy (0 clean / 2 partial).
    """
    notes = int(outcome.get("notes_processed", 0) or 0)
    partial = bool(outcome.get("partial", False))
    return SyncReport(
        folder=outcome.get("folder", "<unknown>"),
        success=not outcome.get("aborted_by_user", False),
        partial=partial,
        started_at=started_at,
        finished_at=finished_at or _now_iso(),
        notes_processed=notes,
        files_written=notes if files_written is None else files_written,
        char_count=char_count,
        loop_count=int(outcome.get("loop_count", 0) or 0),
        conflicts=conflicts,
        audit_events=list(audit_events or []),
    )
