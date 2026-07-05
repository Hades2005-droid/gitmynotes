"""
Portfolio and project management for NWW Asana Connector.
Handles creation and organization of Asana portfolios, projects, and their relationships.
"""

from typing import Dict, Optional, List, Any
from .client import AsanaClient
from .schemas import CustomFieldSchemas


class PortfolioManager:
    """Manage creation and synchronization of portfolio hierarchy."""

    def __init__(self, client: AsanaClient):
        """
        Initialize portfolio manager.

        Args:
            client: AsanaClient instance
        """
        self.client = client
        self.portfolio_cache: Dict[str, Dict[str, Any]] = {}
        self.project_cache: Dict[str, Dict[str, Any]] = {}

    # ============ Portfolio Setup ============

    def create_nww_portfolio_hierarchy(self) -> Dict[str, str]:
        """
        Create the complete NWW portfolio hierarchy.

        Returns:
            Dict with portfolio IDs:
            {
                "nww_unified": "...",
                "shadow_garden": "...",
                "gitmynotes": "...",
                "spell_simulator": "...",
            }
        """
        # Create top-level portfolio
        nww_unified = self.client.create_portfolio(
            name="NWW Unified Resonance",
            description="Central hub for cross-project magical resonance tracking",
        )
        nww_id = nww_unified.get("gid")
        self.portfolio_cache["nww_unified"] = nww_unified

        # Create sub-portfolios
        portfolios = {
            "nww_unified": nww_id,
            "shadow_garden": self._create_sub_portfolio(
                nww_id,
                "Shadow-Garden Voice Resonance",
                "Voice synthesis & Grok chat orchestration metrics",
            ),
            "gitmynotes": self._create_sub_portfolio(
                nww_id,
                "GitMyNotes Technique Mastery",
                "Note sync & audit trail fidelity tracking",
            ),
            "spell_simulator": self._create_sub_portfolio(
                nww_id,
                "Spell Simulator Soul Resonance",
                "Glyph mastery & spell compilation progression",
            ),
        }

        return portfolios

    def _create_sub_portfolio(
        self,
        parent_id: str,
        name: str,
        description: str,
    ) -> str:
        """Create a sub-portfolio under a parent portfolio."""
        portfolio = self.client.create_portfolio(name=name, description=description)
        portfolio_id = portfolio.get("gid")
        self.portfolio_cache[name] = portfolio
        return portfolio_id

    # ============ Project Setup ============

    def create_nww_projects(self) -> Dict[str, str]:
        """
        Create the three main NWW projects.

        Returns:
            Dict with project IDs:
            {
                "shadow_garden": "...",
                "gitmynotes": "...",
                "spell_simulator": "...",
            }
        """
        projects = {
            "shadow_garden": self._create_project(
                "Shadow-Garden Voice Bridge",
                "Real-time voice synthesis and Grok chat resonance tracking",
            ),
            "gitmynotes": self._create_project(
                "GitMyNotes Sync Pipeline",
                "macOS Notes → GitHub synchronization with audit trail mastery",
            ),
            "spell_simulator": self._create_project(
                "Wha-Spell Simulator Glyph Mastery",
                "Spell glyph recognition and compilation progression",
            ),
        }

        for key, pid in projects.items():
            self.project_cache[key] = {"gid": pid}

        return projects

    def _create_project(self, name: str, description: str) -> str:
        """Create a single project."""
        project = self.client.create_project(name=name, description=description)
        return project.get("gid")

    # ============ Custom Fields Setup ============

    def create_custom_fields(self) -> Dict[str, str]:
        """
        Create all custom fields in the workspace.

        Returns:
            Dict mapping field keys to Asana custom field GIDs
        """
        field_ids = {}
        schemas = CustomFieldSchemas.FIELDS

        for field_key, schema in schemas.items():
            try:
                field = self.client.create_custom_field(
                    name=schema["name"],
                    type=schema["type"],
                    options=schema.get("options"),
                )
                field_ids[field_key] = field.get("gid")
                print(f"✓ Created custom field: {schema['name']} ({field_key})")
            except Exception as e:
                print(f"⚠ Failed to create custom field {field_key}: {e}")
                # Don't raise, continue with other fields

        return field_ids

    # ============ Configuration Export ============

    def export_configuration(
        self,
        portfolio_ids: Dict[str, str],
        project_ids: Dict[str, str],
        field_ids: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Export configuration for use in adapters.

        Returns:
            Configuration dict ready for environment variables or config files
        """
        return {
            "workspace_id": self.client.workspace_id,
            "portfolios": portfolio_ids,
            "projects": project_ids,
            "custom_fields": field_ids,
            "field_descriptions": {
                key: schema.get("description", "")
                for key, schema in CustomFieldSchemas.FIELDS.items()
            },
        }

    def print_setup_summary(
        self,
        portfolio_ids: Dict[str, str],
        project_ids: Dict[str, str],
        field_ids: Dict[str, str],
    ):
        """Print a human-readable setup summary."""
        print("\n" + "=" * 60)
        print("NWW Asana Connector - Setup Complete!")
        print("=" * 60)

        print("\n📋 Portfolios Created:")
        for name, pid in portfolio_ids.items():
            print(f"  {name:20} → {pid}")

        print("\n📊 Projects Created:")
        for name, pid in project_ids.items():
            print(f"  {name:20} → {pid}")

        print("\n✨ Custom Fields Created:")
        for name, fid in field_ids.items():
            schema = CustomFieldSchemas.FIELDS.get(name, {})
            print(f"  {schema.get('name', name):25} → {fid}")

        print("\n" + "=" * 60)
        print("Environment Variables to Set:")
        print("=" * 60)
        print(f"ASANA_WORKSPACE_ID={self.client.workspace_id}")
        print(f"ASANA_PORTFOLIO_ID={portfolio_ids.get('nww_unified', 'NOT_SET')}")
        print(f"ASANA_PROJECT_SHADOWGARDEN={project_ids.get('shadow_garden', 'NOT_SET')}")
        print(f"ASANA_PROJECT_GITMYNOTES={project_ids.get('gitmynotes', 'NOT_SET')}")
        print(f"ASANA_PROJECT_SPELLSIM={project_ids.get('spell_simulator', 'NOT_SET')}")
        print("=" * 60 + "\n")
