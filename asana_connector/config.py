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
    """

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
            api_token: Asana Personal Access Token (falls back to ASANA_API_TOKEN env var)
            workspace_id: Workspace GID (falls back to ASANA_WORKSPACE_ID)
            portfolio_id: NWW portfolio GID (falls back to ASANA_PORTFOLIO_ID)
            project_ids: Dict of project names → GIDs (falls back to env vars)
        """
        self.api_token = api_token or os.getenv("ASANA_API_TOKEN")
        self.workspace_id = workspace_id or os.getenv("ASANA_WORKSPACE_ID")
        self.portfolio_id = portfolio_id or os.getenv("ASANA_PORTFOLIO_ID")

        self.project_ids = project_ids or {
            "shadow_garden": os.getenv("ASANA_PROJECT_SHADOWGARDEN"),
            "gitmynotes": os.getenv("ASANA_PROJECT_GITMYNOTES"),
            "spell_simulator": os.getenv("ASANA_PROJECT_SPELLSIM"),
        }

        self._validate()

    def _validate(self):
        """Validate that required credentials are present."""
        if not self.api_token:
            raise ValueError(
                "ASANA_API_TOKEN not set. Provide via env var or constructor."
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
