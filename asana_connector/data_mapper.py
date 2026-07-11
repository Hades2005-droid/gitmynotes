"""
Data mapper for converting project metrics to Asana custom fields.
Bridges technical metrics to their magical/metaphorical representations.
"""

import json
from typing import Dict, Any, Optional
from datetime import datetime
from .schemas import CustomFieldSchemas


class DataMapper:
    """
    Map technical project metrics to Asana custom field values.
    Handles bilingual presentation: technical backing, magical display names.
    """

    def __init__(self, custom_field_ids: Dict[str, str]):
        """
        Initialize data mapper.

        Args:
            custom_field_ids: Map of field keys to Asana custom field GIDs
        """
        self.field_ids = custom_field_ids

    # ============ Generic Mappers ============

    def map_resonance_score(self, technical_score: float) -> Dict[str, Any]:
        """
        Map a technical metric (0-100) to resonance score.

        Args:
            technical_score: Quality/performance metric (0-100)

        Returns:
            Asana custom field dict
        """
        field_id = self.field_ids.get("resonance_score")
        if not field_id:
            return {}

        return {
            "gid": field_id,
            "number_value": min(100, max(0, technical_score)),
        }

    def map_technique_mastery(self, mastery_level: str) -> Dict[str, Any]:
        """
        Map technical proficiency to technique mastery level.

        Args:
            mastery_level: One of: Novice, Adept, Expert, Master, Transcendent

        Returns:
            Asana custom field dict
        """
        field_id = self.field_ids.get("technique_mastery")
        if not field_id:
            return {}

        valid_levels = ["Novice", "Adept", "Expert", "Master", "Transcendent"]
        if mastery_level not in valid_levels:
            mastery_level = "Adept"  # default

        return {
            "gid": field_id,
            "text_value": mastery_level,
        }

    def map_soul_alignment(self, descriptor: str) -> Dict[str, Any]:
        """
        Map technical alignment to soul alignment descriptor.

        Args:
            descriptor: Thematic descriptor (e.g., "Harmonious", "Ascending")

        Returns:
            Asana custom field dict
        """
        field_id = self.field_ids.get("soul_alignment")
        if not field_id:
            return {}

        return {
            "gid": field_id,
            "text_value": descriptor,
        }

    def map_copy_technique_success(self, success_percentage: float) -> Dict[str, Any]:
        """
        Map sync/replication success percentage.

        Args:
            success_percentage: Success rate 0-100

        Returns:
            Asana custom field dict
        """
        field_id = self.field_ids.get("copy_technique_success")
        if not field_id:
            return {}

        return {
            "gid": field_id,
            "number_value": min(100, max(0, success_percentage)),
        }

    def map_metrics_json(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Store raw metrics as JSON in hidden field.

        Args:
            metrics: Technical metrics dict

        Returns:
            Asana custom field dict
        """
        field_id = self.field_ids.get("metrics_json")
        if not field_id:
            return {}

        return {
            "gid": field_id,
            "text_value": json.dumps(metrics),
        }

    def map_last_reported(self, timestamp: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Map timestamp of last report.

        Args:
            timestamp: When metrics were captured (defaults to now)

        Returns:
            Asana custom field dict
        """
        field_id = self.field_ids.get("last_reported")
        if not field_id:
            return {}

        ts = timestamp or datetime.utcnow()
        return {
            "gid": field_id,
            "date_value": ts.strftime("%Y-%m-%d"),
        }

    # ============ Project-Specific Mappers ============

    def map_shadow_garden_metrics(
        self,
        voice_quality_score: float,
        chat_sync_success_rate: float,
        total_messages: int,
    ) -> Dict[str, Any]:
        """
        Map shadow-garden-launcher metrics to custom fields.

        Args:
            voice_quality_score: Voice synthesis quality (0-100)
            chat_sync_success_rate: Grok chat sync success (0-100)
            total_messages: Total messages synced

        Returns:
            Dict of custom field assignments
        """
        avg_score = (voice_quality_score + chat_sync_success_rate) / 2
        mastery = self._score_to_mastery(avg_score)
        resonance = self._score_to_soul_alignment(avg_score)

        return {
            **self.map_resonance_score(avg_score),
            **self.map_technique_mastery(mastery),
            **self.map_soul_alignment(resonance),
            **self.map_metrics_json({
                "voice_quality": voice_quality_score,
                "chat_sync_success": chat_sync_success_rate,
                "total_messages": total_messages,
            }),
            **self.map_last_reported(),
        }

    def map_gitmynotes_metrics(
        self,
        sync_success_rate: float,
        notes_synced: int,
        conflicts_resolved: int,
        total_audit_entries: int,
    ) -> Dict[str, Any]:
        """
        Map gitmynotes metrics to custom fields.

        Args:
            sync_success_rate: Percentage of successful syncs (0-100)
            notes_synced: Count of notes synced
            conflicts_resolved: Count of conflicts resolved
            total_audit_entries: Total audit trail entries

        Returns:
            Dict of custom field assignments
        """
        mastery = self._score_to_mastery(sync_success_rate)
        resonance = "Synchronized Resonance" if sync_success_rate > 85 else "Harmonizing"

        return {
            **self.map_copy_technique_success(sync_success_rate),
            **self.map_technique_mastery(mastery),
            **self.map_soul_alignment(resonance),
            **self.map_metrics_json({
                "sync_success_rate": sync_success_rate,
                "notes_synced": notes_synced,
                "conflicts_resolved": conflicts_resolved,
                "audit_entries": total_audit_entries,
            }),
            **self.map_last_reported(),
        }

    def map_spell_simulator_metrics(
        self,
        glyph_accuracy: float,
        compilation_success_rate: float,
        spells_compiled: int,
        copy_technique_precision: float,
    ) -> Dict[str, Any]:
        """
        Map wha-spell-simulator metrics to custom fields.

        Args:
            glyph_accuracy: Glyph recognition accuracy (0-100)
            compilation_success_rate: Spell compilation success (0-100)
            spells_compiled: Count of spells compiled
            copy_technique_precision: Copy technique effectiveness (0-100)

        Returns:
            Dict of custom field assignments
        """
        avg_score = (glyph_accuracy + compilation_success_rate) / 2
        mastery = self._score_to_mastery(avg_score)
        resonance = self._score_to_soul_alignment(avg_score)

        return {
            **self.map_resonance_score(avg_score),
            **self.map_technique_mastery(mastery),
            **self.map_soul_alignment(resonance),
            **self.map_copy_technique_success(copy_technique_precision),
            **self.map_metrics_json({
                "glyph_accuracy": glyph_accuracy,
                "compilation_success": compilation_success_rate,
                "spells_compiled": spells_compiled,
                "copy_technique": copy_technique_precision,
            }),
            **self.map_last_reported(),
        }

    # ============ Helper Methods ============

    @staticmethod
    def _score_to_mastery(score: float) -> str:
        """Convert numeric score to mastery level."""
        if score >= 90:
            return "Master"
        elif score >= 75:
            return "Expert"
        elif score >= 60:
            return "Adept"
        elif score >= 40:
            return "Novice"
        else:
            return "Novice"

    @staticmethod
    def _score_to_soul_alignment(score: float) -> str:
        """Convert numeric score to thematic soul alignment descriptor."""
        if score >= 90:
            return "Transcendent Resonance"
        elif score >= 75:
            return "Ascending Harmony"
        elif score >= 60:
            return "Harmonious Synthesis"
        elif score >= 45:
            return "Emerging Potential"
        else:
            return "Seeking Alignment"

    def build_task_update(
        self,
        task_data: Dict[str, Any],
        custom_fields: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Build a complete task update payload.

        Args:
            task_data: Basic task data (name, description, etc.)
            custom_fields: Custom field assignments

        Returns:
            Complete update dict for Asana task
        """
        return {
            **task_data,
            "custom_fields": custom_fields,
        }
