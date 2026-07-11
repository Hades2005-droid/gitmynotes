"""
Custom field schema definitions for NWW Asana Connector.
Defines the structure and metadata for all Asana custom fields used across projects.
"""

from typing import Dict, List, Any


class CustomFieldSchemas:
    """Define custom field schemas for bilingual technical + magical tracking."""

    # Technical backing, magical presentation
    FIELDS = {
        "resonance_score": {
            "name": "Resonance Score",
            "type": "number",
            "description": "Technical: Performance/quality metric (0-100). Magical: Soul alignment coefficient.",
            "precision": 0,
            "min_value": 0,
            "max_value": 100,
            "display_type": "slider",
        },
        "technique_mastery": {
            "name": "Technique Mastery",
            "type": "text",
            "description": "Technical: Optimization/complexity level. Magical: Mastery grade (Novice→Master)",
            "options": ["Novice", "Adept", "Expert", "Master", "Transcendent"],
        },
        "soul_alignment": {
            "name": "Soul Alignment",
            "type": "text",
            "description": "Technical: Feature completeness. Magical: Thematic resonance descriptor.",
            "example": "Harmonious Synthesis, Ascending Resonance, etc.",
        },
        "copy_technique_success": {
            "name": "Copy Technique Success",
            "type": "number",
            "description": "Technical: Replication/sync success rate (%). Magical: Technique precision.",
            "precision": 1,
            "min_value": 0,
            "max_value": 100,
            "display_type": "percentage",
        },
        "last_reported": {
            "name": "Last Reported",
            "type": "date",
            "description": "When metrics were last pushed to Asana (auto-updated)",
        },
        "metrics_json": {
            "name": "Metrics JSON",
            "type": "text",
            "description": "Technical: Raw metric blob for detailed analysis. Hidden from UI.",
            "format": "json",
            "is_hidden": True,
        },
    }

    # Project-specific field mappings
    PROJECT_FIELD_MAPS = {
        "shadow_garden": {
            "primary_metric": "resonance_score",
            "description": "Voice synthesis & Grok chat resonance",
            "custom_fields": [
                "resonance_score",
                "technique_mastery",
                "soul_alignment",
                "last_reported",
                "metrics_json",
            ],
        },
        "gitmynotes": {
            "primary_metric": "copy_technique_success",
            "description": "Note sync & audit trail fidelity",
            "custom_fields": [
                "copy_technique_success",
                "technique_mastery",
                "soul_alignment",
                "last_reported",
                "metrics_json",
            ],
        },
        "spell_simulator": {
            "primary_metric": "resonance_score",
            "description": "Glyph mastery & spell compilation",
            "custom_fields": [
                "resonance_score",
                "technique_mastery",
                "soul_alignment",
                "copy_technique_success",
                "last_reported",
                "metrics_json",
            ],
        },
    }

    @classmethod
    def get_field_schema(cls, field_key: str) -> Dict[str, Any]:
        """Get schema for a specific field."""
        return cls.FIELDS.get(field_key, {})

    @classmethod
    def get_all_fields(cls) -> Dict[str, Dict[str, Any]]:
        """Get all field schemas."""
        return cls.FIELDS

    @classmethod
    def get_project_fields(cls, project_key: str) -> List[str]:
        """Get custom field keys needed for a project."""
        if project_key not in cls.PROJECT_FIELD_MAPS:
            raise ValueError(f"Unknown project: {project_key}")
        return cls.PROJECT_FIELD_MAPS[project_key]["custom_fields"]

    @classmethod
    def describe(cls, field_key: str) -> str:
        """Get human-readable description of a field."""
        field = cls.get_field_schema(field_key)
        return field.get("description", "")
