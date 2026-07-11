"""
Configuration management for Asana connector.
Loads credentials and workspace IDs from environment variables or config files.
"""

import os
from typing import Optional


class AsanaConfig:
    """
    Manage Asana API credentials and workspace configuration.
    Reads from environment variables first, falls back to provided values.

    Constructing an AsanaConfig never raises just because credentials are
    absent -- an unconfigured instance is a valid "disabled" state. Callers
    should gate on the ``enabled`` property before doing any network work, or
    call ``require_enabled()`` to fail loudly when configuration is mandatory.
    """

    # Accepted env var names for the access token, in priority order. Both are
    # honored so the shared connector, the single-file connectors, and the
    # per-repo adapters agree regardless of which name a deployment sets.
    _TOKEN_ENV_VARS = ("ASANA_ACCESS_TOKEN", "ASANA_API_TOKEN")

    def __init__(
        self,
        api_token: Optional[str] = None,
        workspace_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        project_ids: Optional[dict] = None,
    ):
        """
        Initialize Asana configuration.

        Args:
            api_token: Asana Personal Access Token (falls back to
                ASANA_ACCESS_TOKEN, then ASANA_API_TOKEN env vars)
            workspace_id: Workspace GID (falls back to ASANA_WORKSPACE_ID)
            portfolio_id: NWW portfolio GID (falls back to ASANA_PORTFOLIO_ID)
            project_ids: Dict of project names -> GIDs (falls back to env vars)
        """
        self.api_token = api_token or self._token_from_env()
        self.workspace_id = workspace_id or os.getenv("ASANA_WORKSPACE_ID")
        self.portfolio_id = portfolio_id or os.getenv("ASANA_PORTFOLIO_ID")

        self.project_ids = project_ids or {
            "shadow_garden": os.getenv("ASANA_PROJECT_SHADOWGARDEN"),
            "gitmynotes": os.getenv("ASANA_PROJECT_GITMYNOTES"),
            "spell_simulator": os.getenv("ASANA_PROJECT_SPELLSIM"),
        }

    @classmethod
    def _token_from_env(cls) -> Optional[str]:
        for name in cls._TOKEN_ENV_VARS:
            value = os.getenv(name)
            if value:
                return value
        return None

    @classmethod
    def from_env(cls) -> "AsanaConfig":
        """Build a config purely from environment variables."""
        return cls()

    @property
    def enabled(self) -> bool:
        """
        Reporting is active only when both an access token and a workspace
        are configured. This is the single guard every caller should check
        before constructing a client or making any network request.
        """
        return bool(self.api_token and self.workspace_id)

    # Backwards-compatible alias (the single-file connectors expose is_enabled).
    @property
    def is_enabled(self) -> bool:
        return self.enabled

    def require_enabled(self) -> None:
        """Raise if the config is not fully populated for live reporting."""
        if not self.api_token:
            raise ValueError(
                "Asana access token not set. Provide via ASANA_ACCESS_TOKEN "
                "(or ASANA_API_TOKEN) env var or the constructor."
            )
        if not self.workspace_id:
            raise ValueError(
                "ASANA_WORKSPACE_ID not set. Provide via env var or constructor."
            )

    def to_dict(self) -> dict:
        """Return config as dict (without sensitive data)."""
        return {
            "workspace_id": self.workspace_id,
            "portfolio_id": self.portfolio_id,
            "project_ids": self.project_ids,
        }
